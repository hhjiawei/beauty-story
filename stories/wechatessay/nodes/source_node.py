# =============================================================================
# 五、Map 阶段 Node：单篇分析
# =============================================================================
import json
import logging
import os
from pathlib import Path
from typing import List

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_openai import ChatOpenAI

from wechatessay.prompts.vx_prompt import SOURCE_REDUCE_PROMPT, SOURCE_MAP_PROMPT
from wechatessay.states.vx_state import ArticleAnalyseNode, GraphState
from wechatessay.utils.vx_util import split_articles, scan_article_files, read_article

logger = logging.getLogger(__name__)

# 配置 API
OPENAI_API_KEY = "468d6aba-3c9e-407f-ad91-d5f904662742"
OPENAI_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
MODEL_NAME = "doubao-seed-2-0-pro-260215"

# deepseek-reasoner
# OPENAI_API_KEY = "sk-0638b83c1e6a47eca1aeade34c493f6a"
# OPENAI_API_BASE = "https://api.deepseek.com"
# MODEL_NAME = "deepseek-reasoner"


# # qwen  sk-5fd1dda940aa46d282873be7e02fcd82
# OPENAI_API_KEY = "sk-5fd1dda940aa46d282873be7e02fcd82"
# OPENAI_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# MODEL_NAME = "qwen3.6-plus"

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE

model = ChatOpenAI(
    model=MODEL_NAME,
    temperature=1.5,
)


async def map_analyze_single(state: GraphState) -> GraphState:
    """
    Map 阶段：读取所有文章文件，为每篇生成独立分析。
    注意：这里用顺序执行演示，生产环境建议用 asyncio.gather 并行。
    """
    input_path = state["input_path"]
    articles_content = state.get("articles_content")

    # 1. 获取文章列表
    if articles_content:
        articles = split_articles(articles_content)
        file_list = [f"inline_article_{i}" for i in range(len(articles))]
    else:
        file_list = scan_article_files(input_path)  # 文件地址+名称
        articles = [read_article(f) for f in file_list]  # 读取每篇内容

    # 过滤空内容
    valid_pairs = [(f, a) for f, a in zip(file_list, articles) if a.strip()]
    if not valid_pairs:
        return {**state, "error": "未找到有效文章内容"}

    logger.info(f"Map 阶段：共 {len(valid_pairs)} 篇文章待分析")

    # 2. 为每篇文章创建 DeepAgent 并分析
    backend = FilesystemBackend(root_dir=Path(input_path).parent if input_path else Path.cwd())

    per_results: List[ArticleAnalyseNode] = []

    for file_path, article_text in valid_pairs:
        try:
            agent = create_deep_agent(  # 可以根据其他参数选用不同skill或者定制化
                model=model,
                backend=backend,
                tools=[],
                response_format=ArticleAnalyseNode,
                system_prompt="你是一个专业的微信公众号文章分析助手。",
            )

            prompt = SOURCE_MAP_PROMPT.format(article_content=article_text)  # 单篇截断保护
            result = await agent.ainvoke({
                "messages": [{"role": "user", "content": prompt}]
            })

            structured = result.get("structured_response")
            if isinstance(structured, dict):
                analysis = ArticleAnalyseNode.model_validate(structured)
            elif isinstance(structured, ArticleAnalyseNode):
                analysis = structured
            else:
                # 兜底解析
                msgs = result.get("messages", [])
                if msgs:
                    parsed = json.loads(msgs[-1].content)
                    analysis = ArticleAnalyseNode.model_validate(parsed)
                else:
                    raise ValueError("无结构化响应")

            per_results.append(analysis)
            logger.info(f"  ✓ {file_path} -> {analysis.hotspot_title[:30]}...")

        except Exception as e:
            logger.error(f"  ✗ {file_path} 分析失败: {e}")
            continue

    if not per_results:
        return {**state, "error": "所有文章分析均失败"}

    return {
        **state,
        "article_files": [f for f, _ in valid_pairs],
        "per_article_results": per_results,
    }


# =============================================================================
# 六、Reduce 阶段 Node：跨篇汇总
# =============================================================================

async def reduce_merge_results(state: GraphState) -> GraphState:
    """
    Reduce 阶段：将多篇分析结果汇总为一份统一的热点追踪表。
    """
    per_results = state.get("per_article_results", [])
    if not per_results:
        return {**state, "error": "Map 阶段无有效结果，无法汇总"}

    # 如果只有一篇文章，直接返回
    if len(per_results) == 1:
        return {
            **state,
            "analysis_result": per_results[0],
        }

    logger.info(f"Reduce 阶段：汇总 {len(per_results)} 篇分析结果")

    # 构建 Reduce 输入
    per_article_jsons = "\\n\\n---\\n\\n".join([
        f"【分析结果 {i + 1}】\\n{json.dumps(r.model_dump(by_alias=True), ensure_ascii=False, indent=2)}"
        for i, r in enumerate(per_results)
    ])

    backend = FilesystemBackend(root_dir=Path.cwd())

    try:
        agent = create_deep_agent(
            model=model,
            backend=backend,
            response_format=ArticleAnalyseNode,
            system_prompt="你是一个信息整合专家，擅长合并多源信息。",
        )

        prompt = SOURCE_REDUCE_PROMPT.format(per_article_jsons=per_article_jsons)
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": prompt}]
        })

        structured = result.get("structured_response")
        if isinstance(structured, dict):
            merged = ArticleAnalyseNode.model_validate(structured)
        elif isinstance(structured, ArticleAnalyseNode):
            merged = structured
        else:
            msgs = result.get("messages", [])
            if msgs:
                parsed = json.loads(msgs[-1].content)
                merged = ArticleAnalyseNode.model_validate(parsed)
            else:
                raise ValueError("Reduce 阶段无结构化响应")

        logger.info(f"  ✓ 汇总完成: {merged.hotspot_title}")

        return {
            **state,
            "analysis_result": merged,
            "raw_response": merged.model_dump(by_alias=True),
        }

    except Exception as e:
        logger.error(f"Reduce 汇总失败: {e}")
        # 降级：返回第一篇的结果（避免完全失败）
        return {
            "analysis_result": per_results[0]
        }


## **state 是 Python 中的 字典解包（Dictionary Unpacking） 语法。
"""
假设 state 是一个字典，比如：

state = {
    "per_article_results": [...],
    "some_other_key": "value",
    "timestamp": "2026-04-28"
}
那么 {**state, "analysis_result": merged} 等价于：

{
    "per_article_results": [...],
    "some_other_key": "value", 
    "timestamp": "2026-04-28",
    "analysis_result": merged   # ← 新增或覆盖这个键
}

"""
