"""
幽默注入部节点
植入黑色幽默和吐槽，缓解压抑
"""
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_HUMOR
from config.config import llm_creative

# 初始化 LLM
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


def humor_node(state: MainState) -> dict:
    """
    幽默注入部节点函数

    Args:
        state: 主状态对象，包含感官增强稿

    Returns:
        更新后的状态字典，包含幽默增强稿
    """
    print("\n" + "=" * 60)
    print("[幽默注入部] 开始工作")
    print("=" * 60)

    # 构建消息
    messages = [
        SystemMessage(content=PROMPT_HUMOR),
        HumanMessage(content=state["sensory"]["sensory_enhanced"])
    ]

    # 调用 LLM
    response = llm.invoke(messages)

    # 分离报告和正文
    content = response.content

    # 解析报告
    # draft = parse_json_response(content)

    # 构建幽默状态对象
    humor = {
        "humor_enhanced": content,
        "qa_status": "PENDING",
        "qa_feedback": ""
    }

    # 打印工作日志
    print(f"[幽默注入部] ✅ 完成")

    # 返回状态更新
    return {"humor": humor}
