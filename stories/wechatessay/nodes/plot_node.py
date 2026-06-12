"""
wechatessay.nodes.plot_node

节点4: plot_node — 大纲节点

职责：
1. 整合前面所有节点的内容
2. 生成详细的公众号文章大纲
3. 每段包含逻辑、情绪、修辞、金句等详细指令
4. 需要人工审核
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from wechatessay.agents.backend import load_backend
from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.config import get_model_instance, BACKEND_CONFIG, MEMORY_CONFIG, MODEL_CONFIG
from wechatessay.prompts.vx_prompt import PLOT_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import ArticlePlotNode, GraphState
from wechatessay.tools.base_tools.base_tool import get_base_tools
from wechatessay.tools.mcp_tools.mcp_tool import get_total_tools
from wechatessay.utils.json_utils import parse_json_response

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
                "writingContext",
                "contentSegments",
                "globalChecklist",
                "articleMetadata",
                "seoConfig",
                "viralPrediction",
        )):
            return text

        candidates.append(text)

    # --- 兜底：返回最后一个非空且非工具的 AI content ---
    return candidates[0] if candidates else ""

def _create_plot_agent(tools: list[BaseTool]) -> Any:
    """创建 plot_node 的 Deep Agent。"""
    backend = load_backend()
    mm = get_memory_manager()
    memory_context = mm.build_memory_context("大纲设计")

    system_prompt = PLOT_NODE_SYSTEM_PROMPT
    if memory_context:
        system_prompt = f"{memory_context}\n\n{system_prompt}"

    memory_files = []
    mem_file = Path(MEMORY_CONFIG["long_term_file"])
    if mem_file.exists():
        memory_files.append(str(mem_file))

    return create_deep_agent(
        model=get_model_instance(MODEL_CONFIG.get("writing_model")),
        tools=tools,
        system_prompt=system_prompt,
        backend=backend,
        memory=["/memories/thought.md", "/memories/style.md"],
        name="plot_designer",
    )


def _fill_segment_defaults(data: dict) -> dict:
    """
    填充 ContentSegment 中可能缺失的必填字段。
    LLM 经常漏掉 goldSentenceRequirement、wordCountRange 等嵌套对象，
    在 model_validate 前自动补全，避免 Pydantic validation error。
    """
    segments = data.get("contentSegments") or data.get("content_segments", [])
    for seg in segments:
        # goldSentenceRequirement 必填但 LLM 常漏
        gsr = seg.get("goldSentenceRequirement") or seg.get("gold_sentence_requirement")
        if not gsr:
            seg["goldSentenceRequirement"] = {"position": "none", "theme": ""}

        # wordCountRange 必填但 LLM 常漏
        wcr = seg.get("wordCountRange") or seg.get("word_count_range")
        if not wcr:
            seg["wordCountRange"] = {"min": 200, "max": 500}

        # transitionToNext 可选，但若缺失补空字符串
        if "transitionToNext" not in seg and "transition_to_next" not in seg:
            seg["transitionToNext"] = None

        # sectionTitle 可选
        if "sectionTitle" not in seg and "section_title" not in seg:
            seg["sectionTitle"] = None
    return data


async def _generate_plot(
    blueprint: dict,
    search_result: dict,
    agent: Any,
) -> ArticlePlotNode:
    """生成文章大纲。"""
    context = json.dumps({
        "blueprint": blueprint,
        "search_result": search_result,
    }, ensure_ascii=False, indent=2)

    messages = [
        {
            "role": "user",
            "content": (
                f"基于以下写作蓝图和搜索结果，设计详细的公众号文章大纲。\n\n"
                f"{context}\n\n"
                f"请严格按 JSON 格式输出 ArticlePlotNode 结构，"
                f"结果一定要 ArticlePlotNode 的JSON结构，不许落盘，不许保存到文件夹，不许擅自加描述、总结等其他内容，你输出的结果只有ArticlePlotNode的JSON结构"
                f"只要产生ArticlePlotNode 的JSON结构必须在最后一个AIMessage中，后续不许产生任何message 不许产生toolMessage 和其他aiMessage"
            ),
        }
    ]

    result = await agent.ainvoke({"messages": messages})
    # response_content = result["messages"][-1].content if result.get("messages") else ""
    response_content = _extract_final_ai_content(result)
    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict):
            plot_data = parsed.get("plot_result") or parsed
            plot_data = _fill_segment_defaults(plot_data)  # 填充缺失字段
            return ArticlePlotNode.model_validate(plot_data)
    except Exception as e:
        print(f"[plot_node] 解析大纲失败: {e}")

    return ArticlePlotNode(
        writing_context={
            "articleTitle": "", "coreIdea": "", "targetAudience": "",
            "globalStyle": {"tone": "", "languageRequirement": ""},
        },
        content_segments=[],
        global_checklist=[],
    )


async def plot_node_async(state: GraphState) -> GraphState:
    """
    plot_node 异步执行入口。
    核心修复：使用 await agent.ainvoke() 而非 agent.invoke()。
    """
    blueprint = state.get("blueprint_result")
    search_result = state.get("search_result")

    if not blueprint:
        state["error_message"] = "缺少 blueprint_result"
        state["error_node"] = "plot_node"
        return state

    print(f"[plot_node] 开始生成大纲")

    base_tools = await get_base_tools()
    mcp_tools = await get_total_tools()
    total_tools = list(base_tools) + list(mcp_tools)

    agent = _create_plot_agent(total_tools)

    plot_result = await _generate_plot(
        blueprint.model_dump(by_alias=True),
        search_result.model_dump(by_alias=True) if search_result else {},
        agent,
    )

    state["plot_result"] = plot_result
    state["current_node"] = "plot_node"
    state["node_status"]["plot_node"] = "completed"  # [TEST] 自动通过


    mm = get_memory_manager()
    mm.add_short_term(
        f"plot_{datetime.now().isoformat()}",
        {"title": plot_result.writing_context.article_title, "segments": len(plot_result.content_segments)},
    )

    print(f"[plot_node] 完成: {len(plot_result.content_segments)} 段")
    return state


def plot_node(state: GraphState) -> GraphState:
    """plot_node 同步入口包装。"""
    import asyncio
    return asyncio.run(plot_node_async(state))