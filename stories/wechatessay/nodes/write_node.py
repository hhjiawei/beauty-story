"""
wechatessay.nodes.write_node

节点5: write_node — 逐段写作节点

【核心设计】逐段精修式写作：
1. 遍历 ArticlePlotNode.content_segments，每次只写一段
2. 每段写作时提供完整上下文窗口：
   - 全局写作上下文（标题、风格、受众）
   - 蓝图信息（情绪曲线、钩子策略、核心思路）
   - 搜索素材（数据、专家观点、案例，供引用）
   - 前一段已写正文（衔接用）
   - 前一段大纲（上文走向）
   - 当前段大纲（核心写作指令）
   - 后一段大纲（下文铺垫）
3. 每写完一段暂停，等待人工审核：
   - approve: 继续写
   - revise: 重写当前段（附修改意见）
   - back: 回退到上一段重写
4. 所有段完成后组装为 ArticleOutputNode，进入整体人工审核

依赖：
- Deep Agent (create_deep_agent)
- ArticlePlotNode, ArticleBlueprintNode, ArticleSearchNode 状态
- SEGMENT_WRITE_SYSTEM_PROMPT, ASSEMBLE_ARTICLE_SYSTEM_PROMPT


上下文窗口结构（每次写一段时传入 Agent）：
    1. 全局写作上下文（标题、核心观点、风格、受众）
    2. 蓝图信息（情绪曲线、钩子策略、核心思路、风险提示）
    3. 搜索素材（来源列表、专家观点、数据、案例、法规）
    4. 前一段已写正文（用于丝滑衔接）
    5. 前一段大纲（上文走向）
    6. ★ 当前段大纲（核心逻辑/情绪/修辞/字数/金句/素材来源）
    7. 后一段大纲（为下文埋引子）

核心函数：
函数	                        职责
write_node_async()	        主入口，三段状态机：segment → assembly → assembly_review
_build_segment_prompt()	    组装 7 层上下文的完整 prompt
_write_single_segment()	    调用 Deep Agent 写单段
_assemble_full_article()	所有段通过后组装 ArticleOutputNode
handle_segment_approve()	HITL approve：推进到下一段或进入组装
handle_segment_revise()	    HITL revise：重写当前段（注入修改意见）
handle_segment_back()	    HITL back：回退到上一段

逐段写作状态机：

    首次进入 → 初始化段追踪 → phase="segment", index=0
      ↓
    写第 i 段 → HITL(段级)等待用户
      ↓ approve  → index+=1, 还有段? → 继续写 : → 进入 assembly
      ↓ revise   → 保持 index, 注入 revision_notes → 重写当前段
      ↓ back     → index-=1, 清空上一段内容 → 回退重写
      ↓
    assembly → 组装 ArticleOutputNode → HITL(节点级)等待整体审核
      ↓ approve → phase="done", 进入 composition_node
      ↓ revise  → 回到 assembly 重新组装

"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from wechatessay.agents.backend import load_backend
from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.config import BACKEND_CONFIG, MEMORY_CONFIG, MODEL_CONFIG
from wechatessay.prompts.vx_prompt import (
    ASSEMBLE_ARTICLE_SYSTEM_PROMPT,
    SEGMENT_WRITE_SYSTEM_PROMPT,
)
from wechatessay.states.vx_state import (
    ArticleOutputNode,
    ArticlePlotNode,
    GoldenSentence,
    GraphState,
)
from wechatessay.tools.base_tools.base_tool import get_base_tools
from wechatessay.tools.mcp_tools.mcp_tool import get_total_tools
from wechatessay.utils.json_utils import parse_json_response


def _create_segment_writer_agent(tools: List[BaseTool]) -> Any:
    """创建逐段写作的 Deep Agent。"""
    backend = load_backend()
    mm = get_memory_manager()
    memory_context = mm.build_memory_context("逐段写作", top_k=3)

    system_prompt = (
        "你是一名逐段精修式公众号写手。每次只写一段，"
        "但必须在全文上下文中精确打磨当前段落。"
    )
    if memory_context:
        system_prompt = f"{memory_context}\n\n{system_prompt}"

    memory_files = []
    mem_file = Path(MEMORY_CONFIG["long_term_file"])
    if mem_file.exists():
        memory_files.append(str(mem_file))

    return create_deep_agent(
        model=MODEL_CONFIG.get("writing_model", MODEL_CONFIG["default_model"]),
        tools=tools,
        system_prompt=system_prompt,
        backend=backend,
        memory=memory_files,
        name="segment_writer",
    )


def _create_assembler_agent(tools: List[BaseTool]) -> Any:
    """创建组装文章的 Deep Agent。"""
    backend = load_backend()
    return create_deep_agent(
        model=MODEL_CONFIG.get("review_model", MODEL_CONFIG["default_model"]),
        tools=tools,
        system_prompt=ASSEMBLE_ARTICLE_SYSTEM_PROMPT,
        backend=backend,
        name="article_assembler",
    )


def _format_global_context(plot: ArticlePlotNode) -> str:
    """格式化全局写作上下文。"""
    ctx = plot.writing_context
    gs = ctx.global_style
    return f"""
