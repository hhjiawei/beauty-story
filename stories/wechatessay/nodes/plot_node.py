"""
wechatessay.nodes.plot_node

节点4: plot_node — 大纲节点

职责：
1. 整合前面所有节点的内容
2. 生成详细的公众号文章大纲
3. 每段包含逻辑、情绪、修辞、金句等详细指令
4. 需要人工审核
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
from wechatessay.prompts.vx_prompt import PLOT_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import ArticlePlotNode, GraphState
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


def _create_plot_agent(tools: List[BaseTool]) -> Any:
    """创建 plot_node 的 Deep Agent。"""
    backend = _load_backend()
    mm = get_memory_manager()
    memory_context = mm.build_memory_context("大纲设计")

    system_prompt = PLOT_NODE_SYSTEM_PROMPT
    if memory_context:
        system_prompt = f"{memory_context}\n\n{system_prompt}"

    memory_files = []
    mem_file = Path(MEMORY_CONFIG["long_term_file"])
    if mem_file.exists():
        memory_files.append(str(mem_file))

    return create_deep_agent(
        model=MODEL_CONFIG.get("writing_model", MODEL_CONFIG["default_model"]),
        tools=tools,
        system_prompt=system_prompt,
        backend=backend,
        memory=memory_files,
        name="plot_designer",
    )


def _generate_plot(
    blueprint: Dict[str, Any],
    search_result: Dict[str, Any],
    agent: Any,
) -> ArticlePlotNode:
    """生成文章大纲。"""
    context = json.dumps({
        "blueprint": blueprint,
        "search_result": search_result,
    }, ensure_ascii=False, indent=2)

    messages = [
        {
            "role": "user",
            "content": (
                f"基于以下写作蓝图和搜索结果，设计详细的公众号文章大纲。\n\n"
                f"{context}\n\n"
                f"请严格按 JSON 格式输出 ArticlePlotNode 结构，"
                f"包含完整的段落级写作指令。"
            ),
        }
    ]

    result = agent.invoke({"messages": messages})
    response_content = result["messages"][-1].content if result.get("messages") else ""

    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict):
            plot_data = parsed.get("plot_result") or parsed
            return ArticlePlotNode.model_validate(plot_data)
    except Exception as e:
        print(f"[plot_node] 解析大纲失败: {e}")

    return ArticlePlotNode(
        writing_context={"articleTitle": "", "coreIdea": "", "targetAudience": "",
                         "globalStyle": {"tone": "", "languageRequirement": ""}},
        content_segments=[],
        global_checklist=[],
    )


async def plot_node_async(state: GraphState) -> GraphState:
    """plot_node 异步执行入口。"""
    blueprint = state.get("blueprint_result")
    search_result = state.get("search_result")

    if not blueprint:
        state["error_message"] = "缺少 blueprint_result"
        state["error_node"] = "plot_node"
        return state

    print(f"[plot_node] 开始生成大纲")

    base_tools = get_base_tools()
    mcp_tools = await get_total_tools()
    total_tools = list(base_tools) + list(mcp_tools)

    agent = _create_plot_agent(total_tools)

    plot_result = _generate_plot(
        blueprint.model_dump(by_alias=True),
        search_result.model_dump(by_alias=True) if search_result else {},
        agent,
    )

    state["plot_result"] = plot_result
    state["current_node"] = "plot_node"
    state["node_status"]["plot_node"] = "waiting_human"

    state["pending_human_review"] = {
        "node": "plot_node",
        "content": plot_result.model_dump(by_alias=True),
        "instruction": "请检查大纲结构是否合理，段落逻辑是否清晰，金句位置是否恰当。",
    }

    mm = get_memory_manager()
    mm.add_short_term(
        f"plot_{datetime.now().isoformat()}",
        {"title": plot_result.writing_context.article_title, "segments": len(plot_result.content_segments)},
    )

    print(f"[plot_node] 完成: {len(plot_result.content_segments)} 段")
    return state


def plot_node(state: GraphState) -> GraphState:
    """plot_node 同步入口。"""
    import asyncio
    return asyncio.run(plot_node_async(state))
