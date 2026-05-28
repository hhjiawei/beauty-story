"""
wechatessay.nodes.review_node

节点5-Review: review_node — 多模型评审+择优节点（SubAgent 架构）

【核心设计】
    review_supervisor（主评审 Agent）
        ├── task("语言精修师") → 评审意见 + 修改后的文章版本A
        ├── task("传播策略师") → 评审意见 + 修改后的文章版本B
        ├── task("逻辑架构师") → 评审意见 + 修改后的文章版本C
        └── task("合规审查员") → 评审意见 + 修改后的文章版本D
        └── 比较择优 → 最优版本替换 article_output → 输出评审报告

【与旧架构的区别】
- 旧：评审提意见 → 回到 write_node 修改 → 再评审（循环）
- 新：每个 SubAgent 直接修改全文 → 主 Agent 比较择优 → 一步到位

职责：
1. 创建主评审 Agent，配置多个评审 SubAgent（不同模型、统一提示词）
2. 主 Agent 调用各 SubAgent，每个 SubAgent 评审+修改全文
3. 主 Agent 比较各版本，选择最优版本
4. 最优版本直接替换 state["article_output"]
5. 评审报告保存到 state["review_result"]

依赖：
- Deep Agent (create_deep_agent)
- config.REVIEWERS_CONFIG
- vx_prompt.REVIEW_AND_REVISE_SYSTEM_PROMPT, REVIEW_SUPERVISOR_SYSTEM_PROMPT
"""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

from deepagents import create_deep_agent

from wechatessay.agents.backend import load_backend
from wechatessay.config import MODEL_CONFIG, REVIEWERS_CONFIG
from wechatessay.prompts.vx_prompt import (
    REVIEW_AND_REVISE_SYSTEM_PROMPT,
    REVIEW_SUPERVISOR_SYSTEM_PROMPT,
)
from wechatessay.states.vx_state import (
    ArticleOutputNode,
    GraphState,
    ReviewResult,
    ReviewerOpinion,
)
from wechatessay.utils.json_utils import parse_json_response

logger = logging.getLogger(__name__)


def _build_subagent_for_reviewer(cfg: dict) -> dict:
    """将单个评审员配置转换为 SubAgent 字典格式。

    所有 SubAgent 使用统一的评审+修改提示词模板，
    区别仅在于注入的 identity、focus_dimensions 和 model。
    """
    focus_items = cfg.get("focus", [])
    focus_text = "\n".join(f"  - {item}" for item in focus_items)

    system_prompt = REVIEW_AND_REVISE_SYSTEM_PROMPT.format(
        identity=cfg["identity"],
        focus_dimensions=focus_text,
    )

    subagent = {
        "name": cfg["name"],
        "description": (
            f"{cfg['name']}：{cfg['identity']} "
            f"负责对文章进行专业评审并直接修改全文，"
            f"输出自己视角的最优版本。"
        ),
        "system_prompt": system_prompt,
    }

    if cfg.get("model"):
        subagent["model"] = cfg["model"]

    return subagent


def _build_supervisor_prompt(reviewer_cfgs: List[dict]) -> str:
    """构建主评审 Agent 的 system prompt。"""
    reviewer_list = "\n".join(
        f"  {i + 1}. task(\"{cfg['name']}\", ... )  — 使用模型：{cfg.get('model', '默认')}"
        for i, cfg in enumerate(reviewer_cfgs)
    )

    return REVIEW_SUPERVISOR_SYSTEM_PROMPT.format(reviewer_list=reviewer_list)


def _create_review_supervisor(reviewer_cfgs: List[dict]) -> Any:
    """创建带多个评审 SubAgent 的主评审 Agent。"""
    backend = load_backend()
    subagents = [_build_subagent_for_reviewer(cfg) for cfg in reviewer_cfgs]
    supervisor_prompt = _build_supervisor_prompt(reviewer_cfgs)

    return create_deep_agent(
        model=MODEL_CONFIG.get("review_model", MODEL_CONFIG["default_model"]),
        tools=[],
        system_prompt=supervisor_prompt,
        backend=backend,
        subagents=subagents,
        name="review_supervisor",
    )


