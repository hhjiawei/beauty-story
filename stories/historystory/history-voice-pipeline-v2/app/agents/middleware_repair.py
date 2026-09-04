"""悬空 tool_call 修复中间件（deepagents#2703 线上事故对策）。

事故链：模型输出被 max_tokens 截断（finish_reason=length）→ 工具调用参数 JSON
残缺 → langchain-openai 将其归入 invalid_tool_calls → ToolNode 只执行合法的
tool_calls、不为其生成 ToolMessage → 下一次模型调用的消息序列里出现
「带 tool_calls 却没有对应 tool 返回」的 assistant 消息 → API 400：
"An assistant message with 'tool_calls' must be followed by tool messages..."

deepagents 自带的 PatchToolCallsMiddleware 只在 before_agent（整轮开始）修一次，
管不到循环中段新产生的悬空调用。本中间件在每次模型调用前扫描并补齐，
并借 ToolMessage 告知模型「参数被截断，请分块重试」，让 agent 循环活下去。
"""
from __future__ import annotations

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage

_TRUNCATED_HINT = (
    "该工具调用未被执行：上次响应在输出工具参数时被长度截断"
    "（finish_reason=length），参数 JSON 不完整。"
    "请把要写的内容拆小，分多次工具调用完成（例如先 write_file 写前半、"
    "再用后续调用追加），然后继续任务。"
)


class DanglingToolCallRepairMiddleware(AgentMiddleware):
    """每次模型调用前，给没有 ToolMessage 应答的 tool_call/invalid_tool_call
    补一条说明性 ToolMessage。"""

    name = "dangling_tool_call_repair"

    @staticmethod
    def _repair(request):
        messages = list(request.messages)
        answered = {m.tool_call_id for m in messages if m.type == "tool"}
        out: list = []
        changed = False
        for m in messages:
            out.append(m)
            if not isinstance(m, AIMessage):
                continue
            for tc in (*m.tool_calls, *m.invalid_tool_calls):
                tcid = tc.get("id")
                if tcid and tcid not in answered:
                    answered.add(tcid)
                    changed = True
                    out.append(ToolMessage(
                        content=_TRUNCATED_HINT,
                        name=tc.get("name") or "unknown",
                        tool_call_id=tcid,
                    ))
        return request.override(messages=out) if changed else request

    def wrap_model_call(self, request, handler):
        return handler(self._repair(request))

    async def awrap_model_call(self, request, handler):
        return await handler(self._repair(request))