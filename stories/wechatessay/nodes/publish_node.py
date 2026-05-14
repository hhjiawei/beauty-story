"""
wechatessay.nodes.publish_node

节点8: publish_node — 发布节点

职责：
1. 生成微信公众号 HTML 格式
2. 配置发布参数
3. 记录发布日志
4. 支持定时发布
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.config import BACKEND_CONFIG, MEMORY_CONFIG, MODEL_CONFIG, PUBLISH_CONFIG
from wechatessay.prompts.vx_prompt import PUBLISH_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import CompositionNode, GraphState, PublishNode
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


def _create_publish_agent(tools: List[BaseTool]) -> Any:
    """创建 publish_node 的 Deep Agent。"""
    backend = _load_backend()
    mm = get_memory_manager()
    memory_context = mm.build_memory_context("文章发布")

    system_prompt = PUBLISH_NODE_SYSTEM_PROMPT
    if memory_context:
        system_prompt = f"{memory_context}\n\n{system_prompt}"

    memory_files = []
    mem_file = Path(MEMORY_CONFIG["long_term_file"])
    if mem_file.exists():
        memory_files.append(str(mem_file))

    return create_deep_agent(
        model=MODEL_CONFIG.get("review_model", MODEL_CONFIG["default_model"]),
        tools=tools,
        system_prompt=system_prompt,
        backend=backend,
        memory=memory_files,
        name="publisher",
    )


def _prepare_publish(
    composition: Dict[str, Any],
    legality: Dict[str, Any],
    agent: Any,
) -> PublishNode:
    """准备发布。"""
    context = json.dumps({
        "composition": composition,
        "legality": legality,
        "publish_config": PUBLISH_CONFIG,
    }, ensure_ascii=False, indent=2)

    messages = [
        {
            "role": "user",
            "content": (
                f"请将以下排版后的文章转化为微信公众号可发布的 HTML 格式。\n\n"
                f"{context}\n\n"
                f"请以 JSON 格式输出 PublishNode 结构，"
                f"包含完整的 HTML、发布配置和日志。"
            ),
        }
    ]

    result = agent.invoke({"messages": messages})
    response_content = result["messages"][-1].content if result.get("messages") else ""

    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict):
            pub_data = parsed.get("publish_result") or parsed
            return PublishNode.model_validate(pub_data)
    except Exception as e:
        print(f"[publish_node] 解析发布结果失败: {e}")

    # fallback: 生成基本 HTML
    article_text = composition.get("formatted_article", {}).get("fullText", "")
    html = f"""
    <html>
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
                  font-size:15px;line-height:1.75;color:#333;padding:16px;">
        {article_text}
    </body>
    </html>
    """

    return PublishNode(
        publish_config={
            "platform": "wechat",
            "tags": [],
            "isOriginal": True,
        },
        publish_status="draft",
        final_article_html=html,
        publish_log=[f"[{datetime.now().isoformat()}] 文章进入发布队列"],
    )


async def publish_node_async(state: GraphState) -> GraphState:
    """publish_node 异步执行入口。"""
    composition = state.get("composition_result")
    legality = state.get("legality_result")

    if not composition:
        state["error_message"] = "缺少 composition_result"
        state["error_node"] = "publish_node"
        return state

    print(f"[publish_node] 开始准备发布")

    base_tools = get_base_tools()
    mcp_tools = await get_total_tools()
    total_tools = list(base_tools) + list(mcp_tools)

    agent = _create_publish_agent(total_tools)

    publish = _prepare_publish(
        composition.model_dump(by_alias=True),
        legality.model_dump(by_alias=True) if legality else {},
        agent,
    )

    state["publish_result"] = publish
    state["current_node"] = "publish_node"
    state["node_status"]["publish_node"] = "completed"

    mm = get_memory_manager()
    mm.add_long_term(
        content=f"发布文章: {publish.publish_config.get('tags', [])}",
        mtype="publish_record",
        tags=["publish"],
    )

    print(f"[publish_node] 完成: 状态={publish.publish_status}")
    return state


def publish_node(state: GraphState) -> GraphState:
    """publish_node 同步入口。"""
    import asyncio
    return asyncio.run(publish_node_async(state))
