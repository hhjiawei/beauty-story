"""
wechatessay.nodes.legality_node

节点7: legality_node — 合规检查 + 小规模精修节点

【核心设计】在 article_output 基础上进行小规模修改：
    1. 读取 article_output（评审通过后的文章）
    2. 调用 Agent 检查问题 + 直接修改
    3. 修改后的文章保存到 legality_result.corrected_article
    4. 同时更新 state["article_output"] 为修改后的版本
    5. 如未通过 → needs_legality_fix=true → 循环回自身再检查
    6. 最多 MAX_LEGALITY_ROUNDS 轮

【小规模修改原则】
    - 只改有问题的部分，没问题的文字不动
    - 保留原文结构和风格
    - 每处修改标注位置、原文、修改后、原因

【循环流程】
    legality(第0轮检查) → 发现问题 → 修改 → needs_legality_fix=true
    legality(第1轮检查) → 还有问题 → 修改 → needs_legality_fix=true
    legality(第2轮检查) → 通过 → needs_legality_fix=false → composition
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from deepagents import create_deep_agent

from wechatessay.agents.backend import load_backend
from wechatessay.config import (
    LEGALITY_CONFIG,
    MODEL_CONFIG,
    get_model_instance,
)
from wechatessay.prompts.vx_prompt import LEGALITY_REVIEW_PROMPT
from wechatessay.states.vx_state import (
    ArticleOutputNode,
    GraphState,
    LegalityCheckResult,
)
from wechatessay.utils.json_utils import parse_json_response

logger = logging.getLogger(__name__)

# 校验最大轮次
MAX_LEGALITY_ROUNDS = 3


def _create_legality_agent() -> Any:
    """创建合规检查 Agent。"""
    backend = load_backend()
    model_name = MODEL_CONFIG.get("review_model", MODEL_CONFIG["default_model"])
    return create_deep_agent(
        model=get_model_instance(model_name),
        tools=[],
        system_prompt=LEGALITY_REVIEW_PROMPT,
        backend=backend,
        name="legality_checker",
    )


def _build_check_task(article: ArticleOutputNode) -> str:
    """构建检查任务。"""
    article_text = article.full_text or ""
    title = article.parts[0].title_alternatives[0] if article.parts else "未命名"
    meta = article.metadata or {}

    return f"""请对以下文章进行合规检查并直接修改。

【文章标题】{title}
【字数】{meta.get('totalWordCount', 0)}字

【全文内容】
{article_text}

