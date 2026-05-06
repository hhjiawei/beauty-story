import json
from typing import Optional
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from utils.json_util import parse_json_response
from wechatessay.config import composite_backend, store
from wechatessay.prompts.vx_prompt import BLUEPRINT_PROMPT
from wechatessay.states.vx_state import GraphState, ArticleBlueprintNode


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

async def blueprint_node(state: GraphState) -> dict:
    """
    基于热点追踪表（analysis_result）和资料收集结果（search_result）
    生成写作蓝图（角度、风格、模板、计划）。
    """

    # 1. 获取必要输入
    analysis = state.get("analysis_result", {})
    search = state.get("search_result", {})

    # 2. 格式化输入数据为 JSON 字符串
    analysis_str = json.dumps(analysis, ensure_ascii=False, indent=2) if hasattr(analysis, "model_dump") else str(analysis)
    search_str = json.dumps(search, ensure_ascii=False, indent=2) if hasattr(search, "model_dump") else str(search)

    # 3. 创建 Deep Agent（不额外提供工具，仅依靠模型能力进行写作策划）
    agent = create_deep_agent(
        model=llm,
        tools=[],                           # 蓝图生成一般不需要联网搜索
        # system_prompt="",
        backend=composite_backend,
        store=store,
    )

    # 4. 格式化完整提示词（注入两个分析结果）
    filled_prompt = BLUEPRINT_PROMPT.format(
        analysis_result=analysis_str,
        search_result=search_str,
    )

    try:
        response = await agent.ainvoke({
            "messages": [{"role": "user", "content": filled_prompt}]
        })

        # 提取最后一条消息的内容
        content = response["messages"][-1]

        # 解析 JSON 响应
        char_data = parse_json_response(response.content)

    except Exception as e:
        return {
            "error": f"写作蓝图节点执行失败: {str(e)}",
            "raw_response": {"exception": str(e), "last_content": content if 'content' in locals() else None},
            "current_node": "blueprint_node",
        }

    # 5. 返回更新状态
    return {
        "blueprint_result": char_data,
        "raw_response": None,
        "current_node": "blueprint_node",
        "error": None,
    }