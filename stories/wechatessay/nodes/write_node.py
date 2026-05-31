"""
wechatessay.nodes.write_node

节点5: write_node — 多模型并行全文写作节点

【核心设计】
    使用同一份写作 prompt (FULL_WRITE_SYSTEM_PROMPT)，
    并行调用多个独立 Deep Agent（各用不同模型），
    各自独立完成全文写作并自评分数，
    最后选择评分最高的版本输出。

    plot → write_node
        ├→ Agent-deepseek → 文章A + 自评分数
        ├→ Agent-kimi     → 文章B + 自评分数
        └→ Agent-qwen     → 文章C + 自评分数
        └→ 择优（选最高分）→ article_output

    如果带有 review_feedback（来自 review_node 的修改意见）：
    → 在 user message 中注入评审意见，要求针对性修改

职责：
1. 读取 plot_result / blueprint_result / search_result
2. 为每个模型创建独立 Deep Agent（同一份 FULL_WRITE_SYSTEM_PROMPT）
3. 并行调用所有 Agent，各自写作 + 自评
4. 选评分最高的版本保存
5. 记录写作历史到 writing_history

依赖：
- Deep Agent (create_deep_agent)
- FULL_WRITE_SYSTEM_PROMPT
- WRITER_CONFIG
"""

from __future__ import annotations

import asyncio
import logging
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
    WRITER_CONFIG,
)
from wechatessay.prompts.vx_prompt import FULL_WRITE_SYSTEM_PROMPT
from wechatessay.states.vx_state import (
    ArticleOutputNode,
    GraphState,
    WritingRecord,
)
from wechatessay.tools.base_tools.base_tool import get_base_tools
from wechatessay.tools.mcp_tools.mcp_tool import get_total_tools
from wechatessay.utils.json_utils import parse_json_response

logger = logging.getLogger(__name__)


def _format_context(state: GraphState) -> str:
    """【保留】组装写作所需的完整上下文（大纲+蓝图+素材）。"""
    plot = state["plot_result"]
    blueprint = state.get("blueprint_result")
    search = state.get("search_result")

    ctx = plot.writing_context
    gs = ctx.global_style

    global_ctx = f"""【文章标题】{ctx.article_title}
【核心观点】{ctx.core_idea}
【目标受众】{ctx.target_audience}
【语调】{gs.tone}
【语言约束】{gs.language_requirement}
【风格样板句】{__import__('json').dumps(gs.example_sentences, ensure_ascii=False)}
"""

    segments_info = []
    for i, seg in enumerate(plot.content_segments):
        gs_req = seg.gold_sentence_requirement
        wc = seg.word_count_range
        segments_info.append(
            f"\n--- 第{i + 1}段 ---\n"
            f"类型: {seg.segment_type} | 小标题: {seg.section_title or '无'}\n"
            f"核心逻辑: {seg.core_logic}\n"
            f"必须包含: {__import__('json').dumps(seg.key_information, ensure_ascii=False)}\n"
            f"情绪目标: {seg.emotional_objective}\n"
            f"修辞手法: {seg.rhetorical_device}\n"
            f"金句预留: 位置={gs_req.position}, 主题={gs_req.theme}\n"
            f"字数范围: {wc.min}-{wc.max}字\n"
            f"素材来源: {__import__('json').dumps(seg.material_sources, ensure_ascii=False) or '无'}\n"
            f"向下过渡: {seg.transition_to_next or '无'}"
        )
    plot_ctx = "【大纲】\n" + "\n".join(segments_info)

    blueprint_ctx = "【蓝图】暂无"
    if blueprint:
        plan = blueprint.writing_plan
        blueprint_ctx = f"""【核心创作思路】{plan.core_idea}
【引子设计】{plan.lead_in}
【文章线索】{__import__('json').dumps(plan.clues, ensure_ascii=False)}
【情绪曲线设计】{blueprint.emotional_arc_design}
【钩子策略】{__import__('json').dumps(blueprint.hook_strategy, ensure_ascii=False)}
【互动设计】{blueprint.interactive_design}
【写作方向】{__import__('json').dumps(plan.writing_direction, ensure_ascii=False)}
【风险提示】{__import__('json').dumps(plan.risk_notes, ensure_ascii=False)}
"""

    search_ctx = "【搜索素材】暂无"
    if search:
        parts = ["【搜索素材 — 可供引用的内容】"]
        for s in search.search_sources:
            parts.append(f"  - [{s.platform}] {s.title} (可信度:{s.credibility_score}/5)\n    {s.content_summary}...")
        if search.expert_quotes:
            parts.append(f"专家观点: {__import__('json').dumps(search.expert_quotes, ensure_ascii=False)}")
        if search.data_supplements:
            parts.append(f"数据补充: {__import__('json').dumps(search.data_supplements, ensure_ascii=False)}")
        if search.related_cases:
            parts.append(f"同类案例: {__import__('json').dumps(search.related_cases, ensure_ascii=False)}")
        if search.legal_policy_references:
            parts.append(f"法规引用: {__import__('json').dumps(search.legal_policy_references, ensure_ascii=False)}")
        search_ctx = "\n".join(parts)

    return f"{global_ctx}\n{plot_ctx}\n{blueprint_ctx}\n{search_ctx}"


