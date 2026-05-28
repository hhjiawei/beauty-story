"""
wechatessay.nodes.write_node

节点5: write_node — 一次性全文写作节点

职责：
1. 接收 plot_result（大纲）、blueprint_result（蓝图）、search_result（素材）
2. 调用 Deep Agent 一次性生成完整文章（ArticleOutputNode）
3. 支持带上评审反馈（revision_notes）进行修改
4. 输出 ArticleOutputNode 到 state["article_output"]

依赖：
- Deep Agent (create_deep_agent)
- ArticlePlotNode, ArticleBlueprintNode, ArticleSearchNode 状态
- FULL_WRITE_SYSTEM_PROMPT
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from wechatessay.agents.backend import load_backend
from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.config import (
    MEMORY_CONFIG,
    MODEL_CONFIG,
    REVIEWERS_CONFIG,
)
from wechatessay.prompts.vx_prompt import FULL_WRITE_SYSTEM_PROMPT
from wechatessay.states.vx_state import (
    ArticleOutputNode,
    ArticlePlotNode,
    GraphState,
)
from wechatessay.tools.base_tools.base_tool import get_base_tools
from wechatessay.tools.mcp_tools.mcp_tool import get_total_tools
from wechatessay.utils.json_utils import parse_json_response

import logging

logger = logging.getLogger(__name__)


def _create_writer_agent(tools: List[BaseTool]) -> Any:
    """创建全文写作的 Deep Agent。"""
    backend = load_backend()
    mm = get_memory_manager()
    memory_context = mm.build_memory_context("全文写作")

    system_prompt = "你是一名顶级公众号主笔，擅长一次性完成高质量全文写作。"
    if memory_context:
        system_prompt = f"{memory_context}\n\n{system_prompt}"

    memory_files = []
    mem_file = Path(MEMORY_CONFIG["long_term_file"])
    if mem_file.exists():
        memory_files.append(str(mem_file))

    return create_deep_agent(
        model=MODEL_CONFIG.get("writing_model", MODEL_CONFIG["default_model"]),
        # tools=tools,
        system_prompt=system_prompt,
        backend=backend,
        memory=memory_files,
        name="full_writer",
    )


def _format_context(state: GraphState) -> str:
    """组装写作所需的完整上下文。"""
    plot = state["plot_result"]
    blueprint = state.get("blueprint_result")
    search = state.get("search_result")

    ctx = plot.writing_context
    gs = ctx.global_style

    # 1. 全局写作上下文
    global_ctx = f"""【文章标题】{ctx.article_title}
【核心观点】{ctx.core_idea}
【目标受众】{ctx.target_audience}
【语调】{gs.tone}
【语言约束】{gs.language_requirement}
【风格样板句】{json.dumps(gs.example_sentences, ensure_ascii=False)}
"""

    # 2. 大纲
    segments_info = []
    for i, seg in enumerate(plot.content_segments):
        gs_req = seg.gold_sentence_requirement
        wc = seg.word_count_range
        segments_info.append(
            f"\n--- 第{i + 1}段 ---\n"
            f"类型: {seg.segment_type} | 小标题: {seg.section_title or '无'}\n"
            f"核心逻辑: {seg.core_logic}\n"
            f"必须包含: {json.dumps(seg.key_information, ensure_ascii=False)}\n"
            f"情绪目标: {seg.emotional_objective}\n"
            f"修辞手法: {seg.rhetorical_device}\n"
            f"金句预留: 位置={gs_req.position}, 主题={gs_req.theme}\n"
            f"字数范围: {wc.min}-{wc.max}字\n"
            f"素材来源: {json.dumps(seg.material_sources, ensure_ascii=False) or '无'}\n"
            f"向下过渡: {seg.transition_to_next or '无'}"
        )
    plot_ctx = "【大纲】\n" + "\n".join(segments_info)

    # 3. 蓝图
    blueprint_ctx = "【蓝图】暂无"
    if blueprint:
        plan = blueprint.writing_plan
        blueprint_ctx = f"""【核心创作思路】{plan.core_idea}