def _build_article_task(article: ArticleOutputNode) -> str:
    """构建传给主评审 Agent 的文章内容。"""
    article_text = article.fullText or ""

    parts_summary = []
    for p in article.parts:
        parts_summary.append(
            f"\n--- 第{p.part_index}段 ---\n"
            f"标题备选：{p.title_alternatives}\n"
            f"内容：{p.content[:600]}...\n"
            f"节奏：{p.rhythm} | 阅读时间：{p.reading_time}"
        )

    golden_lines = []
    for p in article.parts:
        for g in p.golden_sentences:
            golden_lines.append(f"  [{g.position}] {g.text}")

    title = article.parts[0].title_alternatives[0] if article.parts else "未命名"
    meta = article.metadata or {}

    return f"""请对以下公众号文章组织评审团队进行联合评审与修改。

【文章标题】{title}
【字数】{meta.get('totalWordCount', 0)}字 | 【阅读时间】{meta.get('readingTime', '未知')}

【全文内容】
{article_text}

【各段摘要】
{''.join(parts_summary)}

【金句】
{chr(10).join(golden_lines) if golden_lines else "  无"}

【SEO信息】
  描述：{article.seo_info.get('description', '无') if article.seo_info else '无'}
  标签：{article.seo_info.get('tags', []) if article.seo_info else []}

请按照 system prompt 中的工作流程：
1. 逐一调用所有评审 SubAgent（每个都会评审+修改全文）
2. 比较各版本的修改质量
3. 选择最优版本
4. 输出最终评审报告 JSON（包含 bestVersionFrom 和 selectionReason）
"""


def _parse_subagent_review(
    response_content: str,
    cfg: dict,
) -> Optional[ReviewerOpinion]:
    """解析单个 SubAgent 返回的评审+修改结果。"""
    try:
        parsed = parse_json_response(response_content)
        if not isinstance(parsed, dict):
            return None

        revised_article = None
        raw_article = parsed.get("revisedArticle")
        if isinstance(raw_article, dict):
            try:
                revised_article = ArticleOutputNode.model_validate(raw_article)
            except Exception as e:
                logger.warning(f"解析 {cfg['name']} 的 revisedArticle 失败: {e}")

        return ReviewerOpinion(
            reviewerName=parsed.get("reviewerName", cfg["name"]),
            identity=parsed.get("identity", cfg["identity"]),
            modelUsed=cfg.get("model", MODEL_CONFIG["default_model"]),
            passed=parsed.get("passed", False),
            overallScore=parsed.get("overallScore", 0),
            strengths=parsed.get("strengths", []),
            issues=parsed.get("issues", []),
            revisionSuggestions=parsed.get("revisionSuggestions", ""),
            revisedArticle=revised_article,
        )
    except Exception as e:
        logger.warning(f"解析 {cfg['name']} 的评审结果失败: {e}")
        return None


def _parse_supervisor_response(
    response_content: str,
    reviewer_cfgs: List[dict],
    opinions_from_subagents: List[ReviewerOpinion],
) -> tuple[ReviewResult, Optional[ArticleOutputNode]]:
    """解析主评审 Agent 的汇总结果，提取最优版本。

    Returns:
        (ReviewResult, 最优版本的 ArticleOutputNode 或 None)
    """
    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict):
            best_from = parsed.get("bestVersionFrom", "")
            selection_reason = parsed.get("selectionReason", "")

            # 从 opinions_from_subagents 中找到最优版本
            best_article = None
            for op in opinions_from_subagents:
                if op.reviewer_name == best_from and op.revised_article:
                    best_article = op.revised_article
                    break

            # 如果没找到匹配的，选第一个有 revised_article 的
            if not best_article:
                for op in opinions_from_subagents:
                    if op.revised_article:
                        best_article = op.revised_article
                        best_from = op.reviewer_name
                        selection_reason = f"回退选择：{best_from} 提供了可用的修改版本"
                        break

            opinions_raw = parsed.get("opinions", [])
            # 合并主 Agent 返回的 opinions 和 SubAgent 实际返回的（以 SubAgent 的为准，因为包含 revisedArticle）
            merged_opinions = opinions_from_subagents if opinions_from_subagents else [
                ReviewerOpinion(
                    reviewerName=op.get("reviewerName", "未知"),
                    identity=op.get("identity", ""),
                    modelUsed=op.get("modelUsed", ""),
                    passed=op.get("passed", False),
                    overallScore=op.get("overallScore", 0),
                    strengths=op.get("strengths", []),
                    issues=op.get("issues", []),
                    revisionSuggestions=op.get("revisionSuggestions", ""),
                )
                for op in opinions_raw
            ]

            review_result = ReviewResult(
                allPassed=parsed.get("allPassed", False),
                passRate=parsed.get("passRate", 0.0),
                overallScore=parsed.get("overallScore", 0),
                opinions=merged_opinions,
                consolidatedFeedback=parsed.get("consolidatedFeedback", ""),
                revisionRound=0,
                bestVersionFrom=best_from,
                selectionReason=selection_reason,
            )

            return review_result, best_article

    except Exception as e:
        logger.warning(f"解析主评审 Agent 汇总结果失败: {e}")

    # Fallback：从 SubAgent 结果中自己择优
    return _fallback_select_best(opinions_from_subagents)