def _build_write_task(state: GraphState) -> str:
    """【修改】构建写作任务（上下文 + 可选评审反馈）。"""
    context = _format_context(state)
    review_feedback = state.get("review_feedback")
    revision_count = state.get("revision_count", 0)

    parts = ["基于以下信息，一次性生成完整的公众号文章全文。\n\n", context]

    if review_feedback:
        parts.append(
            f"\n\n【第{revision_count}轮修改要求】\n"
            f"以下是评审反馈，请针对这些问题进行修改，保留原有优点：\n"
            f"{review_feedback}\n\n"
            f"请输出修改后的完整文章 JSON（ArticleOutputNode 结构），"
            f"不要只输出修改部分，要输出完整文章。"
            f"结果一定要 ArticleOutputNode 的结构，不许落盘，不许擅自加描述、总结等其他内容，你输出的结果只有ArticleOutputNode的JSON结构"
        )

    parts.append(
        "\n\n请按 ArticleOutputNode 的 JSON 结构输出完整文章，"
        "并在 JSON 中额外加入字段 selfScore（0-100 自评分数）。"
        "不要输出任何其他描述文字。"
        f"结果不许落盘,不许写入其他文件，后续节点需要使用生成的结构，结果必须包含在内"
    )

    return "".join(parts)


async def _write_with_model(
    model: str,
    task_content: str,
    iteration: int,
) -> tuple[Optional[ArticleOutputNode], Optional[WritingRecord]]:
    """
    【新增】用单个模型写作。

    返回: (文章, 写作记录) 或 (None, None)
    """
    logger.info(f"[write_node] 启动写作 Agent: {model}")

    try:
        backend = load_backend()
        agent = create_deep_agent(
            model=model,
            tools=[],
            system_prompt=FULL_WRITE_SYSTEM_PROMPT,
            backend=backend,
            name=f"writer_{model.replace(':', '_')}",
        )

        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": task_content}]
        })
        response_content = result["messages"][-1].content if result.get("messages") else ""

        if not response_content:
            logger.warning(f"[write_node] {model} 返回空响应")
            return None, None

        parsed = parse_json_response(response_content)
        if not isinstance(parsed, dict):
            logger.warning(f"[write_node] {model} 返回的不是 JSON")
            return None, None

        # 解析文章
        article = None
        try:
            article = ArticleOutputNode.model_validate(parsed)
        except Exception as e:
            # 尝试去掉 selfScore 后再解析
            parsed_copy = {k: v for k, v in parsed.items() if k != "selfScore"}
            try:
                article = ArticleOutputNode.model_validate(parsed_copy)
            except Exception:
                logger.warning(f"[write_node] {model} 文章格式错误: {e}")
                return None, None

        self_score = parsed.get("selfScore", 0)
        if not isinstance(self_score, int):
            self_score = 0

        word_count = article.metadata.get("totalWordCount", 0) if article.metadata else 0
        title = article.parts[0].title_alternatives[0] if article.parts else ""

        record = WritingRecord(
            iteration=iteration,
            modelUsed=model,
            selfScore=self_score,
            wordCount=word_count,
            title=title,
            hasReviewFeedback=False,
        )

        logger.info(f"[write_node] {model} 完成: {self_score}分, {word_count}字")
        return article, record

    except Exception as e:
        logger.error(f"[write_node] {model} 写作失败: {e}")
        return None, None


def write_node(state: GraphState) -> GraphState:
    """【修改】同步入口包装。"""
    import asyncio
    return asyncio.run(write_node_async(state))


async def write_node_async(state: GraphState) -> GraphState:
    """
    【重写】多模型并行全文写作 + 择优。

    流程：
    1. 读取状态（plot + blueprint + search + 可选 review_feedback）
    2. 为每个模型创建独立 Agent，并行写作
    3. 收集所有版本 + 自评分数
    4. 选评分最高的版本
    5. 保存到 state + 记录写作历史
    """
    plot = state.get("plot_result")
    if not plot:
        state["error_message"] = "缺少 plot_result"
        state["error_node"] = "write_node"
        return state

    models = WRITER_CONFIG.get("models", [])
    if not models:
        logger.error("[write_node] WRITER_CONFIG['models'] 为空")
        state["error_message"] = "未配置写作模型"
        state["error_node"] = "write_node"
        return state

    iteration = state.get("revision_count", 0)
    has_feedback = bool(state.get("review_feedback"))

    if iteration == 0:
        logger.info(f"[write_node] 首次写作: {plot.writing_context.article_title}")
    else:
        logger.info(f"[write_node] 第{iteration}轮修改（基于评审反馈）")

    # 构建写作任务
    task_content = _build_write_task(state)

    # 【核心】并行调用所有模型
    tasks = [_write_with_model(m, task_content, iteration) for m in models]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 收集成功的结果
    candidates: list[tuple[ArticleOutputNode, WritingRecord]] = []
    for result in results:
        if isinstance(result, Exception):
            continue
        article, record = result
        if article and record:
            candidates.append((article, record))

    if not candidates:
        logger.error("[write_node] 所有模型写作均失败")
        state["error_message"] = "所有写作模型均失败"
        state["error_node"] = "write_node"
        return state

    # 【核心】择优：选 selfScore 最高的版本
    best_article, best_record = max(candidates, key=lambda x: x[1].self_score)

    # 更新 record 标记是否有评审反馈
    best_record.has_review_feedback = has_feedback

    # 保存写作历史
    writing_history = state.get("writing_history", [])
    writing_history.append(best_record.model_dump(by_alias=True))
    state["writing_history"] = writing_history

    # 保存最优版本
    state["article_output"] = best_article
    state["current_node"] = "write_node"
    state["node_status"]["write_node"] = "completed"

    logger.info(
        f"[write_node] 择优完成！共{candidates}个版本，"
        f"选择 [{best_record.model_used}] 的版本 "
        f"（自评{best_record.self_score}分，{best_record.word_count}字）"
    )

    return state
