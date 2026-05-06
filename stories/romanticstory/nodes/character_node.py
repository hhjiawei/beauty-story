# romantic_story/nodes/character.py
import os

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from romanticstory.config.config import  llm
from romanticstory.prompts.romantic_story_prompt import CHARACTER_PROMPT
from romanticstory.states.romantic_story_state import MainState
import json
from langchain_core.messages import HumanMessage

from wechatessay.utils.json_util import parse_json_response


# 策划节点，需要灵感和天马行空的设计，大模型也需要偏设计一些的 条理要清晰，要有逻辑   deepseek-reasoner

OPENAI_API_KEY = "468d6aba-3c9e-407f-ad91-d5f904662742"
OPENAI_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
MODEL_NAME = "doubao-seed-2-0-pro-260215"

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
    max_tokens=30000
)



def character_node(state: MainState) -> dict:
    """
    人物关系部节点函数
    负责设计主角、配角等的完整档案和关系网
    """
    print("\n" + "=" * 60)
    print("[人物关系部] 开始工作")
    print("=" * 60)

    # # 构建消息
    # messages = [
    #     SystemMessage(content=CHARACTER_PROMPT),
    #     HumanMessage(content=f"""
    #     策划案设定：{json.dumps(state.get('plan_state', {}), ensure_ascii=False)}
    #     """)
    # ]
    #
    # # 调用 LLM
    # response = llm.invoke(messages)


    agent = create_deep_agent(
        model=llm,
        system_prompt=CHARACTER_PROMPT,
    )

    response = agent.invoke({"messages": [HumanMessage(content=f"""
        策划案设定：{json.dumps(state.get('plan_state', {}), ensure_ascii=False)}
        """)]})
    response = response["messages"][-1]

    # 解析 JSON 响应
    char_data = parse_json_response(response.content)

    # 构建人物关系状态对象
    character_state = {
        "characters": char_data.get("characters", []),
        "network": char_data.get("network", [])
    }

    # 打印工作日志
    print(f"[人物关系部] ✅ 完成：共设计 {len(character_state['characters'])} 个角色")
    if len(character_state['characters']) > 0:
        print(f"[人物关系部] 主角：{character_state['characters'][0]['basic']['name']}")

    # 返回状态更新
    return {"character_state": character_state}














