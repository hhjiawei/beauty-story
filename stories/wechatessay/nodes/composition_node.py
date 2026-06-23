"""
wechatessay.nodes.composition_node — 排版节点

职责：
1. 对文章进行公众号风格排版
2. 设计视觉节奏和留白
3. 移动端适配

节点流向：legality → composition → image
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from wechatessay.agents.backend import load_backend
from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.config import get_model_instance, MEMORY_CONFIG, MODEL_CONFIG
from wechatessay.prompts.vx_prompt import COMPOSITION_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import ArticleOutputNode, CompositionNode, GraphState
from wechatessay.tools.base_tools.base_tool import get_base_tools
from wechatessay.tools.mcp_tools.mcp_tool import get_total_tools
from wechatessay.utils.json_utils import parse_json_response

logger = logging.getLogger(__name__)

# SKILL_DIR = Path(__file__).resolve().parent.parent / "backends" / "skills" / "wechat-layout-designer"
SKILL_DIR = Path(__file__).resolve().parent.parent / "backends" / "skills" / "gongzhonghao-typeset"
# ═══════════════════════════════════════════════
# Agent 创建
# ═══════════════════════════════════════════════

def _create_composition_agent(tools: list[BaseTool]) -> Any:
    """创建 composition_node 的 Deep Agent。"""
    backend = load_backend()
    mm = get_memory_manager()
    memory_context = mm.build_memory_context("排版设计")

    skills = [str(SKILL_DIR)] if SKILL_DIR.exists() else []

    system_prompt = COMPOSITION_NODE_SYSTEM_PROMPT
    if memory_context:
        system_prompt = f"{memory_context}\n\n{system_prompt}"

    memory_files = []
    mem_file = Path(MEMORY_CONFIG["long_term_file"])
    if mem_file.exists():
        memory_files.append(str(mem_file))

    return create_deep_agent(
        model=get_model_instance(MODEL_CONFIG.get("analysis_model")),
        tools=tools,
        system_prompt=system_prompt,
        backend=backend,
        memory=memory_files,
        skills=skills,
        name="composition_designer",
    )


# ═══════════════════════════════════════════════
# 新增：结果提取  【新增位置】
# ═══════════════════════════════════════════════
def _extract_final_ai_content(result: dict) -> str:
    """
    从 Agent 返回的 messages 列表中提取最终排版结果。

    问题场景：
        messages = [..., 最终结果(AIMessage), ToolMessage, 空AIMessage]
        直接取 [-1] 会得到空内容，导致解析失败。

    策略：
        1. 从后向前遍历，跳过 ToolMessage（通过 tool_call_id / name 识别）
        2. 优先返回包含排版关键字段（formattedArticle 等）的内容
        3. 兜底返回最后一个非空 AI content
    """
    messages = result.get("messages", [])
    if not messages:
        return ""

    candidates = []

    for msg in reversed(messages):
        # --- 跳过工具消息 ---
        # ToolMessage 通常有 tool_call_id 或 name 属性
        if hasattr(msg, "tool_call_id"):
            continue

        # --- 提取 content ---
        content = getattr(msg, "content", None)
        if content is None:
            continue

        text = str(content).strip()
        if not text:
            continue

        # --- 快速命中：包含排版结果关键字段，直接返回 ---
        if any(keyword in text for keyword in (
                "formattedArticle",
                "formatted_article",
                "compositionNode",
                "composition_node",
                "formatSpec",
                "format_spec",
        )):
            return text

        candidates.append(text)

    # --- 兜底：返回最后一个非空且非工具的 AI content ---
    return candidates[0] if candidates else ""


# ═══════════════════════════════════════════════
# 排版执行
# ═══════════════════════════════════════════════

async def _compose_article(
        article: ArticleOutputNode,
        agent: Any,
) -> CompositionNode:
    """对文章进行排版。"""
    context = article.full_text or ""

    result = await agent.ainvoke({"messages": [{"role": "user", "content": context}]})

    # 【修改】不再直接取 [-1]，使用鲁棒提取
    response_content = _extract_final_ai_content(result)

    # response_content = result["messages"][-1].content if result.get("messages") else ""

    return _extract_composition(response_content, article)


# ═══════════════════════════════════════════════
# 结果提取
# ═══════════════════════════════════════════════

def _extract_composition(response: str, original: ArticleOutputNode) -> CompositionNode:
    """
    从 LLM 响应中提取排版结果。

    prompt 要求 LLM 输出：
    {
        "formattedArticle": "HTML字符串",
        "formatSpec": {...},
        "compositionNotes": [...]
    }

    提取后 formatted_article 转为 dict：{"fullText": html, "title": title}
    """
    if not response:
        return _fallback(original)

    try:
        parsed = parse_json_response(response)
        if not isinstance(parsed, dict):
            return _fallback(original)

        # 提取标题（从原文）
        title = ""
        if original.parts and original.parts[0].title_alternatives:
            title = original.parts[0].title_alternatives[0]

        # 提取 formattedArticle（字符串 HTML 或 dict）
        html, extracted_title = _extract_html(parsed, title)

        # 提取 formatSpec
        format_spec = parsed.get("formatSpec") or parsed.get("format_spec", {})
        if not isinstance(format_spec, dict):
            format_spec = {}

        # 提取 compositionNotes
        notes = parsed.get("compositionNotes") or parsed.get("composition_notes", [])
        if not isinstance(notes, list):
            notes = [str(notes)] if notes else []

        return CompositionNode(
            formatted_article={
                "fullText": html,
                "title": extracted_title or title,
            },
            format_spec=format_spec,
            composition_notes=notes,
        )

    except Exception as e:
        logger.warning(f"[composition_node] 解析失败: {e}")
        return _fallback(original)


def _extract_html(parsed: dict, default_title: str) -> tuple[str, str]:
    """
    提取 HTML 文本和标题。

    支持格式：
    - formattedArticle: "HTML字符串"（prompt 要求的格式）
    - formattedArticle: {"fullText": "...", "title": "..."}
    - compositionNode.step3.html: "..."
    """
    raw = parsed.get("formattedArticle") or parsed.get("formatted_article", "")

    # 格式1: 字符串 HTML
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), default_title

    # 格式2: dict
    if isinstance(raw, dict):
        html = raw.get("fullText") or raw.get("full_text") or raw.get("html", "")
        title = raw.get("title") or default_title
        return html, title

    # 格式3: compositionNode.step3.html（兼容旧格式）
    comp_node = parsed.get("compositionNode") or parsed.get("composition_node", {})
    if isinstance(comp_node, dict):
        step3 = comp_node.get("step3", {})
        if isinstance(step3, dict):
            html = step3.get("html", "")
            if html:
                return html, default_title
        html = comp_node.get("html", "")
        if html:
            return html, default_title

    return "", default_title


def _fallback(original: ArticleOutputNode) -> CompositionNode:
    """排版失败时的兜底：返回原文 HTML。"""
    title = ""
    if original.parts and original.parts[0].title_alternatives:
        title = original.parts[0].title_alternatives[0]

    return CompositionNode(
        formatted_article={
            "fullText": original.full_text or "",
            "title": title,
        },
        format_spec={},
        composition_notes=["使用默认排版"],
    )


# ═══════════════════════════════════════════════
# 节点入口
# ═══════════════════════════════════════════════

def composition_node(state: GraphState) -> GraphState:
    """同步入口包装。"""
    return asyncio.run(composition_node_async(state))


async def composition_node_async(state: GraphState) -> GraphState:
    """composition_node 异步执行入口。"""
    article = state.get("article_output")
    if not article:
        state["error_message"] = "缺少 article_output"
        state["error_node"] = "composition_node"
        return state

    logger.info("[composition_node] 开始排版")

    base_tools = await get_base_tools()
    mcp_tools = await get_total_tools()
    agent = _create_composition_agent(list(base_tools) + list(mcp_tools))

    composition = await _compose_article(article, agent)

    state["composition_result"] = composition
    state["current_node"] = "composition_node"
    state["node_status"]["composition_node"] = "completed"

    mm = get_memory_manager()
    mm.add_short_term(
        f"composition_{datetime.now().isoformat()}",
        {"status": "completed"},
    )

    logger.info("[composition_node] 完成")
    return state
