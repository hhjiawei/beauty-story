"""
Source Node - 基本信息源节点

职责：
1. 读取 txt 文件中的微信公众号文章链接
2. 爬取每篇文章的内容
3. 使用 Deep Agent 分析每篇文章的基本信息和额外信息
4. 汇总所有文章的分析结果

Agent 模式：
- 使用 NodeAgent 执行，自动管理工具调用和记忆
- 工具通过 Agent Factory 动态注册，不硬编码
- 聊天记录通过 CompositeBackend 持久化
"""

import json
from typing import Dict, List, Any

from wechatessay.agents.agent_factory import get_node_agent, discover_tools_for_node
from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.agents.chat_history_store import get_chat_history_store
from wechatessay.states.vx_state import GraphState, PerArticleAnalyseNode, TotalArticleAnalyseNode
from wechatessay.prompts import vx_prompt
from wechatessay.utils.json_utils import parse_json_response
from wechatessay.config import (
    DEFAULT_LLM_MODEL,
    SOURCES_DIR,
)


def source_node(state: GraphState, **kwargs) -> Dict[str, Any]:
    """
    基本信息源节点

    1. 读取 txt 文件中的文章链接
    2. 爬取文章内容
    3. 使用 Deep Agent 分析每篇文章
    4. 返回 per_article_results

    Args:
        state: 当前图状态
        **kwargs: 包含 backend, store, thread_id 等来自 graph 的依赖注入
    """
    print("\n" + "=" * 50)
    print("📚 [source_node] 开始读取和分析文章")
    print("=" * 50)

    # 从 kwargs 获取依赖
    backend = kwargs.get("backend")
    store = kwargs.get("store")
    thread_id = kwargs.get("thread_id", "default")

    input_path = state.get("input_path", "")

    # 1. 读取 txt 文件
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return {"error_message": f"读取文件失败: {e}", "should_continue": False}

    print(f"📄 发现 {len(urls)} 篇文章链接")

    # 2. 分析每篇文章
    per_article_results = []

    # 获取已注册的工具列表
    tools = discover_tools_for_node("source_node")
    print(f"  🔧 source_node 可用工具: {[t.name for t in tools]}")

    for i, url in enumerate(urls):
        print(f"\n🔍 分析第 {i + 1}/{len(urls)} 篇文章: {url[:50]}...")

        # 获取文章内容（预留用户 read_article 接口）
        article_content = _fetch_article(url)

        # 使用 Deep Agent 分析文章
        analysis_result = _analyze_single_article(
            article_content=article_content,
            source_url=url,
            backend=backend,
            store=store,
            thread_id=thread_id,
        )

        if analysis_result:
            per_article_results.append(analysis_result)
            print(f"✅ 第 {i + 1} 篇文章分析完成: {analysis_result.get('hotspotTitle', 'N/A')}")
        else:
            print(f"⚠️ 第 {i + 1} 篇文章分析失败")

    print(f"\n📊 共分析 {len(per_article_results)} 篇文章")

    return {
        "per_article_results": per_article_results,
        "current_node": "source_node"
    }


def _fetch_article(url: str) -> str:
    """
    获取文章内容

    如果用户已实现 read_article，替换为实际调用。
    目前返回占位符，提示用户接入。
    """
    try:
        # 尝试使用用户的 read_article
        # from utils.article_reader import read_article
        # return read_article(url)
        pass
    except ImportError:
        pass
    # 占位符：实际使用时应替换为真实内容
    return f"[文章内容占位符 - URL: {url}]"


def _analyze_single_article(
    article_content: str,
    source_url: str,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """
    使用 Deep Agent 分析单篇文章

    Agent 模式：
    - NodeAgent 自动处理工具调用循环
    - 工具动态发现，不硬编码
    - 聊天记录自动持久化到 CompositeBackend
    """
    # 创建 Agent
    agent = get_node_agent(
        node_name="source_node",
        system_prompt=vx_prompt.SOURCE_SYSTEM_PROMPT,
        llm_model=DEFAULT_LLM_MODEL,
        temperature=0.7,
        max_tokens=4000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    # 构建 prompt
    json_schema = vx_prompt.get_json_schema_prompt(PerArticleAnalyseNode)

    user_prompt = vx_prompt.SOURCE_USER_PROMPT_TEMPLATE.format(
        article_content=article_content,
        source_url=source_url,
        json_schema=json_schema
    )

    # 注入用户记忆
    memory = get_memory_manager(backend=backend, store=store, thread_id=thread_id)
    memories = memory.context.get_context("user_memories", default=[])
    if memories:
        user_prompt += f"\n\n【用户习惯记忆】\n{vx_prompt.format_memories(memories)}"

    # 执行 Agent（自动处理工具调用循环）
    response = agent.invoke(user_prompt, max_iterations=10, use_memory=True)

    if not response:
        return None

    # 解析 JSON 结果
    try:
        result = parse_json_response(response.content)
        result['sourceUrl'] = source_url
        return result
    except Exception as e:
        print(f"  ⚠️ JSON 解析失败: {e}")
        return None


# ── Total Analysis Node ──

def total_analysis_node(state: GraphState, **kwargs) -> Dict[str, Any]:
    """
    文章汇总分析节点

    将 List[PerArticleAnalyseNode] 进行汇总分析
    """
    print("\n" + "=" * 50)
    print("📊 [total_analysis_node] 开始汇总分析")
    print("=" * 50)

    # 从 kwargs 获取依赖
    backend = kwargs.get("backend")
    store = kwargs.get("store")
    thread_id = kwargs.get("thread_id", "default")

    per_article_results = state.get("per_article_results", [])

    if not per_article_results:
        return {"error_message": "没有文章分析结果", "should_continue": False}

    # 使用 Deep Agent 汇总分析
    total_result = _analyze_total_articles(
        per_article_results=per_article_results,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    if total_result:
        print(f"✅ 汇总分析完成: {total_result.get('summary', {}).get('totalCount', 0)} 篇文章")
        return {
            "total_article_results": total_result,
            "current_node": "total_analysis_node"
        }
    else:
        return {"error_message": "汇总分析失败", "should_continue": False}


def _analyze_total_articles(
    per_article_results: List[Dict],
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """使用 Deep Agent 汇总分析多篇文章"""

    agent = get_node_agent(
        node_name="total_analysis_node",
        system_prompt=vx_prompt.TOTAL_ANALYSIS_SYSTEM_PROMPT,
        llm_model=DEFAULT_LLM_MODEL,
        temperature=0.7,
        max_tokens=4000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    json_schema = vx_prompt.get_json_schema_prompt(TotalArticleAnalyseNode)

    formatted_results = []
    for i, r in enumerate(per_article_results):
        title = r.get('hotspotTitle', f'文章{i + 1}')
        formatted_results.append(
            f"\n--- 文章{i + 1}: {title} ---\n{json.dumps(r, ensure_ascii=False, indent=2)[:2000]}"
        )

    per_article_text = "\n".join(formatted_results)

    user_prompt = vx_prompt.TOTAL_ANALYSIS_USER_PROMPT_TEMPLATE.format(
        article_count=len(per_article_results),
        per_article_results=per_article_text,
        json_schema=json_schema
    )

    response = agent.invoke(user_prompt, max_iterations=10, use_memory=True)

    if not response:
        return None

    try:
        return parse_json_response(response.content)
    except Exception as e:
        print(f"  ⚠️ JSON 解析失败: {e}")
        return None