【文章标题】{ctx.article_title}
【核心观点】{ctx.core_idea}
【目标受众】{ctx.target_audience}
【语调】{gs.tone}
【语言约束】{gs.language_requirement}
【风格样板句】{json.dumps(gs.example_sentences, ensure_ascii=False)}
"""


def _format_blueprint_context(blueprint: Optional[Any]) -> str:
    """格式化蓝图上下文（情绪曲线、钩子策略等）。"""
    if not blueprint:
        return "【蓝图】暂无"
    plan = blueprint.writing_plan
    return f"""
【核心创作思路】{plan.core_idea}
【引子设计】{plan.lead_in}
【文章线索】{json.dumps(plan.clues, ensure_ascii=False)}
【情绪曲线设计】{blueprint.emotional_arc_design}
【钩子策略】{json.dumps(blueprint.hook_strategy, ensure_ascii=False)}
【互动设计】{blueprint.interactive_design}
【写作方向】{json.dumps(plan.writing_direction, ensure_ascii=False)}
【风险提示】{json.dumps(plan.risk_notes, ensure_ascii=False)}
"""


def _format_search_context(search_result: Optional[Any]) -> str:
    """格式化搜索素材上下文（可引用内容）。"""
    if not search_result:
        return "【搜索素材】暂无"

    sources = []
    for s in search_result.search_sources:
        sources.append(
            f"  - [{s.platform}] {s.title} (可信度:{s.credibility_score}/5)\n"
            f"    {s.content_summary[:150]}..."
        )

    expert_quotes = search_result.expert_quotes or []
    data_supps = search_result.data_supplements or []
    related = search_result.related_cases or []
    legal = search_result.legal_policy_references or []

    parts = ["【搜索素材 — 可供引用的内容】"]
    if sources:
        parts.append("来源列表:\n" + "\n".join(sources[:8]))  # 最多8条
    if expert_quotes:
        parts.append(f"专家观点: {json.dumps(expert_quotes[:5], ensure_ascii=False)}")
    if data_supps:
        parts.append(f"数据补充: {json.dumps(data_supps[:5], ensure_ascii=False)}")
    if related:
        parts.append(f"同类案例: {json.dumps(related[:3], ensure_ascii=False)}")
    if legal:
        parts.append(f"法规引用: {json.dumps(legal[:3], ensure_ascii=False)}")

    return "\n".join(parts)


def _format_segment_outline(seg: Any, label: str) -> str:
    """格式化单段大纲。"""
    gs_req = seg.gold_sentence_requirement
    wc = seg.word_count_range
    return f"""
{label}
- 类型: {seg.segment_type} | 小标题: {seg.section_title or '无'}
- 核心逻辑: {seg.core_logic}
- 必须包含的信息: {json.dumps(seg.key_information, ensure_ascii=False)}
- 情绪目标: {seg.emotional_objective}
- 修辞手法: {seg.rhetorical_device}
- 金句预留: 位置={gs_req.position}, 主题={gs_req.theme}
- 字数范围: {wc.min}-{wc.max}字
- 素材来源: {json.dumps(seg.material_sources, ensure_ascii=False) or '无'}
- 向下过渡: {seg.transition_to_next or '无'}
"""


def _build_segment_prompt(
        state: GraphState,
        segment_index: int,
) -> str:
    """
    构建逐段写作的完整上下文 Prompt。

    包含：全局上下文 + 蓝图 + 搜索素材 + 前一段正文 + 三段大纲（前/当前/后）
    """
    plot = state["plot_result"]
    blueprint = state.get("blueprint_result")
    search = state.get("search_result")
    segments = plot.content_segments
    segment_contents = state.get("segment_contents", [])

    seg = segments[segment_index]
    total = len(segments)

    # 1. 全局上下文
    global_ctx = _format_global_context(plot)

    # 2. 蓝图
    blueprint_ctx = _format_blueprint_context(blueprint)

    # 3. 搜索素材
    search_ctx = _format_search_context(search)

    # 4. 前一段已写正文
    prev_content = ""
    if segment_index > 0 and segment_index - 1 < len(segment_contents):
        prev_text = segment_contents[segment_index - 1]
        if prev_text:
            prev_content = f"""
