"""
wechatessay.nodes.review_node

节点5-Review: review_node — 串行评审节点

【串行流程】每次用一个模型评审，评审模型≠写作模型：

    write(模型A) → review(模型B≠A评审) → 需修改
    write(模型B) → review(模型C≠B评审) → 通过 → composition

【模型引用】代码中只传模型名称，
实际实例通过 get_model_instance(name) 从 MODEL_REGISTRY 获取。
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Optional

from deepagents import create_deep_agent

from wechatessay.agents.backend import load_backend
from wechatessay.config import (
    MAX_REVISION_ROUNDS,
    REVIEW_CONFIG,
    get_model_instance,
)
from wechatessay.prompts.vx_prompt import REVIEW_SYSTEM_PROMPT
from wechatessay.states.vx_state import (
    ArticleOutputNode,
    GraphState,
    ReviewRecord,
    ReviewResult,
)
from wechatessay.utils.json_utils import parse_json_response

logger = logging.getLogger(__name__)


def _select_reviewer_model(state: GraphState) -> str:
    """
    选择评审模型名称。必须与 writer_model 不同。
    """
    writer_model = state.get("writer_model", "")
    model_names = REVIEW_CONFIG.get("models", [])

    if not model_names:
        raise ValueError("REVIEW_CONFIG['models'] 为空")

    candidates = [m for m in model_names if m != writer_model]

    if not candidates:
        from wechatessay.config import WRITER_CONFIG
        writer_models = WRITER_CONFIG.get("models", [])
        candidates = [m for m in writer_models if m != writer_model]

    if not candidates:
        raise ValueError(f"没有可用评审模型（都与 '{writer_model}' 相同）")

    return random.choice(candidates)


def _build_review_task(article: ArticleOutputNode, writer_model: str) -> str:
    """构建评审任务。"""
    article_text = article.full_text or ""
    title = article.parts[0].title_alternatives[0] if article.parts else "未命名"
    meta = article.metadata or {}

    return f"""请对以下公众号文章进行严格评审。

【文章信息】
- 标题：{title}
- 字数：{meta.get('totalWordCount', 0)}字
- 写作模型：{writer_model}

【全文内容】
{article_text}

注意：
1 不要输出任何其他描述文字。
2 结果不许落盘,不许写入其他文件，后续节点需要使用生成的结构，结果必须包含在内
3 结果不允许是除了内容外的任何东西，例如交付摘要之类的，禁止将结果落盘到 xx.json文件等行为，内容必须放在最后一个AIMessage中


"""


def _parse_review_response(
    response_content: str,
    iteration: int,
    model: str,
) -> Optional[ReviewResult]:
    """解析评审响应。"""
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
        logger.warning(f"[review_node] 解析失败: {e}")
        return None


def review_node(state: GraphState) -> GraphState:
    """同步入口包装。"""
    import asyncio
    return asyncio.run(review_node_async(state))


async def review_node_async(state: GraphState) -> GraphState:
    """串行评审主逻辑。"""
    article = state.get("article_output")
    if not article:
        state["error_message"] = "缺少 article_output"
        state["error_node"] = "review_node"
        return state

    iteration = state.get("iteration", 0)
    writer_model = state.get("writer_model", "")

    if iteration >= MAX_REVISION_ROUNDS:
        logger.warning(f"[review_node] 已达最大轮次({MAX_REVISION_ROUNDS})，强制通过")
        state["needs_revision"] = False
        state["review_feedback"] = None
        state["current_node"] = "review_node"
        return state

    # 选择评审模型名称
    model_name = _select_reviewer_model(state)
    state["reviewer_model"] = model_name

    # 获取 ChatOpenAI 实例
    try:
        model_instance = get_model_instance(model_name)
    except KeyError as e:
        logger.error(f"[review_node] 模型解析失败: {e}")
        state["error_message"] = str(e)
        state["error_node"] = "review_node"
        return state

    logger.info(
        f"[review_node] ===== 第{iteration}轮评审开始 ===== "
        f"写作: {writer_model} → 评审: {model_name}"
    )

    # 调用评审 Agent
    try:
        backend = load_backend()
        agent = create_deep_agent(
            model=model_instance,
            tools=[],
            system_prompt=REVIEW_SYSTEM_PROMPT,
            backend=backend,
            memory=["/memories/thought.md", "/memories/selfCheck.md"],
            name=f"reviewer_{model_name}_r{iteration}",
        )
        task_content = _build_review_task(article, writer_model)
        result = await agent.ainvoke({"messages": [{"role": "user", "content": task_content}]})
        response_content = result["messages"][-1].content if result.get("messages") else ""
    except Exception as e:
        logger.error(f"[review_node] 调用失败: {e}")
        state["needs_revision"] = True
        state["review_feedback"] = f"评审出错: {str(e)[:200]}"
        state["current_node"] = "review_node"
        return state

    # 解析
    review_result = _parse_review_response(response_content, iteration, model_name)

    if not review_result:
        logger.warning("[review_node] 评审结果解析失败")
        state["needs_revision"] = True
        state["review_feedback"] = "评审结果解析失败，请检查格式并重写。"
        state["current_node"] = "review_node"
        return state

    state["review_result"] = review_result

    # 保存历史
    record = ReviewRecord(
        iteration=iteration,
        modelUsed=model_name,
        overallScore=review_result.overall_score,
        passed=review_result.passed,
        strengths=review_result.strengths,
        issues=review_result.issues,
        revisionSuggestions=review_result.revision_suggestions,
    )
    review_history = state.get("review_history", [])
    review_history.append(record.model_dump(by_alias=True))
    state["review_history"] = review_history

    # 判断
    pass_threshold = REVIEW_CONFIG.get("pass_score_threshold", 80)

    if review_result.overall_score >= pass_threshold:
        state["needs_revision"] = False
        state["review_feedback"] = None
        logger.info(f"[review_node] 第{iteration}轮通过！{model_name}: {review_result.overall_score}分")
    else:
        state["needs_revision"] = True
        state["review_feedback"] = review_result.revision_suggestions
        state["iteration"] = iteration + 1
        logger.info(
            f"[review_node] 第{iteration}轮未通过（{review_result.overall_score}分），"
            f"下轮用 {model_name} 写作"
        )

    state["current_node"] = "review_node"
    return state