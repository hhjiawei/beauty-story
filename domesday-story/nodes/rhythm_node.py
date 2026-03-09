"""
节奏控制部节点
优化叙事节奏，确保快节奏强冲突，删除注水内容
"""
import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_RHYTHM
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


def rhythm_node(state: MainState) -> dict:
    """
    节奏控制部节点函数

    Args:
        state: 主状态对象，包含连贯初稿

    Returns:
        更新后的状态字典，包含节奏优化稿
    """
    print("\n" + "=" * 60)
    print("[节奏控制部] 开始工作")
    print("=" * 60)

    # 构建消息
    messages = [
        SystemMessage(content=PROMPT_RHYTHM),
        HumanMessage(content=state["continuity"]["full_draft"])
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

    # 构建节奏状态对象
    rhythm = {
        "optimized_draft": draft,
        "rhythm_report": report,
        "short_sentence_ratio": report.get("short_sentence_ratio", 0.7),
        "paragraph_density": report.get("paragraph_density", 15),
        "qa_status": "PENDING",
        "qa_feedback": ""
    }

    # 打印工作日志
    print(f"[节奏控制部] ✅ 完成，短句占比：{rhythm['short_sentence_ratio']}")

    # 返回状态更新
    return {"rhythm": rhythm}
