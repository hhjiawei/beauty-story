import json
from typing import Optional
from deepagents import create_deep_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI  # 假设使用 OpenAI 模型


from wechatessay.prompts.vx_prompt import COLLECT_PROMPT
from wechatessay.states.vx_state import GraphState, ArticleSearchNode
from wechatessay.tools.vx_tools import tavily_web_search


async def search_collect_node(state: GraphState) -> dict:
    """
    负责基于热点追踪表进行网络搜索补充，输出结构化资料收集结果。
    """

    # 1. 获取热点追踪表内容
    analysis = state.get("analysis_result", {})

    # 2. 格式化提示词，注入 analysis_result
    analysis_str = json.dumps(analysis, ensure_ascii=False, indent=2) if isinstance(analysis, dict) else str(analysis)

    # 3. 创建 Deep Agent
    llm = ChatOpenAI(model="gpt-4o", temperature=0.2)  # 根据实际配置调整

    try:

        agent = create_deep_agent(
            model=llm,
            tools=[tavily_web_search],
            system_prompt="",
            response_format=ArticleSearchNode
        )

        filled_prompt = COLLECT_PROMPT.format(analysis_result=analysis_str)
        response = await agent.ainvoke({
            "messages": [{"role": "user", "content": filled_prompt}]
        })

        # 提取结构化输出（假设 deepagents 按常规 LangChain 方式存放）
        if hasattr(response, "structured_response"):
            result = response.structured_response
        elif isinstance(response, dict) and "structured_response" in response:
            result = response["structured_response"]
        else:
            # 兜底：从最后一条消息解析 JSON
            content = response["messages"][-1].content
            result = ArticleSearchNode(**json.loads(content))

    except Exception as e:
        return {
            "error": f"资料收集节点执行失败: {str(e)}",
            "raw_response": {"exception": str(e)},
            "current_node": "search_collect_node"
        }

    # 5. 返回更新后的状态
    return {
        "search_result": result,          # result 已经是 ArticleSearchNode 实例
        "raw_response": None,              # 可根据需要保留调试信息
        "current_node": "search_collect_node",
        "error": None
    }