【前一段已写正文】（请承接这段的结尾，丝滑过渡）
```
{prev_text[:500]}
```
"""

    # 5. 三段大纲
    outlines = []
    if segment_index > 0:
        outlines.append(_format_segment_outline(segments[segment_index - 1], f"【第{segment_index}段大纲 — 前一段】"))
    outlines.append(_format_segment_outline(seg, f"【第{segment_index + 1}段大纲 — ★ 当前要写的段落 ★】"))
    if segment_index < total - 1:
        outlines.append(_format_segment_outline(segments[segment_index + 1], f"【第{segment_index + 2}段大纲 — 后一段】"))

    # 组装完整 prompt
    system_prompt = SEGMENT_WRITE_SYSTEM_PROMPT.format(
        current_index=segment_index + 1,
        total_count=total,
    )

    user_content = f"""{global_ctx}

{blueprint_ctx}

{search_ctx}

{prev_content}

{"\n---\n".join(outlines)}

请只输出第 {segment_index + 1} 段的 JSON，不要输出其他内容。
"""
    return system_prompt, user_content


async def _write_single_segment(
        state: GraphState,
        segment_index: int,
        agent: Any,
) -> Dict[str, Any]:
    """调用 Deep Agent 写单一段落。"""
    system_prompt, user_content = _build_segment_prompt(state, segment_index)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    # 如果有修改意见，追加修改指令
    revision = state.get("revision_notes")
    if revision:
        messages.append({
            "role": "user",
            "content": f"【修改要求】\n{revision}\n\n请根据以上修改意见重新写第 {segment_index + 1} 段。",
        })

    result = await agent.ainvoke({"messages": messages})
    response_content = result["messages"][-1].content if result.get("messages") else ""

    # 解析 JSON
    parsed = parse_json_response(response_content)
    if not isinstance(parsed, dict):
        return {
            "segmentIndex": segment_index,
            "content": response_content[:2000] or "（解析失败，请重试）",
            "goldenSentences": [],
            "wordCount": 0,
            "sourcesCited": [],
            "transitionPreview": "",
        }

    # 确保必要字段存在
    return {
        "segmentIndex": parsed.get("segmentIndex", segment_index + 1),
        "content": parsed.get("content", ""),
        "goldenSentences": parsed.get("goldenSentences", []),
        "wordCount": parsed.get("wordCount", len(parsed.get("content", ""))),
        "sourcesCited": parsed.get("sourcesCited", []),
        "transitionPreview": parsed.get("transitionPreview", ""),
    }


async def _assemble_full_article(state: GraphState, agent: Any) -> ArticleOutputNode:
    """所有段落写完后，组装为 ArticleOutputNode。"""
    plot = state["plot_result"]
    segment_contents = state.get("segment_contents", [])
    segment_golden = state.get("segment_golden_sentences", [])

    full_text = "\n\n".join(segment_contents)

    # 构建 parts 列表
    parts = []
    for i, content in enumerate(segment_contents):
        if not content:
            continue
        golden = segment_golden[i] if i < len(segment_golden) else []
        parts.append({
            "partIndex": i + 1,
            "titleAlternatives": [plot.writing_context.article_title] if i == 0 else [],
            "content": content,
            "goldenSentences": golden,
            "shareTexts": [],  # 组装时再生成
            "readingTime": f"{max(1, len(content) // 300)}分钟",
            "rhythm": f"第{i + 1}段节奏",
        })

    # 调用 Agent 做最终组装（标题、转发语、SEO等）
    context = json.dumps({
        "fullText": full_text,
        "parts": parts,
        "plot": plot.model_dump(by_alias=True),
    }, ensure_ascii=False, indent=2)

    messages = [
        {
            "role": "user",
            "content": (
                f"所有段落已审核通过，请组装为完整文章。\n\n"
                f"{context}\n\n"
                f"请按 ASSEMBLE_ARTICLE_SYSTEM_PROMPT 的格式输出 JSON。"
            ),
        }
    ]

    result = await agent.ainvoke({"messages": messages})
    response_content = result["messages"][-1].content if result.get("messages") else ""

    try:
        parsed = parse_json_response(response_content)
        if isinstance(parsed, dict) and "parts" in parsed:
            return ArticleOutputNode.model_validate(parsed)
    except Exception:
        pass

    # Fallback：手动组装
    golden_sentences_all = []
    for i, golden_list in enumerate(segment_golden):
        for g in golden_list:
            golden_sentences_all.append({
                "position": f"第{i + 1}段",
                "text": g.get("text", ""),
                "highlightType": g.get("highlightType", "default"),
            })

    return ArticleOutputNode(
        parts=[{
            "partIndex": 1,
            "titleAlternatives": [plot.writing_context.article_title],
            "content": full_text,
            "goldenSentences": golden_sentences_all,
            "shareTexts": [],
            "readingTime": f"{max(1, len(full_text) // 300)}分钟",
            "rhythm": "逐段精修组装",
        }],
        full_text=full_text,
        metadata={
            "totalWordCount": len(full_text),
            "readingTime": f"{max(1, len(full_text) // 300)}分钟",
            "generatedAt": datetime.now().isoformat(),
        },
    )


# ═══════════════════════════════════════════════
# 核心入口函数
# ═══════════════════════════════════════════════
import asyncio
"""如果 write_node 本身是在一个已经运行的事件循环中被调用（例如 Jupyter Notebook、某些 Web 框架、或 LangGraph 的异步执行模式），
asyncio.run() 会抛出 RuntimeError: asyncio.run() cannot be called from a running event loop。
建议： 如果该节点可能在异步上下文中被调用，同步入口应改用："""
def write_node(state: GraphState) -> GraphState:
    try:
        loop = asyncio.get_running_loop()
        # 已在事件循环中，需要特殊处理（如使用 nest_asyncio 或重构为纯异步节点）
    except RuntimeError:
        return asyncio.run(write_node_async(state))


async def write_node_async(state: GraphState) -> GraphState:
    """
    write_node 异步执行入口。

    三种进入场景：
    1. 首次进入：初始化段追踪，开始写第 0 段
    2. HITL approve 后继续：写 current_segment_index 指定的段
    3. HITL back 回退：回退到上一段重写
    """
    plot = state.get("plot_result")
    if not plot:
        state["error_message"] = "缺少 plot_result"
        state["error_node"] = "write_node"
        return state

    segments = plot.content_segments
    total = len(segments)

    # ── 初始化段追踪（首次进入） ──
    phase = state.get("write_node_phase", "")
    if not phase:
        state["write_node_phase"] = "segment"
        state["current_segment_index"] = 0
        state["segment_contents"] = [""] * total
        state["segment_golden_sentences"] = [[] for _ in range(total)]
        state["segment_approved"] = [False] * total
        state["total_segments"] = total
        state["revision_notes"] = None
        phase = "segment"
        print(f"[write_node] 初始化逐段写作：共 {total} 段")

    current_idx = state.get("current_segment_index", 0)
    segment_contents = state.get("segment_contents", [])

    # ── 安全校验 ──
    if current_idx < 0:
        current_idx = 0
        state["current_segment_index"] = 0
    if current_idx >= total:
        phase = "assembly"

    # ── Phase: 逐段写作 ──
    if phase == "segment" and current_idx < total:
        print(f"[write_node] 正在写第 {current_idx + 1}/{total} 段...")

        # 准备工具 + Agent
        base_tools = await get_base_tools()
        mcp_tools = await get_total_tools()
        total_tools = list(base_tools) + list(mcp_tools)
        agent = _create_segment_writer_agent(total_tools)

        # 写当前段
        segment_result = await _write_single_segment(state, current_idx, agent)
        content = segment_result.get("content", "")
        golden = segment_result.get("goldenSentences", [])

        # 保存到状态
        segment_contents[current_idx] = content
        state["segment_contents"] = segment_contents
        state["segment_golden_sentences"][current_idx] = golden
        state["current_node"] = "write_node"
        state["node_status"]["write_node"] = "waiting_human"

        # 获取当前段大纲信息用于审核提示
        seg = segments[current_idx]

        # 设置段级 HITL
        state["pending_human_review"] = {
            "node": "write_node",
            "scope": "segment",  # 标记为段级审核（区别于节点级）
            "segment_index": current_idx,
            "segment_type": seg.segment_type,
            "total_segments": total,
            "content": {
                "segment_number": current_idx + 1,
                "segment_type": seg.segment_type,
                "section_title": seg.section_title,
                "core_logic": seg.core_logic,
                "content": content,
                "word_count": segment_result.get("wordCount", len(content)),
                "golden_sentences": golden,
                "sources_cited": segment_result.get("sourcesCited", []),
                "transition_preview": segment_result.get("transitionPreview", ""),
            },
            "instruction": (
                f"第 {current_idx + 1}/{total} 段写作完成。\n"
                f"【本段要求】{seg.core_logic} | 情绪:{seg.emotional_objective} | "
                f"字数:{seg.word_count_range.min}-{seg.word_count_range.max}\n"
                f"请检查：1)内容是否符合大纲要求 2)与上段衔接是否自然 "
                f"3)是否为下段做了过渡 4)引用素材是否恰当 5)是否有AI感\n"
                f"决策：approve=通过继续 | revise=修改当前段(请附意见) | "
                f"back=回退到上一段"
            ),
        }

        # 清理修改意见（已消费）
        state["revision_notes"] = None

        print(f"[write_node] 第 {current_idx + 1} 段完成（{len(content)}字），等待人工审核")
        return state

    # ── Phase: 组装全文 ──
    elif phase in ("assembly", "segment") and current_idx >= total:
        print(f"[write_node] 所有 {total} 段已审核通过，组装全文...")

        base_tools = get_base_tools()
        mcp_tools = await get_total_tools()
        total_tools = list(base_tools) + list(mcp_tools)
        agent = _create_assembler_agent(total_tools)

        article = await _assemble_full_article(state, agent)

        state["article_output"] = article
        state["write_node_phase"] = "assembly_review"
        state["current_node"] = "write_node"
        state["node_status"]["write_node"] = "waiting_human"

        # 设置整体 HITL
        state["pending_human_review"] = {
            "node": "write_node",
            "scope": "node",  # 节点级审核（整体文章）
            "content": article.model_dump(by_alias=True),
            "instruction": (
                "全文已组装完成。请进行整体审核：\n"
                "1) 标题是否吸引人 2) 全文节奏是否流畅 3) 段落衔接是否自然\n"
                "4) 金句分布是否合理 5) 整体是否有AI感 6) 转发语是否合适\n"
                "决策：approve=通过，进入排版 | revise=修改某段(请指定段落和意见) | "
                "retry=重新组装"
            ),
        }

        print(f"[write_node] 全文组装完成（{article.metadata.get('totalWordCount', 0)}字），等待整体审核")
        return state

    # ── Phase: 整体审核通过 ──
    elif phase == "assembly_review":
        # 用户已通过整体审核
        state["write_node_phase"] = "done"
        state["node_status"]["write_node"] = "completed"
        print("[write_node] 整体审核通过，完成！")
        return state

    return state


# ═══════════════════════════════════════════════
# HITL 处理辅助函数（供 graph.py 调用）
# ═══════════════════════════════════════════════

def handle_segment_approve(state: GraphState) -> GraphState:
    """
    处理段级 approve 决策。

    - 标记当前段已批准
    - 推进到下一段
    - 如果全部完成，切换到 assembly phase
    """
    idx = state.get("current_segment_index", 0)
    total = state.get("total_segments", 0)
    approved = state.get("segment_approved", [])

    if idx < len(approved):
        approved[idx] = True
    state["segment_approved"] = approved

    # 推进下一段
    next_idx = idx + 1
    state["current_segment_index"] = next_idx

    if next_idx >= total:
        # 全部写完，进入组装阶段
        state["write_node_phase"] = "assembly"
        print(f"[write_node HITL] 第 {idx + 1} 段通过，全部 {total} 段完成，进入组装")
    else:
        print(f"[write_node HITL] 第 {idx + 1} 段通过，继续写第 {next_idx + 1} 段")

    return state


def handle_segment_revise(state: GraphState, comment: str) -> GraphState:
    """
    处理段级 revise 决策。

    - 保持 current_segment_index 不变（重写当前段）
    - 设置 revision_notes
    """
    state["revision_notes"] = comment
    # phase 保持 "segment"，index 不变，下次进入会重写
    print(f"[write_node HITL] 第 {state['current_segment_index'] + 1} 段需修改: {comment[:50]}...")
    return state


def handle_segment_back(state: GraphState) -> GraphState:
    """
    处理段级 back 决策。

    - 回退到上一段
    - 如果已经在第 0 段，提示无法回退
    """
    idx = state.get("current_segment_index", 0)
    if idx > 0:
        state["current_segment_index"] = idx - 1
        state["revision_notes"] = "回退到上一段重新写作"
        # 清空上一段的内容，重新写
        segment_contents = state.get("segment_contents", [])
        if idx - 1 < len(segment_contents):
            segment_contents[idx - 1] = ""
        state["segment_contents"] = segment_contents
        state["segment_approved"][idx - 1] = False
        print(f"[write_node HITL] 回退到第 {idx} 段重新写作")
    else:
        # 已经是第一段，无法回退
        state["revision_notes"] = "已是第一段，无法继续回退"
        print("[write_node HITL] 已在第 1 段，无法回退")
    return state