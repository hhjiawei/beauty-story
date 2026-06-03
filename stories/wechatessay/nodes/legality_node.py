"""
wechatessay.nodes.legality_node

节点7: legality_node — 合规检查 + 小规模精修节点

【核心设计】
1. 读取 article_output（评审通过后的文章）
2. 调用 Agent 检查问题 + 直接修改
3. LLM 只输出 correctedFullText（修改后的文章纯文本字符串）
4. 代码层将 correctedFullText 直接更新到 article_output.full_text
5. 如未通过 → needs_legality_fix=true → 循环回自身再检查
6. 最多 MAX_LEGALITY_ROUNDS 轮

【数据简化原则】
- 不再要求 LLM 输出完整的 ArticleOutputNode JSON（容易出错）
- 所有解析基于 dict 操作，不做 Pydantic model_validate
- issues 以原生 dict 列表存储
- 最终结果：state["article_output"].full_text = 修改后的全文
"""

from __future__ import annotations

import asyncio
import logging
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
)
from wechatessay.utils.json_utils import parse_json_response

logger = logging.getLogger(__name__)

# 校验最大轮次
MAX_LEGALITY_ROUNDS = 3


# ═══════════════════════════════════════════════
# Agent 创建
# ═══════════════════════════════════════════════

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


# ═══════════════════════════════════════════════
# 任务构建
# ═══════════════════════════════════════════════

def _build_check_task(article: ArticleOutputNode) -> str:
    """构建检查任务。"""
    article_text = article.full_text or ""
    title = ""
    if article.parts and article.parts[0].title_alternatives:
        title = article.parts[0].title_alternatives[0]
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
5. **无论是否通过，都必须输出 correctedFullText**（修改后的完整文章纯文本字符串）
6. correctedFullText 放在 JSON 顶层，不要嵌套在 correctedArticle 里
7. 只输出 JSON，不要其他文字
8. 结果不许落盘，不许擅自加描述、总结等其他内容

