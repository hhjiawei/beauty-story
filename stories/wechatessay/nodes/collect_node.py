"""
wechatessay.nodes.collect_node

节点2: collect_node — 收集信息节点

职责：
1. 基于 source_node 的分析结果，进行网络搜索补充
2. 从知乎高赞、今日头条、个人观点等渠道收集额外信息
3. 需要人工审核，若不满意则提出修改意见
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
from wechatessay.prompts.vx_prompt import COLLECT_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import ArticleSearchNode, GraphState
from wechatessay.tools.base_tools.base_tool import get_base_tools
from wechatessay.tools.mcp_tools.mcp_tool import get_total_tools
from wechatessay.utils.json_utils import parse_json_response



def _create_collect_agent(tools: list[BaseTool]) -> Any:
    """创建 collect_node 的 Deep Agent。"""
    backend = load_backend()

    mm = get_memory_manager()
    memory_context = mm.build_memory_context("热点调研")

    system_prompt = COLLECT_NODE_SYSTEM_PROMPT
    if memory_context:
        system_prompt = f"{memory_context}\n\n{system_prompt}"

    memory_files = []
    mem_file = Path(MEMORY_CONFIG["long_term_file"])
    if mem_file.exists():
        memory_files.append(str(mem_file))

    return create_deep_agent(
        model=MODEL_CONFIG.get("search_model", MODEL_CONFIG["default_model"]),
        tools=tools,
        system_prompt=system_prompt,
        backend=backend,
        memory=memory_files,
        name="info_collector",
    )


async def _execute_searches(
    total_analysis: dict,
    agent: Any,
) -> ArticleSearchNode:
    """
    执行多轮搜索，收集补充信息。
    """
    hotspot_title = total_analysis.get("hotspotTitle", "")
    core_demand = total_analysis.get("coreDemand", "")
    creation_ideas = total_analysis.get("creationIdeas", [])

    search_queries = [
        f"{hotspot_title} 最新进展",
        f"{hotspot_title} 知乎 高赞",
        f"{hotspot_title} 今日头条 观点",
        f"{hotspot_title} 争议",
        f"{hotspot_title} 网友评论",
    ]
    if creation_ideas:
        for idea in creation_ideas:
            search_queries.append(f"{hotspot_title} {idea}")

    search_context = json.dumps({
        "hotspot_title": hotspot_title,
        "core_demand": core_demand,
        "creation_ideas": creation_ideas,
        "search_queries": search_queries,
    }, ensure_ascii=False, indent=2)

    messages = [
        {
            "role": "user",
            "content": (
                f"基于以下热点分析结果，执行网络调研并补充信息。\n\n"
                f"已确定的热点信息：\n{search_context}\n\n"
                f"请依次执行搜索查询，收集补充信息，"
                f"最终以 JSON 格式输出 ArticleSearchNode 结构。"
                f"结果一定要ArticleSearchNode的JSON结构，不许落盘，不许擅自加其他内容，你输出的结果必须是ArticleSearchNode的JSON结构"
            ),
        }
    ]

    result = await agent.ainvoke({"messages": messages})
    response_content = result["messages"][-1].content if result.get("messages") else ""

    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict):
            search_data = parsed.get("search_result") or parsed
            search_node = ArticleSearchNode.model_validate(search_data)
            search_node.search_queries_used = search_queries
            search_node.searched_at = datetime.now().isoformat()
            return search_node
    except Exception as e:
        print(f"[collect_node] 解析搜索结果失败: {e}")

    return ArticleSearchNode(
        cause_process_result="",
        topic_angle="",
        topic_material="",
        controversial_points="",
        creation_inspiration="",
        search_queries_used=search_queries,
        searched_at=datetime.now().isoformat(),
    )


async def collect_node_async(state: GraphState) -> GraphState:
    """
    collect_node 异步执行入口。
    核心修复：使用 await agent.ainvoke() 而非 agent.invoke()，
    以支持 MCP 异步工具。
    """
    total_analysis = state.get("total_article_results")
    if not total_analysis:
        state["error_message"] = "缺少 total_article_results，请先执行 source_node"
        state["error_node"] = "collect_node"
        return state

    print(f"[collect_node] 开始收集信息: {total_analysis.hotspot_title}")

    # 1. 准备工具并创建 Agent
    base_tools =await get_base_tools()
    mcp_tools = await get_total_tools()
    total_tools = list(base_tools) + list(mcp_tools)

    agent = _create_collect_agent(total_tools)

    # 2. 执行搜索（await ainvoke）
    search_result = await _execute_searches(
        total_analysis.model_dump(by_alias=True), # by_alias=True 表示：序列化（dump）时，字段名使用 Field(alias=...) 中定义的别名，而不是 Python 类的属性名。
        agent,
    )

    # 3. 更新状态
    state["search_result"] = search_result
    state["current_node"] = "collect_node"
    state["node_status"]["collect_node"] = "waiting_human"

    # 4. 准备人工审核内容
    state["pending_human_review"] = {
        "node": "collect_node",
        "content": search_result.model_dump(by_alias=True),
        "instruction": "请检查搜索结果是否充分，是否覆盖了需要的角度。如需补充搜索，请提供搜索方向。",
    }

    # 5. 保存到短期记忆
    mm = get_memory_manager()
    mm.add_short_term(
        f"collect_{datetime.now().isoformat()}",
        {
            "hotspot_title": total_analysis.hotspot_title,
            "search_count": len(search_result.search_sources),
        },
    )

    print(f"[collect_node] 完成: 收集到 {len(search_result.search_sources)} 条来源")
    return state


def collect_node(state: GraphState) -> GraphState:
    """collect_node 同步入口包装。"""
    import asyncio
    return asyncio.run(collect_node_async(state))