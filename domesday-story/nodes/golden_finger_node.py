"""
金手指设计部节点
负责设计主角能力系统，确保开局巅峰且有合理限制
"""
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_GOLDEN_FINGER
from config.config import llm_creative

# 初始化 LLM 创造性的llm
llm = llm_creative


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


def golden_finger_node(state: MainState) -> dict:
    """
    金手指设计部节点函数

    Args:
        state: 主状态对象，包含世界观设定等信息

    Returns:
        更新后的状态字典，包含金手指配置
    """
    print("\n" + "=" * 60)
    print("[金手指设计部] 开始工作")
    print("=" * 60)

    # 构建消息
    messages = [
        SystemMessage(content=PROMPT_GOLDEN_FINGER),
        HumanMessage(content=json.dumps(state["world_building"], ensure_ascii=False))
    ]

    # 调用 LLM
    response = llm.invoke(messages)

    # 解析 JSON 响应
    gf_data = parse_json_response(response.content)

    # 构建金手指状态对象
    golden_finger = {
        "ability_type": gf_data.get("ability_type", "重生"),
        "activation_condition": gf_data.get("activation_condition", ""),
        "functions": gf_data.get("functions", []),
        "limitations": gf_data.get("limitations", ""),
        "revenge_advantages": gf_data.get("revenge_advantages", []),
        "growth_path": gf_data.get("growth_path", ""),
        "qa_status": "PENDING",
        "qa_feedback": ""
    }

    # 打印工作日志
    print(f"[金手指设计部] ✅ 完成：{golden_finger['ability_type']}")

    # 返回状态更新
    return {"golden_finger": golden_finger}