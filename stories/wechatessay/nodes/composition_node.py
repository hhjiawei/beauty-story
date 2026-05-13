"""
Composition Node - 排版节点

职责：
1. 将文章转换为适合微信公众号阅读的排版格式
2. 设计标题样式、段落间距、重点高亮
3. 金句单独成段
4. 生成 HTML 和 Markdown 两种格式
5. 人机协同：需要人工检查

Agent 模式：NodeAgent 自动管理工具调用和记忆
"""

import json
from typing import Dict, Any

from wechatessay.agents.agent_factory import get_node_agent, discover_tools_for_node
from wechatessay.states.vx_state import GraphState, CompositionNode
from wechatessay.prompts import vx_prompt
from wechatessay.utils.json_utils import parse_json_response
from wechatessay.config import DEFAULT_LLM_MODEL, HUMAN_IN_THE_LOOP, MAX_REVISION_ROUNDS


def composition_node(state: GraphState, **kwargs) -> Dict[str, Any]:
    """排版节点"""
    print("\n" + "=" * 50)
    print("🎨 [composition_node] 开始排版")
    print("=" * 50)

    backend = kwargs.get("backend")
    store = kwargs.get("store")
    thread_id = kwargs.get("thread_id", "default")

    article_output = state.get("article_output", {})
    blueprint = state.get("blueprint_result", {})
    human_feedback = state.get("human_feedback")
    revision_count = state.get("revision_count", 0)

    tools = discover_tools_for_node("composition_node")
    print(f"  🔧 composition_node 可用工具: {[t.name for t in tools]}")

    full_text = article_output.get("fullText", "")
    if not full_text:
        parts = article_output.get("parts", [])
        full_text = "\n\n".join([p.get("content", "") for p in parts])

    if human_feedback and human_feedback.lower() not in ["ok", "满意", "continue"]:
        if revision_count >= MAX_REVISION_ROUNDS:
            print(f"⚠️ 达到最大修改轮次 ({MAX_REVISION_ROUNDS})")
            return {
                "composition_result": state.get("composition_result", {}),
                "awaiting_human": False,
                "human_feedback": None,
                "current_node": "composition_node"
            }

        print(f"📝 收到修改意见（第{revision_count}轮）: {human_feedback[:100]}...")
        composition = _revise_composition(
            original_composition=state.get("composition_result", {}),
            human_feedback=human_feedback,
            article_content=full_text,
            blueprint=blueprint,
            revision_history=state.get("composition_result", {}).get("revisionHistory", []),
            backend=backend,
            store=store,
            thread_id=thread_id,
        )
    else:
        composition = _compose_article(
            article_content=full_text,
            blueprint=blueprint,
            backend=backend,
            store=store,
            thread_id=thread_id,
        )

    if not composition:
        return {"error_message": "排版失败", "should_continue": False}

    print(f"   - 排版元素数: {len(composition.get('elements', []))}")

    if HUMAN_IN_THE_LOOP and not human_feedback:
        print(vx_prompt.HUMAN_FEEDBACK_PROMPT.format(
            content_display=_format_composition_for_display(composition)
        ))
        return {
            "composition_result": composition,
            "awaiting_human": True,
            "current_node": "composition_node"
        }

    return {
        "composition_result": composition,
        "awaiting_human": False,
        "human_feedback": None,
        "current_node": "composition_node"
    }


def _compose_article(
    article_content: str,
    blueprint: Dict,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """排版文章"""
    agent = get_node_agent(
        node_name="composition_node",
        system_prompt=vx_prompt.COMPOSITION_SYSTEM_PROMPT,
        llm_model=DEFAULT_LLM_MODEL,
        temperature=0.5,
        max_tokens=6000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    json_schema = vx_prompt.get_json_schema_prompt(CompositionNode)

    user_prompt = vx_prompt.COMPOSITION_USER_PROMPT_TEMPLATE.format(
        article_content=article_content[:3000],
        blueprint=json.dumps(blueprint, ensure_ascii=False, indent=2)[:1500],
        memories="（暂无用户习惯记忆）",
        json_schema=json_schema
    )

    response = agent.invoke(user_prompt, max_iterations=5, use_memory=True)

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


def _revise_composition(
    original_composition: Dict,
    human_feedback: str,
    article_content: str,
    blueprint: Dict,
    revision_history: list,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """修改排版"""
    agent = get_node_agent(
        node_name="composition_node",
        system_prompt=vx_prompt.COMPOSITION_SYSTEM_PROMPT,
        llm_model=DEFAULT_LLM_MODEL,
        temperature=0.5,
        max_tokens=6000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    response = agent.invoke_with_revision(
        original_result=json.dumps(original_composition, ensure_ascii=False, indent=2),
        human_feedback=human_feedback,
        revision_history=revision_history,
        max_iterations=3,
    )

    if not response:
        return original_composition

    try:
        result = parse_json_response(response.content)
        new_history = revision_history.copy()
        new_history.append(human_feedback)
        result['revisionHistory'] = new_history
        result['revisionCount'] = len(new_history)
        result['humanFeedback'] = human_feedback
        return result
    except Exception:
        return original_composition


def _format_composition_for_display(composition: Dict) -> str:
    """格式化排版展示"""
    elements = composition.get("elements", [])
    layout = composition.get("layoutSuggestions", [])
    markdown = composition.get("markdownText", "")

    display = f"\n🎨 排版预览\n\n📐 排版元素 ({len(elements)}个):\n"
    for i, elem in enumerate(elements[:8], 1):
        display += f"{i}. [{elem.get('elementType', '?')}] {elem.get('content', 'N/A')[:50]}\n"

    if markdown:
        display += f"\n📝 Markdown:\n{markdown[:800]}...\n"

    if layout:
        display += f"\n📏 布局建议:\n"
        for i, sug in enumerate(layout[:5], 1):
            display += f"{i}. {sug}\n"
    return display