def _fallback_select_best(
    opinions: List[ReviewerOpinion],
) -> tuple[ReviewResult, Optional[ArticleOutputNode]]:
    """当主 Agent 解析失败时，自行择优。"""
    if not opinions:
        return ReviewResult(
            allPassed=True, passRate=1.0, overallScore=100,
            opinions=[], consolidatedFeedback="无评审数据，跳过。",
            bestVersionFrom="", selectionReason="",
        ), None

    total_score = sum(op.overall_score for op in opinions)
    avg_score = int(total_score / len(opinions)) if opinions else 0
    passed_count = sum(1 for op in opinions if op.passed)
    pass_rate = passed_count / len(opinions)

    # 选择评分最高且有 revised_article 的版本
    best_op = None
    for op in sorted(opinions, key=lambda x: x.overall_score, reverse=True):
        if op.revised_article:
            best_op = op
            break

    if not best_op:
        best_op = opinions[0]

    best_article = best_op.revised_article
    best_from = best_op.reviewer_name

    review_result = ReviewResult(
        allPassed=all(op.passed for op in opinions),
        passRate=pass_rate,
        overallScore=avg_score,
        opinions=opinions,
        consolidatedFeedback=f"各评审员均完成评审与修改。择优采用 {best_from} 的版本。",
        bestVersionFrom=best_from,
        selectionReason=f"该版本评分最高（{best_op.overall_score}分），"
                        f"且{'通过' if best_op.passed else '未通过'}评审。",
    )

    return review_result, best_article


def review_node(state: GraphState) -> GraphState:
    """review_node 同步入口包装。"""
    import asyncio
    return asyncio.run(review_node_async(state))


async def review_node_async(state: GraphState) -> GraphState:
    """
    多模型 SubAgent 评审 + 择优主逻辑。

    流程：
    1. 读取 article_output
    2. 创建主评审 Agent（带所有评审 SubAgent）
    3. 主 Agent 调用各 SubAgent → 每个 SubAgent 评审+修改全文
    4. 主 Agent 比较择优 → 选择最优版本
    5. 最优版本替换 article_output → 直接进入 composition
    """
    article = state.get("article_output")
    if not article:
        state["error_message"] = "缺少 article_output，无法评审"
        state["error_node"] = "review_node"
        return state

    reviewer_cfgs = REVIEWERS_CONFIG.get("reviewers", [])
    if not reviewer_cfgs:
        logger.warning("[review_node] 未配置评审员，跳过评审")
        state["review_result"] = ReviewResult(
            allPassed=True, passRate=1.0, overallScore=100,
            opinions=[], consolidatedFeedback="无评审员配置，跳过。",
            bestVersionFrom="", selectionReason="",
        )
        state["current_node"] = "review_node"
        return state

    logger.info(
        f"[review_node] 启动多模型评审+择优，"
        f"文章：{article.parts[0].title_alternatives[0] if article.parts else '未命名'} "
        f"（{article.metadata.get('totalWordCount', 0)}字）"
    )

    # 创建主评审 Agent（带所有 SubAgent）
    supervisor = _create_review_supervisor(reviewer_cfgs)

    # 构建评审任务
    task_content = _build_article_task(article)

    messages = [{"role": "user", "content": task_content}]

    try:
        result = await supervisor.ainvoke({"messages": messages})
        response_content = result["messages"][-1].content if result.get("messages") else ""

        # 尝试从主 Agent 的响应中解析各 SubAgent 的结果
        # 注意：由于 SubAgent 的结果嵌在主 Agent 的对话历史中，
        # 实际 opinions 需要从更深层解析。这里我们同时尝试两种方式：
        # 1. 从主 Agent 的最终响应解析
        # 2. 如果失败，用 fallback 从已知数据中择优

        opinions_from_subagents = []
        best_article = None

        # 尝试解析主 Agent 的最终汇总
        review_result, best_article = _parse_supervisor_response(
            response_content, reviewer_cfgs, opinions_from_subagents
        )

        # 如果主 Agent 没选出最优版本，用 fallback
        if not best_article:
            review_result, best_article = _fallback_select_best(
                review_result.opinions
            )

    except Exception as e:
        logger.error(f"[review_node] 评审主管 Agent 执行失败: {e}")
        state["error_message"] = f"评审失败: {str(e)}"
        state["error_node"] = "review_node"
        return state

    # 保存评审结果
    state["review_result"] = review_result

    # 用最优版本替换 article_output
    if best_article:
        state["article_output"] = best_article
        logger.info(
            f"[review_node] 择优完成！采用 [{review_result.best_version_from}] 的版本 "
            f"（评分{review_result.overall_score}）→ 进入排版"
        )
    else:
        logger.warning("[review_node] 未获得任何修改版本，保留原文")

    # 清理不再需要的循环控制字段
    state["revision_notes"] = None
    state["revision_count"] = 0
    state["current_node"] = "review_node"

    return state