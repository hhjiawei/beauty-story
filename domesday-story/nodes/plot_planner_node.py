"""
剧情策划部节点
负责规划 6000 字情绪曲线、爽点分布、时间地点流程
"""
import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_PLOT_PLANNER
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


def plot_planner_node(state: MainState) -> dict:
    """
    剧情策划部节点函数

    Args:
        state: 主状态对象，包含世界观、金手指、人物关系

    Returns:
        更新后的状态字典，包含剧情大纲
    """
    print("\n" + "=" * 60)
    print("[剧情策划部] 开始工作")
    print("=" * 60)

    # 构建消息
    messages = [
        SystemMessage(content=PROMPT_PLOT_PLANNER),
        HumanMessage(content=f"""
        世界观设定：{json.dumps(state['world_building'], ensure_ascii=False)}
        金手指配置：{json.dumps(state['golden_finger'], ensure_ascii=False)}
        人物关系：{json.dumps(state['character'], ensure_ascii=False)}
        """)
    ]

    # 调用 LLM
    response = llm.invoke(messages)

    # 解析 JSON 响应
    plot_data = parse_json_response(response.content)

    # 获取情节大纲
    beat_sheet = plot_data.get("beat_sheet", [])

    # 确保至少 6 段
    if len(beat_sheet) < 6:
        for i in range(len(beat_sheet), 6):
            beat_sheet.append({
                "segment": i + 1,
                "word_range": f"{i * 1000}-{(i + 1) * 1000}",
                "time": f"第{i + 1}阶段",
                "location": "未指定",
                "characters": ["主角"],
                "character_states": {"主角": "正常"},
                "plot_summary": f"第{i + 1}段情节",
                "hook_points": ["爽点"],
                "key_props": [],
                "transition_to_next": "自然过渡"
            })

    # 构建剧情状态对象
    plot = {
        "beat_sheet": beat_sheet,
        "hook_points": plot_data.get("hook_points", []),
        "transition_design": "",
        "opening_hook": plot_data.get("opening_hook", ""),
        "ending_hook": plot_data.get("ending_hook", ""),
        "timeline_summary": plot_data.get("timeline_summary", ""),
        "qa_status": "PENDING",
        "qa_feedback": ""
    }

    # 打印工作日志
    print(f"[剧情策划部] ✅ 完成：{len(plot['beat_sheet'])} 个段落")

    # 返回状态更新
    return {"plot": plot}
