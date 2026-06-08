"""
wechatessay.nodes.composition_node

节点6: composition_node — 排版节点

职责：
1. 对文章进行公众号风格排版
2. 设计视觉节奏和留白
3. 移动端适配
4. 需要人工审核
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from wechatessay.agents.backend import load_backend
from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.config import get_model_instance, BACKEND_CONFIG, MEMORY_CONFIG, MODEL_CONFIG
from wechatessay.prompts.vx_prompt import COMPOSITION_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import ArticleOutputNode, CompositionNode, FormatSpec, GraphState
from wechatessay.tools.base_tools.base_tool import get_base_tools
from wechatessay.tools.mcp_tools.mcp_tool import get_total_tools
from wechatessay.utils.json_utils import parse_json_response



def _create_composition_agent(tools: list[BaseTool]) -> Any:
    """创建 composition_node 的 Deep Agent。"""
    backend = load_backend()
    mm = get_memory_manager()
    memory_context = mm.build_memory_context("排版设计")

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
        name="composition_designer",
    )


async def _compose_article(
    article: ArticleOutputNode,
    agent: Any,
) -> CompositionNode:
    """对文章进行排版。"""
    context = article.full_text or ""

    messages = [
        {
            "role": "user",
            "content": (
                f"请对以下文章进行公众号风格排版设计。\n\n"
                f"{context}\n\n"
                f"请输出 JSON 格式："
                f'{{"compositionNode": {{"step3": {{"html": "排版后的HTML"}}, '
                f'"formatSpec": {{...}}, "compositionNotes": ["..."]}}}}'
            ),
        }
    ]

    result = await agent.ainvoke({"messages": messages})
    response_content = result["messages"][-1].content if result.get("messages") else ""

    return _extract_composition(response_content, article)


def _extract_composition(response_content: str, original: ArticleOutputNode) -> CompositionNode:
    """从 LLM 响应中提取排版结果。适配多种输出格式。"""
    if not response_content:
        return _fallback_composition(original)

    try:
        parsed = parse_json_response(response_content)
        if not isinstance(parsed, dict):
            return _fallback_composition(original)

        # 优先级1: compositionNode 结构
        comp_node = parsed.get("compositionNode") or parsed.get("composition_node")
        if isinstance(comp_node, dict):
            return _from_composition_node(comp_node, original)

        # 优先级2: 直接是 CompositionNode 格式
        if "formattedArticle" in parsed or "formatted_article" in parsed:
            return CompositionNode.model_validate(parsed)

        return _fallback_composition(original)

    except Exception as e:
        print(f"[composition_node] 解析排版结果失败: {e}")
        return _fallback_composition(original)


def _from_composition_node(comp_node: dict, original: ArticleOutputNode) -> CompositionNode:
    """从 compositionNode 结构中提取排版结果。"""
    # 提取 HTML
    html = ""
    step3 = comp_node.get("step3", {})
    if isinstance(step3, dict):
        html = step3.get("html", "")
    if not html:
        html = comp_node.get("html", "")

    # 提取 formatSpec（转换为 FormatSpec 对象，确保字段完整）
    raw_spec = comp_node.get("formatSpec") or comp_node.get("format_spec", {})
    if isinstance(raw_spec, dict):
        format_spec = FormatSpec(
            fontStyle=raw_spec.get("fontStyle", ""),
            paragraphSpacing=raw_spec.get("paragraphSpacing", ""),
            highlightStyle=raw_spec.get("highlightStyle", ""),
            imagePlacement=raw_spec.get("imagePlacement", []),
        )
    else:
        format_spec = FormatSpec()

    # 提取 compositionNotes
    notes = comp_node.get("compositionNotes") or comp_node.get("composition_notes", [])

    # 构建 formatted_article（保留元数据，替换全文为排版后的 HTML）
    formatted = original.model_copy(deep=True)
    if html:
        formatted.full_text = html
        if formatted.parts:
            formatted.parts[0].content = html

    return CompositionNode(
        formatted_article=formatted,
        format_spec=format_spec,
        composition_notes=notes if isinstance(notes, list) else [str(notes)],
        preview_suggestions=["检查排版效果"],
    )


def _fallback_composition(original: ArticleOutputNode) -> CompositionNode:
    """排版失败时的兜底。"""
    return CompositionNode(
        formatted_article=original,
        format_spec=FormatSpec(),
        composition_notes=["使用默认排版（解析失败）"],
        preview_suggestions=["检查排版效果"],
    )


async def composition_node_async(state: GraphState) -> GraphState:
    """
    composition_node 异步执行入口。
    核心修复：使用 await agent.ainvoke() 而非 agent.invoke()。
    """
    article = state.get("article_output")

    if not article:
        state["error_message"] = "缺少 article_output"
        state["error_node"] = "composition_node"
        return state

    print(f"[composition_node] 开始排版")

    base_tools = await get_base_tools()
    mcp_tools = await get_total_tools()
    total_tools = list(base_tools) + list(mcp_tools)

    agent = _create_composition_agent(total_tools)

    composition = await _compose_article(article, agent)

    state["composition_result"] = composition
    state["current_node"] = "composition_node"
    state["node_status"]["composition_node"] = "completed"  # [TEST] 自动通过


    mm = get_memory_manager()
    mm.add_short_term(
        f"composition_{datetime.now().isoformat()}",
        {"status": "completed"},
    )

    print(f"[composition_node] 完成")
    return state


def composition_node(state: GraphState) -> GraphState:
    """composition_node 同步入口包装。"""
    import asyncio
    return asyncio.run(composition_node_async(state))