import json
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from wechatessay.utils.json_util import parse_json_response
from wechatessay.config import composite_backend, store
from wechatessay.prompts.vx_prompt import PLOT_PROMPT
from wechatessay.states.vx_state import (
    GraphState,
    ArticlePlotNode,
)



import os

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

async def plot_node(state: GraphState) -> dict:
    """
    基于写作蓝图（blueprint_result）生成详细的写作指令（情节/段落结构），
    输出 ArticlePlotNode，供后续文章生成节点使用。
    """

    # 1. 获取必要输入
    blueprint = state.get("blueprint_result", {})

    # 2. 格式化输入数据为 JSON 字符串
    if hasattr(blueprint, "model_dump"):# 序列化：支持 Pydantic 模型的 model_dump() 方法，确保 JSON 字符串格式正确。
        blueprint_str = json.dumps(blueprint.model_dump(), ensure_ascii=False, indent=2)
    else:
        blueprint_str = json.dumps(blueprint, ensure_ascii=False, indent=2)

    # 3. 创建 Deep Agent（不需要工具）
    agent = create_deep_agent(
        model=llm,
        tools=[],
        # system_prompt="",
        backend=composite_backend,
        store=store,
    )

    # 4. 格式化完整提示词（注入蓝图）
    filled_prompt = PLOT_PROMPT.format(blueprint_result=blueprint_str)

    try:
        response = await agent.ainvoke({
            "messages": [{"role": "user", "content": filled_prompt}]
        })

        # 提取最后一条消息的内容（字符串）
        content = response["messages"][-1].content

        # 解析 JSON 响应（该函数会清理 markdown 并返回 dict）
        plot_data = parse_json_response(content)

        # 将字典转换为 ArticlePlotNode 实例（Pydantic 模型）
        result = ArticlePlotNode.model_validate(plot_data)

    except Exception as e:
        return {
            "error": f"写作指令节点执行失败: {str(e)}",
            "raw_response": {"exception": str(e), "last_content": content if 'content' in locals() else None},
            "current_node": "plot_node",
        }

    # 5. 返回更新状态
    return {
        "plot_result": result,
    }




