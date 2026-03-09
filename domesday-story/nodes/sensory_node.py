"""
感官修饰部节点
增加成人向感官张力，提升阅读粘性
"""
import json
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_SENSORY
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


def sensory_node(state: MainState) -> dict:
    """
    感官修饰部节点函数

    Args:
        state: 主状态对象，包含节奏优化稿

    Returns:
        更新后的状态字典，包含感官增强稿
    """
    print("\n" + "=" * 60)
    print("[感官修饰部] 开始工作")
    print("=" * 60)

    # 构建消息
    messages = [
        SystemMessage(content=PROMPT_SENSORY),
        HumanMessage(content=state["rhythm"]["optimized_draft"])
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

    # 构建感官状态对象
    sensory = {
        "sensory_enhanced": draft,
        "sensory_report": report,
        "sensory_count": report.get("sensory_count", 0),
        "compliance_check": report.get("compliance_status") == "PASS",
        "qa_status": "PENDING",
        "qa_feedback": ""
    }

    # 打印工作日志
    print(f"[感官修饰部] ✅ 完成，感官描写：{sensory['sensory_count']} 处")

    # 返回状态更新
    return {"sensory": sensory}
