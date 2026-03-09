"""
世界观设定部节点
负责设计末日来源、世界规则、时间线、地理环境
"""
import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_WORLD_BUILDER
from config import MODEL_NAME, TEMPERATURE

# 初始化 LLM
llm = ChatOpenAI(model=MODEL_NAME, temperature=TEMPERATURE)


def parse_json_response(content: str) -> dict:
    """
    解析 LLM 的 JSON 响应

    Args:
        content: LLM 返回的内容

    Returns:
        解析后的字典
    """
    try:
        # 清理 Markdown 代码块标记
        content = content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        content = content.strip()

        # 解析 JSON
        return json.loads(content)
    except Exception as e:
        print(f"[JSON 解析错误] {e}")
        return {}


def world_builder_node(state: MainState) -> dict:
    """
    世界观设定部节点函数

    Args:
        state: 主状态对象，包含用户输入等信息

    Returns:
        更新后的状态字典，包含世界观设定
    """
    print("\n" + "=" * 60)
    print("[世界观设定部] 开始工作")
    print("=" * 60)

    # 构建消息
    messages = [
        SystemMessage(content=PROMPT_WORLD_BUILDER),
        HumanMessage(content=state["user_input"])
    ]

    # 调用 LLM
    response = llm.invoke(messages)

    # 解析 JSON 响应
    world_data = parse_json_response(response.content)

    # 构建世界观状态对象
    world_building = {
        "apocalypse_name": world_data.get("apocalypse_name", "未知末日"),
        "apocalypse_source": world_data.get("apocalypse_source", ""),
        "outbreak_date": world_data.get("outbreak_date", ""),
        "transmission_rules": world_data.get("transmission_rules", ""),
        "mutation_symptoms": world_data.get("mutation_symptoms", ""),
        "key_locations": world_data.get("key_locations", []),
        "timeline": world_data.get("timeline", []),
        "special_rules": world_data.get("special_rules", ""),
        "qa_status": "PENDING",
        "qa_feedback": ""
    }

    # 打印工作日志
    print(f"[世界观设定部] ✅ 完成：{world_building['apocalypse_name']}")
    print(f"[世界观设定部] 爆发时间：{world_building['outbreak_date']}")

    # 返回状态更新
    return {
        "world_building": world_building,
        "iteration_count": state["iteration_count"] + 1
    }
