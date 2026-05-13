"""
Plot Node - 大纲节点

职责：
1. 基于写作蓝图设计详细文章大纲
2. 规划每段内容、情绪、修辞
3. 预留金句位置
4. 人机协同：需要人工检查

Agent 模式：NodeAgent 自动管理工具调用循环和记忆
"""

import json
from typing import Dict, Any

from wechatessay.agents.agent_factory import get_node_agent, discover_tools_for_node
from wechatessay.states.vx_state import GraphState, ArticlePlotNode
from wechatessay.prompts import vx_prompt
from wechatessay.utils.json_utils import parse_json_response
from wechatessay.config import PLOT_LLM_MODEL, HUMAN_IN_THE_LOOP, MAX_REVISION_ROUNDS


def plot_node(state: GraphState, **kwargs) -> Dict[str, Any]:
    """大纲节点"""
    print("\n" + "=" * 50)
    print("📋 [plot_node] 开始设计文章大纲")
    print("=" * 50)

    backend = kwargs.get("backend")
    store = kwargs.get("store")
    thread_id = kwargs.get("thread_id", "default")

    blueprint = state.get("blueprint_result", {})
    human_feedback = state.get("human_feedback")
    revision_count = state.get("revision_count", 0)

    tools = discover_tools_for_node("plot_node")
    print(f"  🔧 plot_node 可用工具: {[t.name for t in tools]}")

    if human_feedback and human_feedback.lower() not in ["ok", "满意", "continue"]:
        if revision_count >= MAX_REVISION_ROUNDS:
            print(f"⚠️ 达到最大修改轮次 ({MAX_REVISION_ROUNDS})")
            return {
                "plot_result": state.get("plot_result", {}),
                "awaiting_human": False,
                "human_feedback": None,
                "current_node": "plot_node"
            }

        print(f"📝 收到修改意见（第{revision_count}轮）: {human_feedback[:100]}...")
        plot = _revise_plot(
            original_plot=state.get("plot_result", {}),
            human_feedback=human_feedback,
            blueprint=blueprint,
            revision_history=state.get("plot_result", {}).get("revisionHistory", []),
            backend=backend,
            store=store,
            thread_id=thread_id,
        )
    else:
        plot = _generate_plot(
            blueprint=blueprint,
            backend=backend,
            store=store,
            thread_id=thread_id,
        )

    if not plot:
        return {"error_message": "大纲生成失败", "should_continue": False}

    # 显示摘要
    wc = plot.get("writingContext", {})
    print(f"   - 标题: {wc.get('articleTitle', 'N/A')[:40]}")
    print(f"   - 核心观点: {wc.get('coreIdea', 'N/A')[:50]}")
    segments = plot.get("contentSegments", [])
    print(f"   - 段落数: {len(segments)}")
    for seg in segments:
        print(f"     [{seg.get('segmentType', '?')}] {seg.get('sectionTitle', '无标题')}")

    if HUMAN_IN_THE_LOOP and not human_feedback:
        print(vx_prompt.HUMAN_FEEDBACK_PROMPT.format(
            content_display=_format_plot_for_display(plot)
        ))
        return {
            "plot_result": plot,
            "awaiting_human": True,
            "current_node": "plot_node"
        }

    return {
        "plot_result": plot,
        "awaiting_human": False,
        "human_feedback": None,
        "current_node": "plot_node"
    }


def _generate_plot(
    blueprint: Dict,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """生成大纲"""
    agent = get_node_agent(
        node_name="plot_node",
        system_prompt=vx_prompt.PLOT_SYSTEM_PROMPT,
        llm_model=PLOT_LLM_MODEL,
        temperature=0.7,
        max_tokens=4000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    json_schema = vx_prompt.get_json_schema_prompt(ArticlePlotNode)

    user_prompt = vx_prompt.PLOT_USER_PROMPT_TEMPLATE.format(
        blueprint=json.dumps(blueprint, ensure_ascii=False, indent=2)[:3000],
        memories="（暂无用户习惯记忆）",
        word_count_min=1500,
        word_count_max=3000,
        json_schema=json_schema
    )

    response = agent.invoke(user_prompt, max_iterations=10, use_memory=True)

    if not response:
        return None

    try:
        result = parse_json_response(response.content)
        result['humanFeedback'] = None
        result['revisionCount'] = 0
        result['revisionHistory'] = []
        result['overallWordCount'] = {"min": 1500, "max": 3000}
        return result
    except Exception as e:
        print(f"  ⚠️ JSON 解析失败: {e}")
        return None


def _revise_plot(
    original_plot: Dict,
    human_feedback: str,
    blueprint: Dict,
    revision_history: list,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """修改大纲"""
    agent = get_node_agent(
        node_name="plot_node",
        system_prompt=vx_prompt.PLOT_SYSTEM_PROMPT,
        llm_model=PLOT_LLM_MODEL,
        temperature=0.7,
        max_tokens=4000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    response = agent.invoke_with_revision(
        original_result=json.dumps(original_plot, ensure_ascii=False, indent=2),
        human_feedback=human_feedback,
        revision_history=revision_history,
        max_iterations=5,
    )

    if not response:
        return original_plot

    try:
        result = parse_json_response(response.content)
        new_history = revision_history.copy()
        new_history.append(human_feedback)
        result['revisionHistory'] = new_history
        result['revisionCount'] = len(new_history)
        result['humanFeedback'] = human_feedback
        result['overallWordCount'] = original_plot.get('overallWordCount', {"min": 1500, "max": 3000})
        return result
    except Exception:
        return original_plot


def _format_plot_for_display(plot: Dict) -> str:
    """格式化大纲展示"""
    wc = plot.get("writingContext", {})
    segments = plot.get("contentSegments", [])
    checklist = plot.get("globalChecklist", [])

    display = f"""
📋 文章大纲
📰 标题: {wc.get('articleTitle', 'N/A')}
💡 核心观点: {wc.get('coreIdea', 'N/A')[:80]}

📐 段落结构:
"""
    for seg in segments:
        emoji = {"introduction": "🚀", "body": "📄", "conclusion": "🎯"}.get(seg.get("segmentType"), "📄")
        wc_range = seg.get("wordCountRange", {})
        display += f"\n{emoji} 第{seg.get('segmentIndex', 0)}段 [{seg.get('segmentType', '?')}] {seg.get('sectionTitle', '无标题')}\n"
        display += f"   逻辑: {seg.get('coreLogic', 'N/A')[:80]}\n"
        display += f"   情绪: {seg.get('emotionalObjective', 'N/A')[:50]}\n"
        display += f"   字数: {wc_range.get('min', '?')}-{wc_range.get('max', '?')}字\n"

    display += f"\n✅ 自查清单:\n"
    for i, item in enumerate(checklist[:10], 1):
        display += f"{i}. {item}\n"
    return display
