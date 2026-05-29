"""
wechatessay.nodes.review_node

节点5-Review: review_node — 纯评审节点

【核心设计】
    对 write_node 产出的文章进行评审，只提意见不修改全文。

    review_node 读取 article_output → 调用评审 Agent → 输出评审意见
        ↓ passed=true（无需修改）    → needs_revision=false → 进入 composition
        ↓ passed=false（需要修改）   → needs_revision=true  → review_feedback=意见
                                        ↓
                                   回到 write_node（带评审意见重写）

    达到 MAX_REVISION_ROUNDS 后强制通过。

职责：
1. 读取 article_output
2. 调用评审 Agent（单一模型，只做评审）
3. 如果 passed → 标记通过，进入 composition
4. 如果未通过 → 记录评审意见，回到 write_node
5. 每次评审结果保存到 review_history

依赖：
- Deep Agent (create_deep_agent)
- REVIEW_CONFIG
- MAX_REVISION_ROUNDS
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from deepagents import create_deep_agent

from wechatessay.agents.backend import load_backend
from wechatessay.config import (
    MAX_REVISION_ROUNDS,
    MODEL_CONFIG,
    REVIEW_CONFIG,
)
from wechatessay.prompts.vx_prompt import REVIEW_AND_REVISE_SYSTEM_PROMPT
from wechatessay.states.vx_state import (
    ArticleOutputNode,
    GraphState,
    ReviewRecord,
    ReviewResult,
)
from wechatessay.utils.json_utils import parse_json_response

logger = logging.getLogger(__name__)


def _create_review_agent(model: str) -> Any:
    """【简化】创建纯评审 Agent。"""
    backend = load_backend()
    return create_deep_agent(
        model=model,
        tools=[],
        system_prompt=REVIEW_AND_REVISE_SYSTEM_PROMPT,
        backend=backend,
        name="article_reviewer",
    )


def _build_review_task(article: ArticleOutputNode) -> str:
    """【简化】构建评审任务（仅文章，无修改要求）。"""
    article_text = article.fullText or ""
    title = article.parts[0].title_alternatives[0] if article.parts else "未命名"
    meta = article.metadata or {}

    return f"""请对以下公众号文章进行评审。

【文章标题】{title}
【字数】{meta.get("totalWordCount", 0)}字

【全文内容】
{article_text}

请严格按照 system prompt 中的要求：
1. 从语言、传播、逻辑、合规四个维度全面评审
2. 给出 overallScore 和 passed 判断
3. 如未通过，给出具体的 revisionSuggestions（修改建议）
4. 只输出 JSON，不要任何其他文字
"""


def _parse_review_response(
    response_content: str,
    iteration: int,
    model: str,
) -> Optional[ReviewResult]:
    """【简化】解析评审响应，返回 ReviewResult。"""
    if not response_content:
        return None

    try:
        parsed = parse_json_response(response_content)
        if not isinstance(parsed, dict):
            return None

        return ReviewResult(
            iteration=iteration,
            modelUsed=parsed.get("model", model),
            overallScore=parsed.get("overallScore", 0),
            passed=parsed.get("passed", False),
            strengths=parsed.get("strengths", []),
            issues=parsed.get("issues", []),
            revisionSuggestions=parsed.get("revisionSuggestions", ""),
        )
    except Exception as e:
        logger.warning(f"[review_node] 解析评审结果失败: {e}")
        return None


def review_node(state: GraphState) -> GraphState:
    """同步入口包装。"""
    import asyncio
    return asyncio.run(review_node_async(state))


async def review_node_async(state: GraphState) -> GraphState:
    """
    【重写】纯评审主逻辑。

    流程：
    1. 读取 article_output
    2. 调用评审 Agent
    3. 解析评审结果
    4. 如果通过 → needs_revision=false → 进入 composition
    5. 如果未通过 → needs_revision=true → review_feedback=修改意见 → 回到 write_node
    6. 达到 MAX_REVISION_ROUNDS 后强制通过
    """
    article = state.get("article_output")
    if not article:
        state["error_message"] = "缺少 article_output"
        state["error_node"] = "review_node"
        return state

    iteration = state.get("revision_count", 0)

    # 检查是否已达最大轮次
    if iteration >= MAX_REVISION_ROUNDS:
        logger.warning(f"[review_node] 已达最大修改轮次({MAX_REVISION_ROUNDS})，强制通过")
        state["needs_revision"] = False
        state["review_feedback"] = None
        state["current_node"] = "review_node"
        return state

    # 选择评审模型
    models = REVIEW_CONFIG.get("models", [])
    model = models[iteration % len(models)] if models else MODEL_CONFIG.get("default_model")

    logger.info(
        f"[review_node] 第{iteration}轮评审开始，模型：{model}，"
        f"文章：{article.parts[0].title_alternatives[0] if article.parts else '未命名'}"
    )

    # 调用评审 Agent
    try:
        agent = _create_review_agent(model)
        task_content = _build_review_task(article)
        result = await agent.ainvoke({"messages": [{"role": "user", "content": task_content}]})
        response_content = result["messages"][-1].content if result.get("messages") else ""
    except Exception as e:
        logger.error(f"[review_node] 评审 Agent 调用失败: {e}")
        # 出错时保守处理：认为需要修改
        state["needs_revision"] = True
        state["review_feedback"] = f"评审过程出错: {str(e)}，请检查并重写。"
        state["revision_count"] = iteration + 1
        state["current_node"] = "review_node"
        return state

    # 解析评审结果
    review_result = _parse_review_response(response_content, iteration, model)

    if not review_result:
        logger.warning("[review_node] 评审结果解析失败，保守处理为需修改")
        state["needs_revision"] = True
        state["review_feedback"] = "评审结果解析失败，请检查文章格式并重写。"
        state["revision_count"] = iteration + 1
        state["current_node"] = "review_node"
        return state

    # 保存评审结果
    state["review_result"] = review_result

    # 保存评审历史
    review_history = state.get("review_history", [])
    review_history.append(review_result.model_dump(by_alias=True))
    state["review_history"] = review_history

    # 判断是否通过
    pass_threshold = REVIEW_CONFIG.get("pass_score_threshold", 85)

    if review_result.passed and review_result.overall_score >= pass_threshold:
        # 通过
        state["needs_revision"] = False
        state["review_feedback"] = None
        logger.info(
            f"[review_node] 评审通过！{review_result.overall_score}分 → 进入排版"
        )
    else:
        # 未通过，准备修改
        state["needs_revision"] = True
        state["review_feedback"] = review_result.revision_suggestions
        state["revision_count"] = iteration + 1
        logger.info(
            f"[review_node] 评审未通过（{review_result.overall_score}分），"
            f"准备第{iteration + 1}轮修改"
        )

    state["current_node"] = "review_node"
    return state
