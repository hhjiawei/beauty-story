"""
Collect Node - 收集信息节点

职责：
1. 根据汇总分析结果，进行网络搜索补充信息
2. 从知乎、今日头条、微博等平台收集高赞内容
3. 搜索官方回应、最新进展、关联事件
4. 人机协同：收集完成后需要人工检查

Agent 模式：
- 使用 NodeAgent 执行，工具动态发现（tavily_web_search 等）
- 搜索策略由 Agent 自主决定，不限定具体工具
- 聊天记录通过 CompositeBackend 持久化到 records
- 记忆通过 MemoryManager 三层系统管理
"""

import json
from typing import Dict, Any

from wechatessay.agents.agent_factory import get_node_agent, discover_tools_for_node
from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.states.vx_state import GraphState, ArticleSearchNode
from wechatessay.prompts import vx_prompt
from wechatessay.utils.json_utils import parse_json_response
from wechatessay.config import COLLECT_LLM_MODEL, HUMAN_IN_THE_LOOP, MAX_REVISION_ROUNDS


def collect_node(state: GraphState, **kwargs) -> Dict[str, Any]:
    """
    收集信息节点

    1. 分析需要补充的信息方向
    2. Agent 自主搜索相关信息（动态工具调用）
    3. 整理搜索结果
    4. 人机协同检查
    """
    print("\n" + "=" * 50)
    print("🔍 [collect_node] 开始收集补充信息")
    print("=" * 50)

    # 从 kwargs 获取依赖
    backend = kwargs.get("backend")
    store = kwargs.get("store")
    thread_id = kwargs.get("thread_id", "default")

    total_analysis = state.get("total_article_results", {})
    human_feedback = state.get("human_feedback")
    revision_count = state.get("revision_count", 0)

    # 显示可用工具
    tools = discover_tools_for_node("collect_node")
    print(f"  🔧 collect_node 可用工具: {[t.name for t in tools]}")

    # 如果收到人工反馈，进行修改
    if human_feedback and human_feedback.lower() not in ["ok", "满意", "continue"]:
        print(f"📝 收到修改意见（第{revision_count}轮）: {human_feedback[:100]}...")
        search_result = _revise_search(
            original_search=state.get("search_result", {}),
            human_feedback=human_feedback,
            total_analysis=total_analysis,
            backend=backend,
            store=store,
            thread_id=thread_id,
        )
    else:
        search_result = _perform_search(
            total_analysis=total_analysis,
            backend=backend,
            store=store,
            thread_id=thread_id,
        )

    if not search_result:
        return {"error_message": "信息收集失败", "should_continue": False}

    print("\n📋 搜索结果摘要:")
    print(f"   - 起因经过: {search_result.get('causeProcessResult', '')[:80]}...")
    print(f"   - 创作角度: {search_result.get('topicAngle', '')[:80]}...")
    print(f"   - 争议焦点: {search_result.get('controversialPoints', '')[:80]}...")
    print(f"   - 搜索关键词: {', '.join(search_result.get('searchQueriesUsed', [])[:5])}")

    # 人机协同
    if HUMAN_IN_THE_LOOP and not human_feedback:
        display_content = _format_search_for_display(search_result)
        print(vx_prompt.HUMAN_FEEDBACK_PROMPT.format(content_display=display_content))

        return {
            "search_result": search_result,
            "awaiting_human": True,
            "current_node": "collect_node"
        }

    return {
        "search_result": search_result,
        "awaiting_human": False,
        "human_feedback": None,
        "current_node": "collect_node"
    }


def _perform_search(
    total_analysis: Dict,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """
    执行网络搜索

    Agent 自主决定搜索策略，动态调用工具。
    """
    # 创建 Agent
    agent = get_node_agent(
        node_name="collect_node",
        system_prompt=vx_prompt.COLLECT_SYSTEM_PROMPT,
        llm_model=COLLECT_LLM_MODEL,
        temperature=0.8,
        max_tokens=4000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    # 获取记忆
    memory = get_memory_manager(backend=backend, store=store, thread_id=thread_id)
    memories = memory.context.get_context("user_memories", default=[])

    # 提取信息缺口
    information_gaps = total_analysis.get("summary", {}).get("informationGaps", [])
    gaps_text = "\n".join([f"- {g}" for g in information_gaps]) if information_gaps else "（暂无明确信息缺口）"

    json_schema = vx_prompt.get_json_schema_prompt(ArticleSearchNode)

    user_prompt = vx_prompt.COLLECT_USER_PROMPT_TEMPLATE.format(
        total_analysis=json.dumps(total_analysis, ensure_ascii=False, indent=2)[:3000],
        information_gaps=gaps_text,
        memories=vx_prompt.format_memories(memories),
        json_schema=json_schema
    )

    # Agent 执行（自动循环调用工具）
    response = agent.invoke(user_prompt, max_iterations=15, use_memory=True)

    if not response:
        return None

    try:
        return parse_json_response(response.content)
    except Exception as e:
        print(f"  ⚠️ JSON 解析失败: {e}")
        return None


def _revise_search(
    original_search: Dict,
    human_feedback: str,
    total_analysis: Dict,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """根据人工反馈修改搜索结果"""
    agent = get_node_agent(
        node_name="collect_node",
        system_prompt=vx_prompt.COLLECT_SYSTEM_PROMPT,
        llm_model=COLLECT_LLM_MODEL,
        temperature=0.8,
        max_tokens=4000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    revision_prompt = f"""
【原搜索结果】
{json.dumps(original_search, ensure_ascii=False, indent=2)[:3000]}

【修改意见】
{human_feedback}

【汇总分析】
{json.dumps(total_analysis, ensure_ascii=False, indent=2)[:1500]}

请根据修改意见调整搜索结果，输出 JSON 格式（与原格式一致）。
"""

    response = agent.invoke(revision_prompt, max_iterations=5, use_memory=True)

    if not response:
        return original_search

    try:
        return parse_json_response(response.content)
    except Exception:
        return original_search


def _format_search_for_display(search_result: Dict) -> str:
    """格式化搜索结果用于人工审核展示"""
    display = f"""
【事件起因、经过、结果补充】
{search_result.get('causeProcessResult', 'N/A')[:300]}

【创作角度补充】
{search_result.get('topicAngle', 'N/A')[:300]}

【支撑材料补充】
{search_result.get('topicMaterial', 'N/A')[:300]}

【争议焦点梳理】
{search_result.get('controversialPoints', 'N/A')[:300]}

【舆论观点汇总】
"""
    opinions = search_result.get('publicOpinions', [])
    for i, op in enumerate(opinions[:5]):
        display += f"{i+1}. [{op.get('stance', '?')}] {op.get('viewpoint', 'N/A')[:100]}\n"

    display += f"\n【信息来源】\n"
    sources = search_result.get('sources', [])
    for i, src in enumerate(sources[:8]):
        display += f"{i+1}. {src.get('platform', 'N/A')} - {src.get('author', 'N/A')}\n"

    return display
