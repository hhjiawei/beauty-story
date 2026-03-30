# romantic_story/nodes/plot.py
import json
import os

from deepagents import create_deep_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from romanticstory.config.config import  llm
from romanticstory.prompts.romantic_story_prompt import PLOT_PROMPT
from romanticstory.states.romantic_story_state import MainState
from utils.json_util import parse_json_response


# 大纲 需要逻辑清晰，需要把前面的人物形象和剧情相结合并产出，需要合理的推理能力 deepseek-reasoner


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
    temperature=1.0,
)





def plot_node(state: MainState) -> dict:
    """
    剧情策划部：根据策划和人物生成详细大纲 (Beat Sheet)
    """
    plan_state = state.get("plan_state", {})
    character_state = state.get("character_state", {})

    # messages = [
    #     SystemMessage(content=PLOT_PROMPT),
    #     HumanMessage(content=f"基于以下信息生成章节大纲：\n{json.dumps({'plan': plan_state, 'characters': character_state}, ensure_ascii=False)}")
    # ]
    #
    # # 调用 LLM
    # response = llm.invoke(messages)


    agent = create_deep_agent(
        model=llm,
        system_prompt=PLOT_PROMPT,
    )

    response = agent.invoke({"messages": [HumanMessage(content=f"基于以下信息生成章节大纲：\n{json.dumps({'plan': plan_state, 'characters': character_state}, ensure_ascii=False)}")]})
    response = response["messages"][-1]

    # 解析 JSON 响应
    char_data = parse_json_response(response.content)

    # 初始化写作索引
    return {
        "plot_state": char_data,
        "current_segment_index": 0
    }













