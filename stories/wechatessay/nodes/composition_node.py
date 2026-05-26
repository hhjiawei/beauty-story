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
from wechatessay.config import BACKEND_CONFIG, MEMORY_CONFIG, MODEL_CONFIG
from wechatessay.prompts.vx_prompt import COMPOSITION_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import ArticleOutputNode, CompositionNode, GraphState
from wechatessay.tools.base_tools.base_tool import get_base_tools
from wechatessay.tools.mcp_tools.mcp_tool import get_total_tools
from wechatessay.utils.json_utils import parse_json_response

import logging
logger = logging.getLogger(__name__)

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
        model=MODEL_CONFIG.get("analysis_model", MODEL_CONFIG["default_model"]),
        tools=tools,
        system_prompt=system_prompt,
        backend=backend,
        memory=memory_files,
        name="composition_designer",
    )


async def _compose_article(
    article: dict,
    agent: Any,
) -> CompositionNode:
    """对文章进行排版。"""
    context = json.dumps({"article": article}, ensure_ascii=False, indent=2)

    messages = [
        {
            "role": "user",
            "content": (
                f"请对以下文章进行公众号风格排版设计。\n\n"
                f"{context}\n\n"
                f"请以 JSON 格式输出 CompositionNode 结构。"
                f"结果一定要CompositionNode的JSON结构，不许落盘，不许擅自加描述、总结等其他内容，你输出的结果只有CompositionNode的JSON结构"
            ),
        }
    ]

    result = await agent.ainvoke({"messages": messages})
    response_content = result["messages"][-1].content if result.get("messages") else ""

    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict):
            comp_data = parsed.get("composition_result") or parsed
            return CompositionNode.model_validate(comp_data)
    except Exception as e:
        print(f"[composition_node] 解析排版结果失败: {e}")

    original = ArticleOutputNode.model_validate(article)
    return CompositionNode(
        formatted_article=original,
        format_spec={"fontStyle": "", "paragraphSpacing": "", "highlightStyle": "", "imagePlacement": []},
        composition_notes=["使用默认排版"],
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

    composition = await _compose_article(article.model_dump(by_alias=True), agent)

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