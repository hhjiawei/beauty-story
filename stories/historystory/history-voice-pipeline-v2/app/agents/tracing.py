"""节点 agent 运行追踪（可观测性）。

三层可见性：
1. 实时层：NodeTraceHandler（LangChain 回调）把 agent 内部每一步——模型往返、
   工具调用（含入参/返回摘要/报错）——实时写进 pipeline.log，
   前端 /api/logs/tail 或控制台可直接看直播。
2. 回溯层：save_trace() 在 agent 跑完后，把完整消息序列（用户输入、模型思考、
   每次工具调用与返回、token 用量）整理成 Markdown 轨迹文件，
   存 data/agent_traces/，供事后逐条回放。
3. API 层：GET /api/agent-traces[/file]（在 settings_api.py）列出/读取轨迹文件。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler

from .. import config
from ..logging_setup import get_logger
from .lc_models import _content_text


def _clip(text, n: int = 160) -> str:
    """日志单行摘要：压平空白 + 截断。"""
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n] + "…"


# ---------------------------------------------------------------- 实时层：回调 → pipeline.log

class NodeTraceHandler(BaseCallbackHandler):
    """把 agent 内部的模型往返与工具调用实时写进日志。"""

    def __init__(self, node_id: str):
        super().__init__()
        self.node_id = node_id
        self.log = get_logger()
        self._round = 0

    # ---- 模型 ----
    def on_chat_model_start(self, serialized, messages, **kwargs):
        self._round += 1
        n = sum(len(m) for m in messages) if messages else 0
        self.log.info("[%s] → 模型调用 第%d轮（上下文 %d 条消息）",
                      self.node_id, self._round, n)

    def on_llm_end(self, response, **kwargs):
        msg = None
        try:
            gens = response.generations[0]
            msg = gens[0].message if gens else None
        except Exception:  # noqa: BLE001
            pass
        usage = getattr(msg, "usage_metadata", None) if msg else None
        if usage:
            self.log.info("[%s] ← 模型返回（token 入%s/出%s）", self.node_id,
                          usage.get("input_tokens", "?"), usage.get("output_tokens", "?"))
        else:
            self.log.info("[%s] ← 模型返回", self.node_id)
        reasoning = _extract_reasoning(msg) if msg else ""
        if reasoning:
            self.log.info("[%s]   模型思考: %s", self.node_id, _clip(reasoning, 300))
        calls = getattr(msg, "tool_calls", None) if msg else None
        if calls:
            self.log.info("[%s]   发起 %d 个工具调用: %s", self.node_id,
                          len(calls), "、".join(c.get("name", "?") for c in calls))

    # ---- 工具 ----
    def on_tool_start(self, serialized, input_str, **kwargs):
        name = (serialized or {}).get("name", "?")
        self.log.info("[%s] 🔧 调用工具 %s  入参: %s", self.node_id, name, _clip(input_str, 200))

    def on_tool_end(self, output, **kwargs):
        # 不同 langchain-core 版本 output 可能是 str 或 ToolMessage
        text = getattr(output, "content", output)
        self.log.info("[%s] ✓ 工具返回 %d 字: %s", self.node_id,
                      len(str(text or "")), _clip(text))

    def on_tool_error(self, error, **kwargs):
        self.log.warning("[%s] ✗ 工具报错: %s", self.node_id, _clip(str(error), 300))


# ---------------------------------------------------------------- 回溯层：完整轨迹文件

def _extract_reasoning(msg) -> str:
    """模型思考内容：兼容 reasoning_content（DeepSeek/Qwen）与 thinking block（Claude）。"""
    if msg is None:
        return ""
    rc = (getattr(msg, "additional_kwargs", None) or {}).get("reasoning_content")
    if rc:
        return str(rc)
    content = getattr(msg, "content", None)
    if isinstance(content, list):
        parts = [b.get("thinking", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "thinking"]
        return "\n".join(p for p in parts if p)
    return ""


def build_trace_markdown(node_id: str, messages: list, note: str = "") -> str:
    """把 agent 的完整消息序列整理成人可读的 Markdown 轨迹。"""
    lines = [f"# Agent 运行轨迹 · {node_id}", "",
             f"- 时间：{datetime.now().isoformat(timespec='seconds')}",
             f"- 消息总数：{len(messages)}"]
    if note:
        lines.append(f"- 备注：{note}")
    total_in = total_out = 0
    for i, m in enumerate(messages):
        role = getattr(m, "type", type(m).__name__)
        lines += ["", "---", ""]
        if role == "human":
            lines += [f"## [{i}] 👤 用户输入", "", _content_text(m.content)]
        elif role == "ai":
            lines.append(f"## [{i}] 🤖 模型")
            reasoning = _extract_reasoning(m)
            if reasoning:
                lines += ["", "> **思考过程**", ">",
                          *[f"> {ln}" for ln in reasoning.splitlines()]]
            text = _content_text(m.content)
            if text.strip():
                lines += ["", text]
            for tc in (getattr(m, "tool_calls", None) or []):
                args = json.dumps(tc.get("args", {}), ensure_ascii=False, indent=2)
                lines += ["", f"**→ 调用工具 `{tc.get('name')}`**", "",
                          "```json", args, "```"]
            usage = getattr(m, "usage_metadata", None)
            if usage:
                total_in += usage.get("input_tokens") or 0
                total_out += usage.get("output_tokens") or 0
                lines += ["", f"_token：入 {usage.get('input_tokens', '?')}"
                              f" / 出 {usage.get('output_tokens', '?')}_"]
        elif role == "tool":
            name = getattr(m, "name", "?")
            status = getattr(m, "status", "success")
            lines += [f"## [{i}] 🔧 工具返回 `{name}`（{status}）", "",
                      str(_content_text(m.content))]
        else:
            lines += [f"## [{i}] （{role}）", "", _content_text(getattr(m, "content", ""))]
    if total_in or total_out:
        lines.insert(4, f"- token 合计：入 {total_in} / 出 {total_out}")
    return "\n".join(lines)


def save_trace(node_id: str, messages: list, note: str = "") -> Path:
    """轨迹落盘：data/agent_traces/<时间戳>_<节点>.md。"""
    d = config.DATA_DIR / "agent_traces"
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:20]
    path = d / f"{ts}_{node_id}.md"
    path.write_text(build_trace_markdown(node_id, messages, note), encoding="utf-8")
    return path