请严格按照 system prompt 的要求：
1. 逐项检查（错别字/AI感/敏感内容/事实/文风）
2. 发现问题直接在原文基础上修改
3. **只改有问题的部分，没问题的文字不动**
4. 每处修改标注 location + originalText + suggestion
5. **无论是否通过，都必须输出 correctedArticle**（完整的 ArticleOutputNode）
6. 只输出 JSON，不要其他文字
7. 结果不许落盘，不许擅自加描述、总结等其他内容，运行后的最终输出内容必须在最后的AIMessage中，后续节点调用做准备
"""


def _parse_legality_response(response_content: str) -> Optional[LegalityCheckResult]:
    """解析合规检查结果。"""
    if not response_content:
        return None

    try:
        parsed = parse_json_response(response_content)
        if not isinstance(parsed, dict):
            return None

        # 解析 correctedArticle
        corrected = None
        raw_corrected = parsed.get("correctedArticle")
        if isinstance(raw_corrected, dict):
            try:
                corrected = ArticleOutputNode.model_validate(raw_corrected)
            except Exception as e:
                logger.warning(f"[legality_node] correctedArticle 解析失败: {e}")

        return LegalityCheckResult(
            isPassed=parsed.get("isPassed", False),
            overallScore=parsed.get("overallScore", 0),
            typoIssues=parsed.get("typoIssues", []),
            aiFlavorIssues=parsed.get("aiFlavorIssues", []),
            sensitiveIssues=parsed.get("sensitiveIssues", []),
            factualIssues=parsed.get("factualIssues", []),
            styleIssues=parsed.get("styleIssues", []),
            aiFlavorScore=parsed.get("aiFlavorScore", 1.0),
            readabilityScore=parsed.get("readabilityScore", 0.0),
            correctionSuggestions=parsed.get("correctionSuggestions", []),
            correctedArticle=corrected,
        )
    except Exception as e:
        logger.warning(f"[legality_node] 解析失败: {e}")
        return None


def _build_fix_record(result: LegalityCheckResult, iteration: int) -> Dict[str, Any]:
    """构建修改记录。"""
    issues = []
    for issue_list in [result.typo_issues, result.ai_flavor_issues,
                        result.sensitive_issues, result.factual_issues, result.style_issues]:
        for issue in issue_list:
            issues.append({
                "type": issue.issue_type,
                "severity": issue.severity,
                "location": issue.location,
                "original": issue.original_text,
                "fixed": issue.suggestion,
            })

    return {
        "iteration": iteration,
        "overallScore": result.overall_score,
        "isPassed": result.is_passed,
        "issueCount": len(issues),
        "issues": issues,
        "suggestions": result.correction_suggestions,
    }


def legality_node(state: GraphState) -> GraphState:
    """同步入口包装。"""
    import asyncio
    return asyncio.run(legality_node_async(state))


async def legality_node_async(state: GraphState) -> GraphState:
    """
    合规检查 + 小规模精修主逻辑。

    流程：
    1. 读取 article_output
    2. 调用 Agent 检查 + 修改
    3. 解析结果
    4. 通过 → needs_legality_fix=false → composition
    5. 未通过 → 更新 article_output 为修改后版本 → needs_legality_fix=true → 循环
    6. 达到 MAX_LEGALITY_ROUNDS 强制通过
    """
    article = state.get("article_output")
    if not article:
        state["error_message"] = "缺少 article_output"
        state["error_node"] = "legality_node"
        return state

    iteration = state.get("legality_iteration", 0)

    # 达到最大轮次强制通过
    if iteration >= MAX_LEGALITY_ROUNDS:
        logger.warning(f"[legality_node] 已达最大轮次({MAX_LEGALITY_ROUNDS})，强制通过")
        state["needs_legality_fix"] = False
        state["current_node"] = "legality_node"
        return state

    logger.info(f"[legality_node] ===== 第{iteration}轮合规检查开始 =====")

    # 调用 Agent
    try:
        agent = _create_legality_agent()
        task_content = _build_check_task(article)
        result = await agent.ainvoke({"messages": [{"role": "user", "content": task_content}]})
        response_content = result["messages"][-1].content if result.get("messages") else ""
    except Exception as e:
        logger.error(f"[legality_node] 调用失败: {e}")
        state["error_message"] = f"合规检查失败: {e}"
        state["error_node"] = "legality_node"
        return state

    # 解析结果
    legality_result = _parse_legality_response(response_content)

    if not legality_result:
        logger.warning("[legality_node] 解析失败，跳过校验")
        state["needs_legality_fix"] = False
        state["current_node"] = "legality_node"
        return state

    # 保存结果
    state["legality_result"] = legality_result

    # 记录修改历史
    fix_record = _build_fix_record(legality_result, iteration)
    fix_history = state.get("legality_fix_history", [])
    fix_history.append(fix_record)
    state["legality_fix_history"] = fix_history

    # 如果有 correctedArticle，更新 article_output
    if legality_result.corrected_article:
        state["article_output"] = legality_result.corrected_article
        word_count = legality_result.corrected_article.metadata.get("totalWordCount", 0)
        logger.info(f"[legality_node] 文章已更新（{word_count}字）")

    # 判断是否通过
    max_ai_score = LEGALITY_CONFIG.get("max_ai_score", 0.3)

    if legality_result.is_passed and legality_result.ai_flavor_score <= max_ai_score:
        state["needs_legality_fix"] = False
        logger.info(
            f"[legality_node] 第{iteration}轮通过！"
            f"评分={legality_result.overall_score}, AI感={legality_result.ai_flavor_score:.2f} "
            f"→ 进入排版"
        )
    else:
        state["needs_legality_fix"] = True
        state["legality_iteration"] = iteration + 1
        issue_count = (len(legality_result.typo_issues) + len(legality_result.ai_flavor_issues) +
                       len(legality_result.sensitive_issues) + len(legality_result.factual_issues) +
                       len(legality_result.style_issues))
        logger.info(
            f"[legality_node] 第{iteration}轮未通过（{legality_result.overall_score}分，"
            f"{issue_count}个问题）→ 第{iteration + 1}轮再检查"
        )

    state["current_node"] = "legality_node"
    return state