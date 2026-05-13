"""
Write Node - 写作节点

职责：
1. 根据大纲指令写出高质量文章
2. 严格按大纲结构写作
3. 标注金句位置，提供转发语
4. 人机协同：需要人工检查

Agent 模式：NodeAgent 自动管理工具调用和记忆
"""

import json
from typing import Dict, Any

from wechatessay.agents.agent_factory import get_node_agent, discover_tools_for_node
from wechatessay.states.vx_state import GraphState, ArticleOutputNode
from wechatessay.prompts import vx_prompt
from wechatessay.utils.json_utils import parse_json_response
from wechatessay.config import WRITE_LLM_MODEL, HUMAN_IN_THE_LOOP, MAX_REVISION_ROUNDS


def write_node(state: GraphState, **kwargs) -> Dict[str, Any]:
    """写作节点"""
    print("\n" + "=" * 50)
    print("✍️ [write_node] 开始写作文章")
    print("=" * 50)

    backend = kwargs.get("backend")
    store = kwargs.get("store")
    thread_id = kwargs.get("thread_id", "default")

    plot = state.get("plot_result", {})
    blueprint = state.get("blueprint_result", {})
    search_result = state.get("search_result", {})
    human_feedback = state.get("human_feedback")
    revision_count = state.get("revision_count", 0)

    tools = discover_tools_for_node("write_node")
    print(f"  🔧 write_node 可用工具: {[t.name for t in tools]}")

    if human_feedback and human_feedback.lower() not in ["ok", "满意", "continue"]:
        if revision_count >= MAX_REVISION_ROUNDS:
            print(f"⚠️ 达到最大修改轮次 ({MAX_REVISION_ROUNDS})")
            return {
                "article_output": state.get("article_output", {}),
                "awaiting_human": False,
                "human_feedback": None,
                "current_node": "write_node"
            }

        print(f"📝 收到修改意见（第{revision_count}轮）: {human_feedback[:100]}...")
        article = _revise_article(
            original_article=state.get("article_output", {}),
            human_feedback=human_feedback,
            plot=plot,
            blueprint=blueprint,
            revision_history=state.get("article_output", {}).get("revisionHistory", []),
            backend=backend,
            store=store,
            thread_id=thread_id,
        )
    else:
        article = _write_article(
            plot=plot,
            blueprint=blueprint,
            search_result=search_result,
            backend=backend,
            store=store,
            thread_id=thread_id,
        )

    if not article:
        return {"error_message": "文章写作失败", "should_continue": False}

    # 显示摘要
    parts = article.get("parts", [])
    full_text = article.get("fullText", "")
    total_chars = len(full_text) if full_text else sum(len(p.get("content", "")) for p in parts)
    print(f"   - 总字数: {total_chars}")
    print(f"   - 段落数: {len(parts)}")

    if HUMAN_IN_THE_LOOP and not human_feedback:
        print(vx_prompt.HUMAN_FEEDBACK_PROMPT.format(
            content_display=_format_article_for_display(article)
        ))
        return {
            "article_output": article,
            "awaiting_human": True,
            "current_node": "write_node"
        }

    return {
        "article_output": article,
        "awaiting_human": False,
        "human_feedback": None,
        "current_node": "write_node"
    }


def _write_article(
    plot: Dict,
    blueprint: Dict,
    search_result: Dict,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """写作文章"""
    agent = get_node_agent(
        node_name="write_node",
        system_prompt=vx_prompt.WRITE_SYSTEM_PROMPT,
        llm_model=WRITE_LLM_MODEL,
        temperature=0.9,
        max_tokens=8000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    json_schema = vx_prompt.get_json_schema_prompt(ArticleOutputNode)

    user_prompt = vx_prompt.WRITE_USER_PROMPT_TEMPLATE.format(
        plot=json.dumps(plot, ensure_ascii=False, indent=2)[:3000],
        blueprint=json.dumps(blueprint, ensure_ascii=False, indent=2)[:2000],
        search_result=json.dumps(search_result, ensure_ascii=False, indent=2)[:1500],
        memories="（暂无用户习惯记忆）",
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

        # 拼接完整文本
        parts = result.get("parts", [])
        if parts:
            result['fullText'] = "\n\n".join([p.get("content", "") for p in parts])
            for part in parts:
                part['actualWordCount'] = len(part.get("content", ""))

        return result
    except Exception as e:
        print(f"  ⚠️ JSON 解析失败: {e}")
        return None


def _revise_article(
    original_article: Dict,
    human_feedback: str,
    plot: Dict,
    blueprint: Dict,
    revision_history: list,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """修改文章"""
    agent = get_node_agent(
        node_name="write_node",
        system_prompt=vx_prompt.WRITE_SYSTEM_PROMPT,
        llm_model=WRITE_LLM_MODEL,
        temperature=0.9,
        max_tokens=8000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    response = agent.invoke_with_revision(
        original_result=json.dumps(original_article, ensure_ascii=False, indent=2),
        human_feedback=human_feedback,
        revision_history=revision_history,
        max_iterations=5,
    )

    if not response:
        return original_article

    try:
        result = parse_json_response(response.content)
        new_history = revision_history.copy()
        new_history.append(human_feedback)
        result['revisionHistory'] = new_history
        result['revisionCount'] = len(new_history)
        result['humanFeedback'] = human_feedback

        parts = result.get("parts", [])
        if parts:
            result['fullText'] = "\n\n".join([p.get("content", "") for p in parts])

        return result
    except Exception:
        return original_article


def _format_article_for_display(article: Dict) -> str:
    """格式化文章展示"""
    parts = article.get("parts", [])
    display = "\n📄 文章内容\n═══════════════════════════════════════════\n\n"
    for part in parts:
        idx = part.get("partIndex", 0)
        content = part.get("content", "[无内容]")
        golden = part.get("goldenSentences", [])
        share = part.get("shareTexts", [])
        display += f"─── 第{idx}段 ───\n{content[:500]}\n"
        if golden:
            display += f"\n✨ 金句:\n"
            for gs in golden[:2]:
                display += f"   「{gs.get('text', 'N/A')[:60]}」\n"
        if share:
            display += f"\n📤 转发语:\n"
            for st in share[:2]:
                display += f"   {st[:60]}\n"
        display += "\n"
    return display