【引子设计】{plan.lead_in}
【文章线索】{json.dumps(plan.clues, ensure_ascii=False)}
【情绪曲线设计】{blueprint.emotional_arc_design}
【钩子策略】{json.dumps(blueprint.hook_strategy, ensure_ascii=False)}
【互动设计】{blueprint.interactive_design}
【写作方向】{json.dumps(plan.writing_direction, ensure_ascii=False)}
【风险提示】{json.dumps(plan.risk_notes, ensure_ascii=False)}
"""

    # 4. 搜索素材
    search_ctx = "【搜索素材】暂无"
    if search:
        parts = ["【搜索素材 — 可供引用的内容】"]
        for s in search.search_sources[:8]:
            parts.append(f"  - [{s.platform}] {s.title} (可信度:{s.credibility_score}/5)\n    {s.content_summary[:150]}...")
        if search.expert_quotes:
            parts.append(f"专家观点: {json.dumps(search.expert_quotes[:5], ensure_ascii=False)}")
        if search.data_supplements:
            parts.append(f"数据补充: {json.dumps(search.data_supplements[:5], ensure_ascii=False)}")
        if search.related_cases:
            parts.append(f"同类案例: {json.dumps(search.related_cases[:3], ensure_ascii=False)}")
        if search.legal_policy_references:
            parts.append(f"法规引用: {json.dumps(search.legal_policy_references[:3], ensure_ascii=False)}")
        search_ctx = "\n".join(parts)

    return f"{global_ctx}\n{plot_ctx}\n{blueprint_ctx}\n{search_ctx}"


async def _generate_article(state: GraphState, agent: Any) -> ArticleOutputNode:
    """调用 Deep Agent 一次性生成完整文章。"""
    context = _format_context(state)
    revision = state.get("revision_notes")
    revision_count = state.get("revision_count", 0)

    user_prompt_parts = ["基于以下信息，一次性生成完整的公众号文章全文。\n\n", context]

    # 如果有评审反馈，追加修改要求
    if revision and revision_count > 0:
        user_prompt_parts.append(
            f"\n\n【第{revision_count}轮修改要求】\n"
            f"以下是评审反馈，请针对这些问题进行修改，保留原有优点：\n"
            f"{revision}\n\n"
            f"请输出修改后的完整文章 JSON（ArticleOutputNode 结构），"
            f"不要只输出修改部分，要输出完整文章。"
        )

    user_prompt_parts.append(
        "\n\n请按 ArticleOutputNode 的 JSON 结构输出完整文章，"
        "不要输出任何其他描述文字。"
    )

    messages = [
        {"role": "system", "content": FULL_WRITE_SYSTEM_PROMPT},
        {"role": "user", "content": "".join(user_prompt_parts)},
    ]

    result = await agent.ainvoke({"messages": messages})
    response_content = result["messages"][-1].content if result.get("messages") else ""

    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict) and "parts" in parsed:
            return ArticleOutputNode.model_validate(parsed)
    except Exception as e:
        logger.warning(f"解析文章失败: {e}")

    # Fallback：返回结构化的错误占位
    return ArticleOutputNode(
        parts=[{
            "partIndex": 1,
            "titleAlternatives": ["文章生成失败"],
            "content": response_content if response_content else "（生成失败，请检查日志）",
            "goldenSentences": [],
            "shareTexts": [],
            "readingTime": "1分钟",
            "rhythm": "生成失败",
        }],
        fullText=response_content or "",
        metadata={
            "totalWordCount": len(response_content) if response_content else 0,
            "readingTime": "1分钟",
            "generatedAt": datetime.now().isoformat(),
        },
    )


def write_node(state: GraphState) -> GraphState:
    """write_node 同步入口包装。"""
    import asyncio
    return asyncio.run(write_node_async(state))


async def write_node_async(state: GraphState) -> GraphState:
    """
    一次性全文写作（支持多轮修改）。

    流程：
    1. 首次进入：生成完整文章
    2. 评审后修改：根据 revision_notes 修改文章
    """
    plot = state.get("plot_result")
    if not plot:
        state["error_message"] = "缺少 plot_result"
        state["error_node"] = "write_node"
        return state

    revision_count = state.get("revision_count", 0)
    revision = state.get("revision_notes")

    if revision_count == 0:
        logger.info(f"[write_node] 开始生成完整文章: {plot.writing_context.article_title}")
    else:
        logger.info(f"[write_node] 第{revision_count}轮修改，根据评审反馈调整...")

    # 准备工具 + Agent
    base_tools = await get_base_tools()
    mcp_tools = await get_total_tools()
    total_tools = list(base_tools) + list(mcp_tools)
    agent = _create_writer_agent(total_tools)

    # 生成文章
    article = await _generate_article(state, agent)

    state["article_output"] = article
    state["current_node"] = "write_node"
    state["node_status"]["write_node"] = "completed"

    word_count = article.metadata.get("totalWordCount", 0)
    if revision_count == 0:
        logger.info(f"[write_node] 文章生成完成（{word_count}字）→ 进入评审")
    else:
        logger.info(f"[write_node] 第{revision_count}轮修改完成（{word_count}字）→ 再次评审")

    return state