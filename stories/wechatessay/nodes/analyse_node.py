"""
Analyse Node - 分析节点

职责：
1. 整合文章分析和搜索结果
2. 分析写作角度（常用/融合/对立/争议/深思）
3. 确定写作风格、模板、执行计划
4. 人机协同：需要人工检查

Agent 模式：
- NodeAgent 自动管理工具调用和记忆
- 工具动态发现，不硬编码
- 聊天记录通过 CompositeBackend 持久化
- 记忆通过 MemoryManager 三层系统管理
"""

import json
from typing import Dict, Any

from wechatessay.agents.agent_factory import get_node_agent, discover_tools_for_node
from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.states.vx_state import GraphState, ArticleBlueprintNode
from wechatessay.prompts import vx_prompt
from wechatessay.utils.json_utils import parse_json_response
from wechatessay.config import ANALYSE_LLM_MODEL, HUMAN_IN_THE_LOOP, MAX_REVISION_ROUNDS


def analyse_node(state: GraphState, **kwargs) -> Dict[str, Any]:
    """
    分析节点：生成写作蓝图
    """
    print("\n" + "=" * 50)
    print("🎯 [analyse_node] 开始分析写作策略")
    print("=" * 50)

    backend = kwargs.get("backend")
    store = kwargs.get("store")
    thread_id = kwargs.get("thread_id", "default")

    total_analysis = state.get("total_article_results", {})
    search_result = state.get("search_result", {})
    human_feedback = state.get("human_feedback")
    revision_count = state.get("revision_count", 0)

    # 显示可用工具
    tools = discover_tools_for_node("analyse_node")
    print(f"  🔧 analyse_node 可用工具: {[t.name for t in tools]}")

    # 人机协同修改
    if human_feedback and human_feedback.lower() not in ["ok", "满意", "continue"]:
        if revision_count >= MAX_REVISION_ROUNDS:
            print(f"⚠️ 达到最大修改轮次 ({MAX_REVISION_ROUNDS})")
            return {
                "blueprint_result": state.get("blueprint_result", {}),
                "awaiting_human": False,
                "human_feedback": None,
                "current_node": "analyse_node"
            }

        print(f"📝 收到修改意见（第{revision_count}轮）: {human_feedback[:100]}...")
        blueprint = _revise_blueprint(
            original_blueprint=state.get("blueprint_result", {}),
            human_feedback=human_feedback,
            total_analysis=total_analysis,
            search_result=search_result,
            revision_history=state.get("blueprint_result", {}).get("revisionHistory", []),
            backend=backend,
            store=store,
            thread_id=thread_id,
        )
    else:
        blueprint = _generate_blueprint(
            total_analysis=total_analysis,
            search_result=search_result,
            backend=backend,
            store=store,
            thread_id=thread_id,
        )

    if not blueprint:
        return {"error_message": "写作蓝图生成失败", "should_continue": False}

    # 显示摘要
    wa = blueprint.get("writingAnalysis", {})
    print(f"   - 推荐角度: {wa.get('recommendedAngle', 'N/A')[:60]}")
    ws = blueprint.get("writingStyle", {})
    print(f"   - 写作风格: {ws.get('finalStyle', 'N/A')}")
    wp = blueprint.get("writingPlan", {})
    print(f"   - 核心思路: {wp.get('coreIdea', 'N/A')[:60]}")

    # 人机协同
    if HUMAN_IN_THE_LOOP and not human_feedback:
        print(vx_prompt.HUMAN_FEEDBACK_PROMPT.format(
            content_display=_format_blueprint_for_display(blueprint)
        ))
        return {
            "blueprint_result": blueprint,
            "awaiting_human": True,
            "current_node": "analyse_node"
        }

    return {
        "blueprint_result": blueprint,
        "awaiting_human": False,
        "human_feedback": None,
        "current_node": "analyse_node"
    }


def _generate_blueprint(
    total_analysis: Dict,
    search_result: Dict,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """生成写作蓝图 - Agent 自主执行"""
    agent = get_node_agent(
        node_name="analyse_node",
        system_prompt=vx_prompt.ANALYSE_SYSTEM_PROMPT,
        llm_model=ANALYSE_LLM_MODEL,
        temperature=0.8,
        max_tokens=4000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    memory = get_memory_manager(backend=backend, store=store, thread_id=thread_id)
    memories = memory.context.get_context("user_memories", default=[])

    json_schema = vx_prompt.get_json_schema_prompt(ArticleBlueprintNode)

    user_prompt = vx_prompt.ANALYSE_USER_PROMPT_TEMPLATE.format(
        total_analysis=json.dumps(total_analysis, ensure_ascii=False, indent=2)[:2000],
        search_result=json.dumps(search_result, ensure_ascii=False, indent=2)[:2000],
        memories=vx_prompt.format_memories(memories),
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
        return result
    except Exception as e:
        print(f"  ⚠️ JSON 解析失败: {e}")
        return None


def _revise_blueprint(
    original_blueprint: Dict,
    human_feedback: str,
    total_analysis: Dict,
    search_result: Dict,
    revision_history: list,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """根据反馈修改蓝图"""
    agent = get_node_agent(
        node_name="analyse_node",
        system_prompt=vx_prompt.ANALYSE_SYSTEM_PROMPT,
        llm_model=ANALYSE_LLM_MODEL,
        temperature=0.8,
        max_tokens=4000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    response = agent.invoke_with_revision(
        original_result=json.dumps(original_blueprint, ensure_ascii=False, indent=2),
        human_feedback=human_feedback,
        revision_history=revision_history,
        max_iterations=5,
    )

    if not response:
        return original_blueprint

    try:
        result = parse_json_response(response.content)
        new_history = revision_history.copy()
        new_history.append(human_feedback)
        result['revisionHistory'] = new_history
        result['revisionCount'] = len(new_history)
        result['humanFeedback'] = human_feedback
        return result
    except Exception:
        return original_blueprint


def _format_blueprint_for_display(blueprint: Dict) -> str:
    """格式化蓝图用于展示"""
    wa = blueprint.get("writingAnalysis", {})
    ws = blueprint.get("writingStyle", {})
    wt = blueprint.get("writingTemplate", {})
    wp = blueprint.get("writingPlan", {})

    display = f"""
📝 写作蓝图
─────────────────────────────────────────
📐 推荐角度: {wa.get('recommendedAngle', 'N/A')}

常用角度:
"""
    for i, angle in enumerate(wa.get('commonAngles', [])[:3], 1):
        display += f"  {i}. {angle[:80]}\n"

    display += f"\n✍️ 写作风格: {ws.get('finalStyle', 'N/A')}\n"
    display += f"理由: {ws.get('styleReason', 'N/A')[:100]}\n"
    display += f"示例: {ws.get('styleExample', 'N/A')[:100]}\n"
    display += f"\n📰 建议标题: {wt.get('title', 'N/A')}\n"
    display += f"\n💡 核心思路: {wp.get('coreIdea', 'N/A')[:100]}\n"
    display += f"引子设计: {wp.get('leadIn', 'N/A')[:100]}\n"
    display += f"钩子策略: {wp.get('hookStrategy', 'N/A')[:100]}\n"
    return display
