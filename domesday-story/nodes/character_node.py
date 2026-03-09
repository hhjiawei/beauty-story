"""
人物关系部节点
负责设计主角、仇人、盟友的完整档案和关系网
"""
import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_CHARACTER
from config import MODEL_NAME, TEMPERATURE

# 初始化 LLM
llm = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE)


def parse_json_response(content: str) -> dict:
    """解析 LLM 的 JSON 响应"""
    try:
        content = content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        content = content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"[JSON 解析错误] {e}")
        return {}


def character_node(state: MainState) -> dict:
    """
    人物关系部节点函数

    Args:
        state: 主状态对象，包含世界观和金手指配置

    Returns:
        更新后的状态字典，包含人物关系图谱
    """
    print("\n" + "=" * 60)
    print("[人物关系部] 开始工作")
    print("=" * 60)

    # 构建消息
    messages = [
        SystemMessage(content=PROMPT_CHARACTER),
        HumanMessage(content=f"""
        世界观设定：{json.dumps(state['world_building'], ensure_ascii=False)}
        金手指配置：{json.dumps(state['golden_finger'], ensure_ascii=False)}
        """)
    ]

    # 调用 LLM
    response = llm.invoke(messages)

    # 解析 JSON 响应
    char_data = parse_json_response(response.content)

    # 构建人物关系状态对象
    character = {
        "protagonist": char_data.get("protagonist", {}),
        "villains": char_data.get("villains", []),
        "allies": char_data.get("allies", []),
        "relationship_timeline": char_data.get("relationship_timeline", []),
        "qa_status": "PENDING",
        "qa_feedback": ""
    }

    # 打印工作日志
    print(f"[人物关系部] ✅ 完成：{len(character['villains'])} 个仇人")

    # 返回状态更新
    return {"character": character}
