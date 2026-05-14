"""
wechatessay.nodes.legality_node

节点7: legality_node — 合规性检测节点

职责：
1. 错别字/标点检查
2. AI 感检测
3. 敏感内容检查
4. 事实性检查
5. 文风一致性检查
6. 自动修正（如果可能）
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.config import BACKEND_CONFIG, LEGALITY_CONFIG, MEMORY_CONFIG, MODEL_CONFIG
from wechatessay.prompts.vx_prompt import LEGALITY_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import (
    ArticleOutputNode,
    CompositionNode,
    GraphState,
    LegalityCheckResult,
)
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


def _create_legality_agent(tools: List[BaseTool]) -> Any:
    """创建 legality_node 的 Deep Agent。"""
    backend = _load_backend()
    mm = get_memory_manager()
    memory_context = mm.build_memory_context("合规检查")

    system_prompt = LEGALITY_NODE_SYSTEM_PROMPT
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
        name="legality_checker",
    )


def _check_article(
    article: Dict[str, Any],
    target_style: str,
    agent: Any,
) -> LegalityCheckResult:
    """执行合规检查。"""
    context = json.dumps({
        "article": article,
        "target_style": target_style,
        "sensitive_keywords": LEGALITY_CONFIG["sensitive_keywords"],
        "ai_markers": LEGALITY_CONFIG["ai_markers"],
        "max_ai_score": LEGALITY_CONFIG["max_ai_score"],
    }, ensure_ascii=False, indent=2)

    messages = [
        {
            "role": "user",
            "content": (
                f"请对以下文章进行全面的合规性检查。\n\n"
                f"{context}\n\n"
                f"请以 JSON 格式输出 LegalityCheckResult 结构，"
                f"包含所有检查维度和修改建议。"
            ),
        }
    ]

    result = agent.invoke({"messages": messages})
    response_content = result["messages"][-1].content if result.get("messages") else ""

    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict):
            check_data = parsed.get("legality_result") or parsed
            return LegalityCheckResult.model_validate(check_data)
    except Exception as e:
        print(f"[legality_node] 解析检查结果失败: {e}")

    return LegalityCheckResult(
        is_passed=False,
        overall_score=0,
        ai_flavor_score=1.0,
        readability_score=0.0,
        correction_suggestions=["检查失败，请人工审核"],
    )


async def legality_node_async(state: GraphState) -> GraphState:
    """legality_node 异步执行入口。"""
    composition = state.get("composition_result")

    if not composition:
        state["error_message"] = "缺少 composition_result"
        state["error_node"] = "legality_node"
        return state

    print(f"[legality_node] 开始合规检查")

    base_tools = get_base_tools()
    mcp_tools = await get_total_tools()
    total_tools = list(base_tools) + list(mcp_tools)

    agent = _create_legality_agent(total_tools)

    blueprint = state.get("blueprint_result")
    target_style = blueprint.writing_style.final_style if blueprint else "口语化大白话"

    legality = _check_article(
        composition.model_dump(by_alias=True),
        target_style,
        agent,
    )

    state["legality_result"] = legality
    state["current_node"] = "legality_node"

    # 判断是否通过
    if legality.is_passed and legality.ai_flavor_score <= LEGALITY_CONFIG["max_ai_score"]:
        state["node_status"]["legality_node"] = "completed"
        print(f"[legality_node] 通过检查: 得分={legality.overall_score}")
    else:
        state["node_status"]["legality_node"] = "waiting_human"
        state["pending_human_review"] = {
            "node": "legality_node",
            "content": legality.model_dump(by_alias=True),
            "instruction": (
                f"合规检查发现问题，AI感得分={legality.ai_flavor_score:.2f}，"
                f"总分={legality.overall_score}。请检查问题列表并决定是否需要修改。"
            ),
        }
        print(f"[legality_node] 检查未通过: 得分={legality.overall_score}")

    mm = get_memory_manager()
    mm.add_short_term(
        f"legality_{datetime.now().isoformat()}",
        {"passed": legality.is_passed, "score": legality.overall_score},
    )

    return state


def legality_node(state: GraphState) -> GraphState:
    """legality_node 同步入口。"""
    import asyncio
    return asyncio.run(legality_node_async(state))
