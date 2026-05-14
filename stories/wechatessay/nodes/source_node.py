"""
wechatessay.nodes.source_node

节点1: source_node — 基本信息源节点

职责：
1. 读取 txt 文档中的微信文章链接列表
2. 爬取每篇文章的内容
3. 调用 Deep Agent 分析每篇文章，提取结构化信息
4. 汇总所有文章分析结果为 TotalArticleAnalyseNode

依赖：
- Deep Agent (create_deep_agent)
- scan_article_files / read_article 工具
- PerArticleAnalyseNode / TotalArticleAnalyseNode 状态模型
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from deepagents import create_deep_agent
from langchain_core.tools import BaseTool

from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.config import BACKEND_CONFIG, MEMORY_CONFIG, MODEL_CONFIG
from wechatessay.prompts.vx_prompt import SOURCE_NODE_SYSTEM_PROMPT
from wechatessay.states.vx_state import (
    GraphState,
    PerArticleAnalyseNode,
    TotalArticleAnalyseNode,
)
from wechatessay.tools.base_tools.base_tool import get_base_tools
from wechatessay.tools.mcp_tools.mcp_tool import get_total_tools
from wechatessay.utils.json_utils import parse_json_response


def _load_backend():
    """加载 Deep Agents backend 配置。"""
    from deepagents.backends import CompositeBackend, FilesystemBackend
    root = Path(BACKEND_CONFIG["root_dir"])
    return CompositeBackend(
        default=FilesystemBackend(root_dir=root, virtual_mode=BACKEND_CONFIG["virtual_mode"]),
        routes={
            "/memories/": FilesystemBackend(
                root_dir=Path(BACKEND_CONFIG["routes"]["/memories/"]["root_dir"]),
                virtual_mode=True,
            ),
            "/skills/": FilesystemBackend(
                root_dir=Path(BACKEND_CONFIG["routes"]["/skills/"]["root_dir"]),
                virtual_mode=True,
            ),
            "/workspaces/": FilesystemBackend(
                root_dir=Path(BACKEND_CONFIG["routes"]["/workspaces/"]["root_dir"]),
                virtual_mode=True,
            ),
        },
    )


def _create_source_agent(tools: List[BaseTool]) -> Any:
    """
    创建 source_node 的 Deep Agent。

    使用 create_deep_agent 初始化，配置：
    - model: 分析专用模型
    - tools: base_tools + mcp_tools
    - system_prompt: 文章分析专用提示词
    - backend: CompositeBackend 虚拟文件系统
    - response_format: 结构化输出（JSON 模式）
    """
    backend = _load_backend()

    # 获取记忆上下文
    mm = get_memory_manager()
    memory_context = mm.build_memory_context("公众号文章分析")

    # 组装系统提示词
    system_prompt = SOURCE_NODE_SYSTEM_PROMPT
    if memory_context:
        system_prompt = f"{memory_context}\n\n{system_prompt}"

    # 记忆文件列表
    memory_files = []
    mem_file = Path(MEMORY_CONFIG["long_term_file"])
    if mem_file.exists():
        memory_files.append(str(mem_file))

    return create_deep_agent(
        model=MODEL_CONFIG.get("analysis_model", MODEL_CONFIG["default_model"]),
        tools=tools,
        system_prompt=system_prompt,
        backend=backend,
        memory=memory_files,
        name="source_analyzer",
        # response_format 通过 prompt 中的 JSON 格式要求来约束
    )


def _analyze_articles(articles: List[str], agent: Any) -> List[PerArticleAnalyseNode]:
    """
    使用 Deep Agent 分析所有文章。

    每篇文章独立分析，最后汇总。
    """
    per_article_results = []

    for idx, article_content in enumerate(articles):
        if not article_content or article_content.startswith("Error"):
            continue

        # 构建单篇分析消息
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

        # 调用 Agent
        result = agent.invoke({"messages": messages})
        response_content = result["messages"][-1].content if result.get("messages") else ""

        # 解析 JSON 响应
        try:
            parsed = parse_json_response(response_content)
            # 解析为 PerArticleAnalyseNode
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
    per_results: List[PerArticleAnalyseNode],
) -> TotalArticleAnalyseNode:
    """
    将多篇文章的分析结果汇总为 TotalArticleAnalyseNode。

    汇总逻辑：
    - 标题/赛道/诉求：取第一篇的（或智能合并）
    - 情感倾向：统计多数
    - 文风/结构：取多数
    - 时间线：合并去重排序
    - 补充素材：全部合并
    """
    if not per_results:
        raise ValueError("没有可汇总的文章分析结果")

    # 基础信息：取第一篇为主
    first = per_results[0]

    # 情感倾向统计
    emotions = [r.emotional_tendency for r in per_results]
    emotional_tendency = max(set(emotions), key=emotions.count)

    # 合并时间线（去重）
    all_events = []
    for r in per_results:
        all_events.extend(r.event_line)
    event_line = list(dict.fromkeys(all_events))  # 去重保持顺序

    # 合并创作思路
    all_ideas = []
    for r in per_results:
        all_ideas.extend(r.creation_ideas)
    creation_ideas = list(dict.fromkeys(all_ideas))

    # 合并补充素材
    all_quotes = []
    all_details = []
    all_perspectives = []
    all_triggers = []
    for r in per_results:
        all_quotes.extend(r.supplementary.key_quotes)
        all_details.extend(r.supplementary.vivid_details)
        all_perspectives.extend(r.supplementary.unique_perspectives)
        all_triggers.extend(r.supplementary.emotional_triggers)

    # 来源 URLs
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

    流程：
    1. 从 input_path 读取文章列表
    2. 读取每篇文章内容
    3. 调用 Deep Agent 分析
    4. 汇总结果
    5. 更新 GraphState
    """
    input_path = state.get("input_path", "")
    if not input_path:
        state["error_message"] = "input_path 不能为空"
        state["error_node"] = "source_node"
        return state

    print(f"[source_node] 开始分析文章: {input_path}")

    # 1. 读取文章列表
    from wechatessay.utils.vx_util import scan_article_files, read_article

    file_list = scan_article_files(input_path)
    if not file_list:
        state["error_message"] = f"未找到文章文件: {input_path}"
        state["error_node"] = "source_node"
        return state

    print(f"[source_node] 发现 {len(file_list)} 篇文章")

    file_list = scan_article_files(input_path)  # 文件地址+名称
    articles = [read_article(f) for f in file_list]  # 读取每篇内容

    # 2. 读取文章内容
    for f in file_list:
        content = read_article(f)
        if content and not content.startswith("Error"):
            articles.append(content)

    if not articles:
        state["error_message"] = "未能读取任何文章内容"
        state["error_node"] = "source_node"
        return state

    # 3. 准备工具并创建 Agent
    base_tools = get_base_tools()
    mcp_tools = await get_total_tools()
    total_tools = list(base_tools) + list(mcp_tools)

    agent = _create_source_agent(total_tools)

    # 4. 分析文章
    per_results = _analyze_articles(articles, agent)

    if not per_results:
        state["error_message"] = "文章分析未产出任何结果"
        state["error_node"] = "source_node"
        return state

    # 5. 汇总
    total_result = _merge_to_total(per_results)

    # 6. 更新状态
    state["per_article_results"] = per_results
    state["total_article_results"] = total_result
    state["current_node"] = "source_node"
    state["node_status"]["source_node"] = "completed"

    # 7. 保存到短期记忆
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
    """source_node 同步入口。"""
    import asyncio
    return asyncio.run(source_node_async(state))
