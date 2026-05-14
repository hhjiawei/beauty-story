"""
wechatessay.nodes.analyse_node

节点3: analyse_node — 分析节点

职责：
1. 整合 source_node 和 collect_node 的内容
2. 分析可以从哪些角度写该事件
3. 判定可融合、可对立、有争议、引发深思的角度
4. 确定写作风格
5. 需要人工审核

依赖：
- Deep Agent (create_deep_agent)
- ArticleBlueprintNode 状态模型
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
from wechatessay.prompts.vx_prompt import ANALYSE_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import ArticleBlueprintNode, GraphState
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


def _create_analyse_agent(tools: List[BaseTool]) -> Any:
    """
    创建 analyse_node 的 Deep Agent。
    """
    backend = _load_backend()

    mm = get_memory_manager()
    memory_context = mm.build_memory_context("写作分析")

    system_prompt = ANALYSE_NODE_SYSTEM_PROMPT
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
        name="writing_analyzer",
    )


def _analyze_writing(
    total_analysis: Dict[str, Any],
    search_result: Dict[str, Any],
    agent: Any,
) -> ArticleBlueprintNode:
    """
    执行写作角度分析。
    """
    context = json.dumps({
        "article_analysis": total_analysis,
        "search_result": search_result,
    }, ensure_ascii=False, indent=2)

    messages = [
        {
            "role": "user",
            "content": (
                f"基于以下文章内容分析和网络调研结果，"
                f"进行全面的写作策略分析。\n\n"
                f"{context}\n\n"
                f"请以 JSON 格式输出 ArticleBlueprintNode 结构。"
            ),
        }
    ]

    result = agent.invoke({"messages": messages})
    response_content = result["messages"][-1].content if result.get("messages") else ""

    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict):
            blueprint_data = parsed.get("blueprint_result") or parsed
            return ArticleBlueprintNode.model_validate(blueprint_data)
    except Exception as e:
        print(f"[analyse_node] 解析分析结果失败: {e}")

    # 返回空结构
    return ArticleBlueprintNode(
        writing_analysis={"commonAngles": [], "mergeableAngles": [], "opposingAngles": [],
                          "controversialAngles": [], "thoughtProvokingAngles": []},
        writing_style={"finalStyle": "", "styleReason": "", "styleExample": ""},
        writing_template={"title": "", "subtitle": "", "introduction": "", "conclusion": ""},
        writing_plan={"coreIdea": "", "leadIn": ""},
        target_audience_analysis="",
        emotional_arc_design="",
        hook_strategy=[],
        interactive_design="",
        viral_prediction="",
    )


async def analyse_node_async(state: GraphState) -> GraphState:
    """
    analyse_node 异步执行入口。
    """
    total_analysis = state.get("total_article_results")
    search_result = state.get("search_result")

    if not total_analysis:
        state["error_message"] = "缺少 total_article_results"
        state["error_node"] = "analyse_node"
        return state

    print(f"[analyse_node] 开始写作分析: {total_analysis.hotspot_title}")

    # 1. 准备工具
    base_tools = get_base_tools()
    mcp_tools = await get_total_tools()
    total_tools = list(base_tools) + list(mcp_tools)

    agent = _create_analyse_agent(total_tools)

    # 2. 执行分析
    blueprint = _analyze_writing(
        total_analysis.model_dump(by_alias=True),
        search_result.model_dump(by_alias=True) if search_result else {},
        agent,
    )

    # 3. 更新状态
    state["blueprint_result"] = blueprint
    state["current_node"] = "analyse_node"
    state["node_status"]["analyse_node"] = "waiting_human"

    # 4. 准备人工审核
    state["pending_human_review"] = {
        "node": "analyse_node",
        "content": blueprint.model_dump(by_alias=True),
        "instruction": (
            "请检查写作角度分析是否全面，风格定位是否准确。"
            "如需调整，请提供具体修改方向。"
        ),
    }

    # 5. 保存记忆
    mm = get_memory_manager()
    mm.add_short_term(
        f"analyse_{datetime.now().isoformat()}",
        {"style": blueprint.writing_style.final_style, "title": blueprint.writing_template.title},
    )

    print(f"[analyse_node] 完成: 风格={blueprint.writing_style.final_style}")
    return state


def analyse_node(state: GraphState) -> GraphState:
    """analyse_node 同步入口。"""
    import asyncio
    return asyncio.run(analyse_node_async(state))
