import json

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI  # 假设使用 OpenAI 模型

from wechatessay.config import composite_backend, store
from wechatessay.tools.mcp_tools.mcp_tool import trendradar_manager
from wechatessay.prompts.vx_prompt import COLLECT_PROMPT, COLLECT_SYSTEM_PROMPT
from wechatessay.states.vx_state import GraphState, ArticleSearchNode
from wechatessay.tools.base_tools import tavily_web_search, create_file, read_file, shell_exec

import os

from wechatessay.utils.vx_util import parse_json_response

# deepseek-reasoner
OPENAI_API_KEY = "sk-0638b83c1e6a47eca1aeade34c493f6a"
OPENAI_API_BASE = "https://api.deepseek.com"
MODEL_NAME = "deepseek-reasoner"

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


async def search_collect_node(state: GraphState) -> dict:
    """
    负责基于热点追踪表进行网络搜索补充，输出结构化资料收集结果。
    """

    # 1. 获取热点追踪表内容
    analysis = state.get("analysis_result", {})

    # 2. 格式化提示词，注入 analysis_result
    analysis_str = json.dumps(analysis, ensure_ascii=False, indent=2) if isinstance(analysis, dict) else str(analysis)

    mcp_tools = await trendradar_manager.get_tools()

    try:

        agent = create_deep_agent(
            model=llm,
            tools=[tavily_web_search, create_file, read_file, shell_exec] + mcp_tools,
            system_prompt=COLLECT_SYSTEM_PROMPT,
            backend=composite_backend,
            skills=["/skills/trendradar-mcp","/skills/web-access"],
            store=store,
        )

        filled_prompt = COLLECT_PROMPT.format(analysis_result=analysis_str)

        response = await agent.ainvoke({
            "messages": [{"role": "user", "content": filled_prompt}]
        })

        # 提取最后一条消息的内容（字符串）
        content = response["messages"][-1].content

        # 解析 JSON 响应（该函数会清理 markdown 并返回 dict）
        collect_data = parse_json_response(content)


    except Exception as e:
        return {
            "error": f"资料收集节点执行失败: {str(e)}",
            "raw_response": {"exception": str(e)},
            "current_node": "search_collect_node"
        }

    # 5. 返回更新后的状态
    return {
        "search_result": collect_data,  # result 已经是 ArticleSearchNode 实例
    }
