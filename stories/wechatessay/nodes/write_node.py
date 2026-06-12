"""
wechatessay.nodes.write_node

节点5: write_node — 串行全文写作节点

【串行流程】
    第0轮: 随机选模型A → get_model_instance(A) → ChatOpenAI实例 → 写作
        → review_node(模型B≠A评审) → 需修改
    第1轮: 用模型B(上轮评审) → get_model_instance(B) → 写作
        → review_node(模型C≠B评审) → 通过

【模型引用】代码中只传模型名称（如 "deepseek"），
实际实例通过 get_model_instance(name) 从 MODEL_REGISTRY 获取。
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from typing import Any

from deepagents import create_deep_agent

from wechatessay.agents.backend import load_backend
from wechatessay.config import (
    WRITER_CONFIG,
    get_model_instance,
)
from wechatessay.prompts.vx_prompt import FULL_WRITE_SYSTEM_PROMPT
from wechatessay.states.vx_state import (
    ArticleOutputNode,
    GraphState,
    WritingRecord,
)
from wechatessay.utils.json_utils import parse_json_response

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
# 新增：结果提取  【新增位置】
# ═══════════════════════════════════════════════
def _extract_final_ai_content(result: dict) -> str:
    """
    从 Agent 返回的 messages 列表中提取最终排版结果。

    问题场景：
        messages = [..., 最终结果(AIMessage), ToolMessage, 空AIMessage]
        直接取 [-1] 会得到空内容，导致解析失败。

    策略：
        1. 从后向前遍历，跳过 ToolMessage（通过 tool_call_id / name 识别）
        2. 优先返回包含排版关键字段（formattedArticle 等）的内容
        3. 兜底返回最后一个非空 AI content
    """
    messages = result.get("messages", [])
    if not messages:
        return ""

    candidates = []

    for msg in reversed(messages):
        # --- 跳过工具消息 ---
        # ToolMessage 通常有 tool_call_id 或 name 属性
        if hasattr(msg, "tool_call_id"):
            continue

        # --- 提取 content ---
        content = getattr(msg, "content", None)
        if content is None:
            continue

        text = str(content).strip()
        if not text:
            continue

        # --- 快速命中：包含排版结果关键字段，直接返回 ---
        if any(keyword in text for keyword in (
                "parts",
                "fullText",
                "metadata",
                "seoInfo",
        )):
            return text

        candidates.append(text)

    # --- 兜底：返回最后一个非空且非工具的 AI content ---
    return candidates[0] if candidates else ""

def _select_writer_model(state: GraphState) -> str:
    """
    选择本轮写作模型名称。
    - 首次（iteration=0）：从 WRITER_CONFIG 随机选
    - 修改轮次：使用上轮 reviewer_model 名称
    """
    iteration = state.get("iteration", 0)
    model_names = WRITER_CONFIG.get("models", [])

    if not model_names:
        raise ValueError("WRITER_CONFIG['models'] 为空")

    if iteration == 0:
        name = random.choice(model_names)
        logger.info(f"[write_node] 首次写作，随机选择: {name}")
    else:
        name = state.get("reviewer_model", "")
        if not name:
            name = random.choice(model_names)
            logger.info(f"[write_node] 第{iteration}轮，reviewer_model 为空，随机选: {name}")
        else:
            logger.info(f"[write_node] 第{iteration}轮，使用上轮评审模型: {name}")

    return name


def _format_context(state: GraphState) -> str:
    """组装写作上下文（大纲+蓝图+素材）。"""
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
    """构建写作任务。评审意见放最前面。"""
    context = _format_context(state)
    review_feedback = state.get("review_feedback")
    iteration = state.get("iteration", 0)

    parts = []

    if review_feedback and iteration > 0:

        article = state.get("article_output", "")

        full_text = article.full_text

        parts.append(
            f"【重要：第{iteration}轮修改要求】\n"
            f"你正在根据评审意见修改文章。以下是评审专家的详细修改意见，"
            f"你必须严格根据这些意见修改，写得好的部分保留不动。\n\n"
            f"{review_feedback}\n\n"
            f"══════════════════════════════════════\n"
            f"以上修改意见优先级最高。请输出修改后的完整文章。\n\n"
            f"要修改的内容为: {full_text}\n\n"
        )
        logger.info(f"[write_node] 已注入评审意见（{len(review_feedback)}字）")
    else:
        parts.append("【首次写作】请一次性生成完整的公众号文章全文。\n\n")

    parts.append(context)

    parts.append(
        "\n\n请按 ArticleOutputNode 的 JSON 结构输出完整文章。"
        "不要输出任何其他描述文字。"
        "结果不许落盘,不许写入其他文件，后续节点需要使用生成的结构，结果必须包含在内"
        "结果不允许是除了内容外的任何东西，例如交付摘要之类的"
        "结果一定要 ArticleOutputNode 的JSON结构，不许落盘，不许保存到文件夹，不许擅自加描述、总结等其他内容，你输出的结果只有 ArticleOutputNode 的JSON结构"
        "只要产生 ArticleOutputNode 的JSON结构必须在最后一个AIMessage中，后续不许产生任何message 不许产生toolMessage 和其他aiMessage"
        "任务完成后，确认下是否产生用户想要的实际内容，而不是概括的内容"
    )

    return "".join(parts)


def write_node(state: GraphState) -> GraphState:
    """同步入口包装。"""
    import asyncio
    return asyncio.run(write_node_async(state))


async def write_node_async(state: GraphState) -> GraphState:
    """单模型串行全文写作。"""
    plot = state.get("plot_result")
    if not plot:
        state["error_message"] = "缺少 plot_result"
        state["error_node"] = "write_node"
        return state

    # 选择写作模型名称
    model_name = _select_writer_model(state)
    iteration = state.get("iteration", 0)

    # 通过名称获取 ChatOpenAI 实例
    try:
        model_instance = get_model_instance(model_name)
    except KeyError as e:
        logger.error(f"[write_node] 模型解析失败: {e}")
        state["error_message"] = str(e)
        state["error_node"] = "write_node"
        return state

    logger.info(f"[write_node] ===== 第{iteration}轮写作开始，模型: {model_name} =====")
    state["writer_model"] = model_name

    # 创建 Agent（直接传 ChatOpenAI 实例）
    try:
        backend = load_backend()
        agent = create_deep_agent(
            model=model_instance,
            tools=[],
            system_prompt=FULL_WRITE_SYSTEM_PROMPT,
            backend=backend,
            name=f"writer_{model_name}_r{iteration}",
            memory=["/memories/thought.md", "/memories/style.md", "/memories/process.md"]
        )
    except Exception as e:
        logger.error(f"[write_node] 创建 Agent 失败: {e}")
        state["error_message"] = f"创建写作 Agent 失败: {e}"
        state["error_node"] = "write_node"
        return state

    # 调用写作   评审后得写作 是根据大纲+评审结果 重新根据大纲写
    task_content = _build_write_task(state)
    try:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": task_content}]})
        # response_content = result["messages"][-1].content if result.get("messages") else ""

        response_content = _extract_final_ai_content(result)
    except Exception as e:
        logger.error(f"[write_node] 第{iteration}轮调用失败: {e}")
        state["error_message"] = f"写作失败: {e}"
        state["error_node"] = "write_node"
        return state

    # 解析文章
    article = None
    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict) and "parts" in parsed:
            article = ArticleOutputNode.model_validate(parsed)
    except Exception as e:
        logger.warning(f"[write_node] 解析失败: {e}")

    if not article:
        article = ArticleOutputNode(
            parts=[{
                "partIndex": 1,
                "titleAlternatives": ["生成失败"],
                "content": response_content if response_content else "（失败）",
                "goldenSentences": [],
                "shareTexts": [],
                "readingTime": "1分钟",
                "rhythm": "失败",
            }],
            full_text=response_content or "",
            metadata={
                "totalWordCount": len(response_content) if response_content else 0,
                "readingTime": "1分钟",
                "generatedAt": datetime.now().isoformat(),
            },
        )

    # 保存
    state["article_output"] = article
    state["current_node"] = "write_node"

    word_count = article.metadata.get("totalWordCount", 0) if article.metadata else 0
    title = article.parts[0].title_alternatives[0] if article.parts else ""
    has_feedback = bool(state.get("review_feedback")) and iteration > 0

    record = WritingRecord(
        iteration=iteration,
        modelUsed=model_name,
        selfScore=0,
        wordCount=word_count,
        title=title,
        hasReviewFeedback=has_feedback,
    )
    writing_history = state.get("writing_history", [])
    writing_history.append(record.model_dump(by_alias=True))
    state["writing_history"] = writing_history

    logger.info(f"[write_node] 第{iteration}轮完成: {model_name}, {word_count}字")

    return state