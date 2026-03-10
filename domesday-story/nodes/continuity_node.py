"""
连贯性整合部节点
检查 6 段之间的时间、地点、人物、道具连贯性
"""
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_CONTINUITY
from config.config import llm_precise

# 初始化 LLM
llm = llm_precise


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


def continuity_node(state: MainState) -> dict:
    """
    连贯性整合部节点函数

    Args:
        state: 主状态对象，包含所有段落草稿

    Returns:
        更新后的状态字典，包含连贯初稿和检查报告
    """
    print("\n" + "=" * 60)
    print("[连贯性整合部] 开始工作")
    print("=" * 60)

    # 获取所有段落
    segments = state.get("segments", [])

    # 组合所有段落文本
    segments_text = []
    for seg in segments:
        segments_text.append(
            f"===段落{seg['segment_index'] + 1}===\n{seg['content']}\n摘要：{seg['summary']}"
        )
        print(f"===段落{seg['segment_index'] + 1}===\n{seg['content']}\n摘要：{seg['summary']}")


    # 构建消息
    messages = [
        SystemMessage(content=PROMPT_CONTINUITY),
        HumanMessage(content="\n\n".join(segments_text))
    ]

    # 调用 LLM
    response = llm.invoke(messages)

    # 分离报告和正文
    content = response.content
    if "第一部分" in content and "第二部分" in content:
        parts = content.split("第二部分")
        report_str = parts[0].replace("第一部分", "").strip()
        draft = parts[1].strip() if len(parts) > 1 else content
    else:
        report_str = content
        draft = content

    # 解析报告
    report = parse_json_response(report_str)

    # 构建连贯性状态对象
    continuity = {
        "full_draft": draft,
        "continuity_report": report,
        "transition_records": [],
        "logic_continuity": report.get("logic_continuity_score", 80),
        "qa_status": "PENDING",
        "qa_feedback": ""
    }

    # 打印工作日志
    print(f"[连贯性整合部] ✅ 完成，连贯性评分：{continuity['logic_continuity']}")

    # 返回状态更新
    return {"continuity": continuity}
