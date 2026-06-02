"""
wechatessay.nodes.source_node

节点1: source_node — 基本信息源节点

职责：
1. 读取 txt 文档中的微信文章链接列表
2. 爬取每篇文章的内容
3. 调用 Deep Agent 分析每篇文章，提取结构化信息
4. 汇总所有文章分析结果为 TotalArticleAnalyseNode
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from wechatessay.agents.backend import load_backend
from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.config import get_model_instance, BACKEND_CONFIG, MEMORY_CONFIG, MODEL_CONFIG
from wechatessay.prompts.vx_prompt import SOURCE_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import (
    GraphState,
    PerArticleAnalyseNode,
    TotalArticleAnalyseNode,
)
from wechatessay.tools.base_tools.base_tool import get_base_tools
from wechatessay.tools.mcp_tools.mcp_tool import get_total_tools
from wechatessay.utils.json_utils import parse_json_response
from wechatessay.utils.vx_util import scan_article_files, read_article




def _create_source_agent(tools: list[BaseTool]) -> Any:
    """创建 source_node 的 Deep Agent。"""
    backend = load_backend()

    mm = get_memory_manager()
    memory_context = mm.build_memory_context("公众号文章分析")

    system_prompt = SOURCE_NODE_SYSTEM_PROMPT
    if memory_context:
        system_prompt = f"{memory_context}\n\n{system_prompt}"

    memory_files = []
    mem_file = Path(MEMORY_CONFIG["long_term_file"])
    if mem_file.exists():
        memory_files.append(str(mem_file))

    return create_deep_agent(
        model=get_model_instance(MODEL_CONFIG.get("analysis_model")),
        tools=tools,
        system_prompt=system_prompt,
        backend=backend,
        memory=memory_files,
        name="source_analyzer",
    )


async def _analyze_articles(articles: list[str], agent: Any) -> list[PerArticleAnalyseNode]:
    """使用 Deep Agent 分析所有文章。"""
    per_article_results = []

    for idx, article_content in enumerate(articles):
        if not article_content or article_content.startswith("Error"):
            continue

        messages = [
            {
                "role": "user",
                "content": (
                    f"请分析以下第 {idx + 1} 篇文章，"
                    f"提取所有结构化信息并以 JSON 格式输出。\n\n"
                    f"文章内容：\n{article_content[:8000]}\n\n"
                    f"请只输出 JSON，不要输出其他内容。"
                ),
            }
        ]

        result = await agent.ainvoke({"messages": messages})
        response_content = result["messages"][-1].content if result.get("messages") else ""

        try:
            parsed = parse_json_response(response_content)
            if isinstance(parsed, dict) and "per_article_results" in parsed:
                for item in parsed["per_article_results"]:
                    article_node = PerArticleAnalyseNode.model_validate(item)
                    article_node.source_url = f"article_{idx + 1}"
                    article_node.analyzed_at = datetime.now().isoformat()
                    per_article_results.append(article_node)
            elif isinstance(parsed, dict):
                article_node = PerArticleAnalyseNode.model_validate(parsed)
                article_node.source_url = f"article_{idx + 1}"
                article_node.analyzed_at = datetime.now().isoformat()
                per_article_results.append(article_node)
        except Exception as e:
            print(f"[source_node] 解析第 {idx + 1} 篇文章失败: {e}")
            continue

    return per_article_results


def _merge_to_total(
    per_results: list[PerArticleAnalyseNode],
) -> TotalArticleAnalyseNode:
    """将多篇文章的分析结果汇总为 TotalArticleAnalyseNode。"""
    if not per_results:
        raise ValueError("没有可汇总的文章分析结果")

    first = per_results[0]
    emotions = [r.emotional_tendency for r in per_results]
    emotional_tendency = max(set(emotions), key=emotions.count)

    all_events = []
    for r in per_results:
        all_events.extend(r.event_line)
    event_line = list(dict.fromkeys(all_events))

    all_ideas = []
    for r in per_results:
        all_ideas.extend(r.creation_ideas)
    creation_ideas = list(dict.fromkeys(all_ideas))

    all_quotes, all_details, all_perspectives, all_triggers = [], [], [], []
    for r in per_results:
        all_quotes.extend(r.supplementary.key_quotes)
        all_details.extend(r.supplementary.vivid_details)
        all_perspectives.extend(r.supplementary.unique_perspectives)
        all_triggers.extend(r.supplementary.emotional_triggers)

    source_urls = [r.source_url for r in per_results if r.source_url]

    return TotalArticleAnalyseNode(
        hotspot_title=first.hotspot_title,
        vertical_track=first.vertical_track,
        core_demand=first.core_demand,
        emotional_tendency=emotional_tendency,
        writing_style=first.writing_style,
        writing_structure=first.writing_structure,
        event_line=event_line,
        region_scope=first.region_scope,
        public_complaints=first.public_complaints,
        data_comparison=first.data_comparison,
        extended_content=first.extended_content,
        creation_ideas=creation_ideas,
        all_key_quotes=list(dict.fromkeys(all_quotes)),
        all_vivid_details=list(dict.fromkeys(all_details)),
        all_unique_perspectives=list(dict.fromkeys(all_perspectives)),
        all_emotional_triggers=list(dict.fromkeys(all_triggers)),
        source_count=len(per_results),
        source_urls=source_urls,
        summary_version="1.0",
    )


async def source_node_async(state: GraphState) -> GraphState:
    """
    source_node 异步执行入口。
    核心修复：使用 await agent.ainvoke() 而非 agent.invoke()。
    """
    input_path = state.get("input_path", "")
    if not input_path:
        state["error_message"] = "input_path 不能为空"
        state["error_node"] = "source_node"
        return state

    print(f"[source_node] 开始分析文章: {input_path}")


    file_list = scan_article_files(input_path)
    if not file_list:
        state["error_message"] = f"未找到文章文件: {input_path}"
        state["error_node"] = "source_node"
        return state

    print(f"[source_node] 发现 {len(file_list)} 篇文章")

    articles = []
    for f in file_list:
        content = read_article(f)
        if content and not content.startswith("Error"):
            articles.append(content)

    if not articles:
        state["error_message"] = "未能读取任何文章内容"
        state["error_node"] = "source_node"
        return state

    base_tools = await get_base_tools()
    mcp_tools = await get_total_tools()
    total_tools = list(base_tools) + list(mcp_tools)

    agent = _create_source_agent(total_tools)

    per_results = await _analyze_articles(articles, agent)

    if not per_results:
        state["error_message"] = "文章分析未产出任何结果"
        state["error_node"] = "source_node"
        return state

    total_result = _merge_to_total(per_results)

    state["per_article_results"] = per_results
    state["total_article_results"] = total_result
    state["current_node"] = "source_node"
    state["node_status"]["source_node"] = "completed"

    mm = get_memory_manager()
    mm.add_short_term(
        f"source_{datetime.now().isoformat()}",
        {
            "hotspot_title": total_result.hotspot_title,
            "source_count": total_result.source_count,
            "core_demand": total_result.core_demand,
        },
    )

    print(f"[source_node] 完成: {total_result.hotspot_title} (来源{total_result.source_count}篇)")
    return state


def source_node(state: GraphState) -> GraphState:
    """source_node 同步入口包装。"""
    import asyncio
    return asyncio.run(source_node_async(state))