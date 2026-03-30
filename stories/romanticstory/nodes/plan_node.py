import os

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from romanticstory.config.config import llm
from romanticstory.prompts.romantic_story_prompt import PLAN_SUMMARY_PROMPT

from romanticstory.states.romantic_story_state import MainState
from langchain_core.messages import HumanMessage, SystemMessage

from romanticstory.tools.web_search import internet_search
from utils.json_util import parse_json_response


# 策划节点，需要灵感和天马行空的设计，大模型也需要偏设计一些的 条理要清晰，要有逻辑   deepseek-reasoner

# 配置 API
OPENAI_API_KEY = "sk-0638b83c1e6a47eca1aeade34c493f6a"
OPENAI_API_BASE = "https://api.deepseek.com"
MODEL_NAME = "deepseek-reasoner"

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE

# 初始化 LLM
"""
temperature 参数默认为 1.0。

我们建议您根据如下表格，按使用场景设置 temperature。
场景	温度
代码生成/数学解题 	0.0
数据抽取/分析	1.0
通用对话	1.3
翻译	1.3
创意类写作/诗歌创作	1.5  当模型的「温度」较高时（如 0.8、1 或更高），模型会更倾向于从较多样且不同的词汇中选择，这使得生成的文本风险性更高、创意性更强，
"""
llm = ChatOpenAI(
    model=MODEL_NAME,
    temperature=1.5,
)

def planner_node(state: MainState) -> dict:
    """
    策划层节点函数
    负责生成故事核心架构、三线构建及矛盾设定
    """
    print("\n" + "=" * 60)
    print("[策划层] 开始工作")
    print("=" * 60)

    # 构建消息
    # messages = [
    #     SystemMessage(content=PLAN_SUMMARY_PROMPT),
    #     HumanMessage(content=f"请根据以下灵感创作策划案：{state.get('user_input', '')}")
    # ]

    # 调用 LLM
    # response = llm.invoke(messages)

    agent = create_deep_agent(
        model=llm,
        system_prompt=PLAN_SUMMARY_PROMPT,

    )

    response = agent.invoke({"messages": [HumanMessage(content=f"请根据以下灵感创作策划案：{state.get('user_input', '')}")]})
    response = response["messages"][-1]

    # 解析 JSON 响应
    plan_data = parse_json_response(response.content)

    # 构建策划状态对象
    plan_state = {
        "story_summary": plan_data.get("story_summary", ""),
        "hook": plan_data.get("hook", ""),
        "core_topic": plan_data.get("core_topic", ""),
        "story_backend": plan_data.get("story_backend", ""),
        "dual_line_intersections": plan_data.get("dual_line_intersections", []),
        "three_lines_info": plan_data.get("three_lines_info", {}),
        "core_conflicts": plan_data.get("core_conflicts", []),
        "extra_plan": plan_data.get("extra_plan", {})
    }

    # 打印工作日志
    print(f"[策划层] ✅ 完成：{plan_state['core_topic']}")
    print(f"[策划层] 开篇爆点：{plan_state['hook'][:50]}...")

    # 返回状态更新
    return {"plan_state": plan_state}