正确的输出格式示例：
{{
  "isPassed": false,
  "overallScore": 85,
  "typoIssues": [
    {{
      "issueType": "typo",
      "severity": "warning",
      "location": "第2段第3行",
      "originalText": "错词",
      "suggestion": "正确写法"
    }}
  ],
  "aiFlavorIssues": [],
  "sensitiveIssues": [],
  "factualIssues": [],
  "styleIssues": [],
  "aiFlavorScore": 0.2,
  "readabilityScore": 0.85,
  "correctionSuggestions": ["修改说明"],
  "correctedFullText": "修改后的完整文章全文放在这里..."
}}
"""


# ═══════════════════════════════════════════════
# 解析与提取（核心：纯 dict 操作，无 Pydantic 验证）
# ═══════════════════════════════════════════════

def _extract_issues(parsed: dict, key: str) -> list[dict]:
    """安全提取 issues 列表，确保每项是 dict 且有必要字段。"""
    raw = parsed.get(key, [])
    if not isinstance(raw, list):
        return []
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        # 确保必要字段存在
        if item.get("originalText") and item.get("suggestion"):
            cleaned.append({
                "issueType": item.get("issueType", "unknown"),
                "severity": item.get("severity", "info"),
                "location": item.get("location", ""),
                "originalText": item["originalText"],
                "suggestion": item["suggestion"],
            })
    return cleaned


def _extract_corrected_text(parsed: dict, original: ArticleOutputNode) -> str:
    """
    从 LLM 输出中提取修改后的文章文本。
    兼容多种可能的格式，按优先级尝试。
    """
    original_text = original.full_text or ""

    # 优先级1: correctedFullText（顶层字符串，我们推荐的格式）
    cft = parsed.get("correctedFullText")
    if isinstance(cft, str) and cft.strip():
        return cft.strip()

    # 优先级2: correctedArticle 是字符串
    corrected = parsed.get("correctedArticle")
    if isinstance(corrected, str) and corrected.strip():
        return corrected.strip()

    # 优先级3: correctedArticle 是 dict，取各种可能的文本字段
    if isinstance(corrected, dict):
        for key in ["fullText", "full_text", "correctedFullText", "content", "text"]:
            val = corrected.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

        # 尝试 parts[0].content
        parts = corrected.get("parts", [])
        if isinstance(parts, list) and parts:
            first_part = parts[0]
            if isinstance(first_part, dict):
                content = first_part.get("content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()

    # 优先级4: 根据 issues 中的 originalText + suggestion 自己替换原文
    modified = _apply_issues_as_replacements(parsed, original_text)
    if modified != original_text:
        return modified

    # 兜底: 返回原文
    return original_text


def _apply_issues_as_replacements(parsed: dict, original_text: str) -> str:
    """根据所有 issues 中的 originalText/suggestion 对原文进行替换修改。"""
    if not original_text:
        return original_text

    # 收集所有 issues
    all_issues = []
    for key in ["typoIssues", "aiFlavorIssues", "sensitiveIssues", "factualIssues", "styleIssues"]:
        all_issues.extend(_extract_issues(parsed, key))

    if not all_issues:
        return original_text

    # 按原文长度从长到短排序，避免短匹配干扰长匹配
    replacements = []
    for issue in all_issues:
        orig = issue["originalText"]
        sugg = issue["suggestion"]
        if orig and sugg and orig != sugg and orig in original_text:
            replacements.append((orig, sugg))

    if not replacements:
        return original_text

    replacements.sort(key=lambda x: len(x[0]), reverse=True)

    # 执行替换（每个 orig 只替换第一次出现）
    text = original_text
    for orig, sugg in replacements:
        text = text.replace(orig, sugg, 1)

    return text


def _parse_legality_result(parsed: dict, original: ArticleOutputNode) -> tuple[str, dict]:
    """
    解析 LLM 返回的字典，提取修改后的文本和简化的校验结果。

    Returns:
        (corrected_text, simplified_result)
    """
    corrected_text = _extract_corrected_text(parsed, original)

    result = {
        "is_passed": bool(parsed.get("isPassed", False)),
        "overall_score": int(parsed.get("overallScore", 0) or 0),
        "ai_flavor_score": float(parsed.get("aiFlavorScore", 1.0) or 1.0),
        "readability_score": float(parsed.get("readabilityScore", 0.0) or 0.0),
        "typo_issues": _extract_issues(parsed, "typoIssues"),
        "ai_flavor_issues": _extract_issues(parsed, "aiFlavorIssues"),
        "sensitive_issues": _extract_issues(parsed, "sensitiveIssues"),
        "factual_issues": _extract_issues(parsed, "factualIssues"),
        "style_issues": _extract_issues(parsed, "styleIssues"),
        "correction_suggestions": [
            s for s in (parsed.get("correctionSuggestions") or [])
            if isinstance(s, str)
        ],
        "corrected_full_text": corrected_text,
    }

    return corrected_text, result


# ═══════════════════════════════════════════════
# 修改记录
# ═══════════════════════════════════════════════

def _build_fix_record(result: dict, iteration: int) -> dict:
    """构建修改记录（纯 dict，无 Pydantic）。"""
    all_issues = (
        result.get("typo_issues", [])
        + result.get("ai_flavor_issues", [])
        + result.get("sensitive_issues", [])
        + result.get("factual_issues", [])
        + result.get("style_issues", [])
    )

    return {
        "iteration": iteration,
        "overall_score": result.get("overall_score", 0),
        "is_passed": result.get("is_passed", False),
        "issue_count": len(all_issues),
        "issues": [
            {
                "type": issue.get("issueType", ""),
                "severity": issue.get("severity", ""),
                "location": issue.get("location", ""),
                "original": issue.get("originalText", ""),
                "fixed": issue.get("suggestion", ""),
            }
            for issue in all_issues
        ],
        "suggestions": result.get("correction_suggestions", []),
    }


# ═══════════════════════════════════════════════
# 节点入口
# ═══════════════════════════════════════════════

def legality_node(state: GraphState) -> GraphState:
    """同步入口包装。"""
    return asyncio.run(legality_node_async(state))


async def legality_node_async(state: GraphState) -> GraphState:
    """
    合规检查 + 小规模精修主逻辑。

    核心流程：
    1. 读取 article_output
    2. 调用 Agent 检查 + 修改
    3. 解析结果（纯 dict 操作，无 Pydantic 验证）
    4. 提取 correctedFullText → 更新 article_output.full_text
    5. 通过 → needs_legality_fix=false → composition
    6. 未通过 → needs_legality_fix=true → 循环（最多3轮）
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

    # 解析 JSON
    try:
        parsed = parse_json_response(response_content)
        if not isinstance(parsed, dict):
            logger.warning("[legality_node] LLM 输出不是字典，跳过校验")
            state["needs_legality_fix"] = False
            state["current_node"] = "legality_node"
            return state
    except Exception as e:
        logger.warning(f"[legality_node] JSON 解析失败: {e}，跳过校验")
        state["needs_legality_fix"] = False
        state["current_node"] = "legality_node"
        return state

    # 核心：提取修改后的文本 + 简化结果（无 Pydantic 验证）
    corrected_text, legality_result = _parse_legality_result(parsed, article)

    # 更新 article_output（核心目标）
    article.full_text = corrected_text
    # 同时更新 parts[0].content，保持 parts 与 full_text 一致
    if article.parts and len(article.parts) > 0:
        article.parts[0].content = corrected_text

    # 显式回写 state（LangGraph 不可变状态需要显式赋值）
    state["article_output"] = article

    # 保存校验结果（纯 dict）
    state["legality_result"] = legality_result

    # 记录修改历史
    fix_record = _build_fix_record(legality_result, iteration)
    fix_history = state.get("legality_fix_history", [])
    fix_history.append(fix_record)
    state["legality_fix_history"] = fix_history

    logger.info(f"[legality_node] 文章已更新（{len(corrected_text)}字）")

    # 判断是否通过
    max_ai_score = LEGALITY_CONFIG.get("max_ai_score", 0.3)
    ai_score = legality_result["ai_flavor_score"]

    if ai_score <= max_ai_score:
        state["needs_legality_fix"] = False
        logger.info(
            f"[legality_node] 第{iteration}轮通过！"
            f"评分={legality_result['overall_score']}, AI感={ai_score:.2f} → 进入排版"
        )
    else:
        state["needs_legality_fix"] = True
        state["legality_iteration"] = iteration + 1
        issue_count = (
            len(legality_result["typo_issues"])
            + len(legality_result["ai_flavor_issues"])
            + len(legality_result["sensitive_issues"])
            + len(legality_result["factual_issues"])
            + len(legality_result["style_issues"])
        )
        logger.info(
            f"[legality_node] 第{iteration}轮未通过（{legality_result['overall_score']}分，"
            f"{issue_count}个问题, AI感={ai_score:.2f}）→ 第{iteration + 1}轮再检查"
        )

    state["current_node"] = "legality_node"
    return state