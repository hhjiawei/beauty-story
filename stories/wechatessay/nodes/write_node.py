import json
from typing import Optional
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from utils.json_util import parse_json_response
from wechatessay.config import composite_backend, store
from wechatessay.prompts.vx_prompt import WRITE_PROMPT
from wechatessay.states.vx_state import (
    GraphState,
    ArticlePlotNode,
    ArticleOutputNode,
    ArticlePart,
)

import os

# deepseek-reasoner
OPENAI_API_KEY = "sk-0638b83c1e6a47eca1aeade34c493f6a"
OPENAI_API_BASE = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

# # qwen  sk-5fd1dda940aa46d282873be7e02fcd82
# OPENAI_API_KEY = "sk-5fd1dda940aa46d282873be7e02fcd82"
# OPENAI_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# MODEL_NAME = "qwen3.6-plus"

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE

llm = ChatOpenAI(
    model=MODEL_NAME,
    temperature=1.5,
)


async def write_node(state: GraphState) -> dict:
    """
    基于写作指令（plot_result）生成完整的公众号文章，
    输出 ArticleOutputNode（包含分段落、金句、转发语等）。
    """
    # 1. 获取必要输入
    plot = state.get("plot_result", {})

    # 2. 格式化输入数据为 JSON 字符串
    if hasattr(plot, "model_dump"):
        plot_str = json.dumps(plot.model_dump(), ensure_ascii=False, indent=2)
    else:
        plot_str = json.dumps(plot, ensure_ascii=False, indent=2)

    # 3. 创建 Deep Agent（不需要额外工具）
    agent = create_deep_agent(
        model=llm,
        tools=[],
        backend=composite_backend,
        store=store,
    )

    # 4. 格式化完整提示词（注入写作指令）
    filled_prompt = WRITE_PROMPT.format(plot_result=plot_str)

    try:
        response = await agent.ainvoke({
            "messages": [{"role": "user", "content": filled_prompt}]
        })

        # 提取最后一条消息的内容（字符串）
        content = response["messages"][-1].content

        # 解析 JSON 响应（该函数会清理 markdown 并返回 dict 或 list）
        parsed_data = parse_json_response(content)

        # 根据输出格式，parsed_data 应该是一个列表，每个元素对应一个 ArticlePart
        if isinstance(parsed_data, list):
            parts = [ArticlePart.model_validate(item) for item in parsed_data]
        else:
            # 兼容可能包装的对象形式（如 {"parts": [...]}）
            if "parts" in parsed_data:
                parts = [ArticlePart.model_validate(item) for item in parsed_data["parts"]]
            else:
                raise ValueError("解析结果不是数组且不包含 'parts' 字段")

        # 构建最终的输出节点
        result = ArticleOutputNode(parts=parts)

    except Exception as e:
        return {
            "error": f"文章生成节点执行失败: {str(e)}",
            "raw_response": {"exception": str(e), "last_content": content if 'content' in locals() else None},
            "current_node": "write_node",
        }

    # 5. 返回更新状态
    return {
        "article_output": result,
        "raw_response": None,
        "current_node": "write_node",
        "error": None,
    }
