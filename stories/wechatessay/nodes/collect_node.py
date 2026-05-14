"""
wechatessay.nodes.collect_node

节点2: collect_node — 收集信息节点

职责：
1. 基于 source_node 的分析结果，进行网络搜索补充
2. 从知乎高赞、今日头条、个人观点等渠道收集额外信息
3. 需要人工审核，若不满意则提出修改意见

依赖：
- Deep Agent (create_deep_agent)
- search_zhihu, search_toutiao, search_related_topics 等搜索工具
- ArticleSearchNode 状态模型
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.config import BACKEND_CONFIG, MEMORY_CONFIG, MODEL_CONFIG
from wechatessay.prompts.vx_prompt import COLLECT_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import ArticleSearchNode, GraphState
from wechatessay.tools.base_tools.base_tool import get_base_tools
from wechatessay.tools.mcp_tools.mcp_tool import get_total_tools
from wechatessay.utils.json_utils import parse_json_response


def _load_backend():
    """加载 Deep Agents backend 配置。"""
    from deepagents.backends import CompositeBackend, FilesystemBackend
    root = Path(BACKEND_CONFIG["root_dir"])
    return CompositeBackend(
        default=FilesystemBackend(root_dir=root, virtual_mode=BACKEND_CONFIG["virtual_mode"]),
        routes={
            "/memories/": FilesystemBackend(
                root_dir=Path(BACKEND_CONFIG["routes"]["/memories/"]["root_dir"]),
                virtual_mode=True,
            ),
            "/skills/": FilesystemBackend(
                root_dir=Path(BACKEND_CONFIG["routes"]["/skills/"]["root_dir"]),
                virtual_mode=True,
            ),
            "/workspaces/": FilesystemBackend(
                root_dir=Path(BACKEND_CONFIG["routes"]["/workspaces/"]["root_dir"]),
                virtual_mode=True,
            ),
        },
    )


def _create_collect_agent(tools: List[BaseTool]) -> Any:
    """
    创建 collect_node 的 Deep Agent。

    配置：
    - model: 搜索专用模型
    - tools: 包含多个搜索工具
    - system_prompt: 信息收集专用提示词
    - backend: CompositeBackend
    """
    backend = _load_backend()

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


def _execute_searches(
    total_analysis: Dict[str, Any],
    agent: Any,
) -> ArticleSearchNode:
    """
    执行多轮搜索，收集补充信息。

    搜索策略：
    1. 基于热点标题搜索最新进展
    2. 搜索知乎高赞回答
    3. 搜索今日头条观点
    4. 搜索争议和不同观点
    """
    hotspot_title = total_analysis.get("hotspot_title", "")
    core_demand = total_analysis.get("core_demand", "")
    creation_ideas = total_analysis.get("creation_ideas", [])

    # 构建多轮搜索查询
    search_queries = [
        f"{hotspot_title} 最新进展",
        f"{hotspot_title} 知乎 高赞",
        f"{hotspot_title} 今日头条 观点",
        f"{hotspot_title} 争议",
        f"{hotspot_title} 网友评论",
    ]
    if creation_ideas:
        for idea in creation_ideas[:2]:
            search_queries.append(f"{hotspot_title} {idea}")

    # 构建消息
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
            ),
        }
    ]

    # 调用 Agent
    result = agent.invoke({"messages": messages})
    response_content = result["messages"][-1].content if result.get("messages") else ""

    # 解析 JSON
    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict):
            # 尝试多种可能的键名
            search_data = parsed.get("search_result") or parsed
            search_node = ArticleSearchNode.model_validate(search_data)
            search_node.search_queries_used = search_queries
            search_node.searched_at = datetime.now().isoformat()
            return search_node
    except Exception as e:
        print(f"[collect_node] 解析搜索结果失败: {e}")

    # 返回空结构
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

    流程：
    1. 获取 total_article_results
    2. 构建搜索查询
    3. 调用 Deep Agent 执行多轮搜索
    4. 整合搜索结果
    5. 设置人工审核标记
    """
    total_analysis = state.get("total_article_results")
    if not total_analysis:
        state["error_message"] = "缺少 total_article_results，请先执行 source_node"
        state["error_node"] = "collect_node"
        return state

    print(f"[collect_node] 开始收集信息: {total_analysis.hotspot_title}")

    # 1. 准备工具并创建 Agent
    base_tools = get_base_tools()
    mcp_tools = await get_total_tools()
    total_tools = list(base_tools) + list(mcp_tools)

    agent = _create_collect_agent(total_tools)

    # 2. 执行搜索
    search_result = _execute_searches(
        total_analysis.model_dump(by_alias=True),
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
    """collect_node 同步入口。"""
    import asyncio
    return asyncio.run(collect_node_async(state))
