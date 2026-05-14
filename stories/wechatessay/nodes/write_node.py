"""
wechatessay.nodes.write_node

节点5: write_node — 写作节点

职责：
1. 严格按照大纲逐段落生成文章
2. 确保风格、逻辑、情绪、修辞符合大纲要求
3. 自然融入金句
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
from wechatessay.prompts.vx_prompt import WRITE_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import ArticleOutputNode, GraphState
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


def _create_write_agent(tools: List[BaseTool]) -> Any:
    """创建 write_node 的 Deep Agent。"""
    backend = _load_backend()
    mm = get_memory_manager()
    memory_context = mm.build_memory_context("文章写作")

    system_prompt = WRITE_NODE_SYSTEM_PROMPT
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
        name="article_writer",
    )


def _write_article(
    plot: Dict[str, Any],
    blueprint: Dict[str, Any],
    agent: Any,
) -> ArticleOutputNode:
    """按照大纲写作文章。"""
    context = json.dumps({
        "plot": plot,
        "blueprint": blueprint,
    }, ensure_ascii=False, indent=2)

    messages = [
        {
            "role": "user",
            "content": (
                f"请严格按照以下大纲和写作蓝图，逐段落生成公众号文章。\n\n"
                f"{context}\n\n"
                f"请以 JSON 格式输出 ArticleOutputNode 结构，"
                f"包含完整的文章分段、金句标注、转发语等。"
            ),
        }
    ]

    result = agent.invoke({"messages": messages})
    response_content = result["messages"][-1].content if result.get("messages") else ""

    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict):
            article_data = parsed.get("article_output") or parsed
            article = ArticleOutputNode.model_validate(article_data)
            # 拼接完整文本
            article.full_text = "\n\n".join(
                part.content for part in article.parts
            )
            article.metadata = {
                "totalWordCount": len(article.full_text),
                "readingTime": f"{max(1, len(article.full_text) // 300)}分钟",
                "generatedAt": datetime.now().isoformat(),
            }
            return article
    except Exception as e:
        print(f"[write_node] 解析文章失败: {e}")

    return ArticleOutputNode(parts=[], full_text="")


async def write_node_async(state: GraphState) -> GraphState:
    """write_node 异步执行入口。"""
    plot = state.get("plot_result")
    blueprint = state.get("blueprint_result")

    if not plot:
        state["error_message"] = "缺少 plot_result"
        state["error_node"] = "write_node"
        return state

    print(f"[write_node] 开始写作: {plot.writing_context.article_title}")

    base_tools = get_base_tools()
    mcp_tools = await get_total_tools()
    total_tools = list(base_tools) + list(mcp_tools)

    agent = _create_write_agent(total_tools)

    article = _write_article(
        plot.model_dump(by_alias=True),
        blueprint.model_dump(by_alias=True) if blueprint else {},
        agent,
    )

    state["article_output"] = article
    state["current_node"] = "write_node"
    state["node_status"]["write_node"] = "waiting_human"

    state["pending_human_review"] = {
        "node": "write_node",
        "content": article.model_dump(by_alias=True),
        "instruction": "请检查文章内容是否符合大纲要求，风格是否一致，金句是否自然。",
    }

    mm = get_memory_manager()
    mm.add_short_term(
        f"write_{datetime.now().isoformat()}",
        {"word_count": article.metadata.get("totalWordCount", 0)},
    )

    print(f"[write_node] 完成: {article.metadata.get('totalWordCount', 0)} 字")
    return state


def write_node(state: GraphState) -> GraphState:
    """write_node 同步入口。"""
    import asyncio
    return asyncio.run(write_node_async(state))
