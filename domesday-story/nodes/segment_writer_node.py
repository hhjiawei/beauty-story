"""
分块写作部节点
按大纲分 6 段撰写，严格遵循时间地点人物状态
"""
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_SEGMENT_WRITER
from config.config import llm_creative  # ✅ 使用创意 LLM，温度更高

# 初始化 LLM
llm = llm_creative


def extract_text_and_summary(content: str) -> tuple:
    """
    从写作输出中提取正文和摘要

    Args:
        content: 写作输出内容

    Returns:
        (正文，摘要) 元组
    """
    if "===段落摘要===" in content:
        parts = content.split("===段落摘要===")
        text = parts[0].strip()
        summary = parts[1].strip() if len(parts) > 1 else ""
        return text, summary
    else:
        return content.strip(), ""


def segment_writer_node(state: MainState) -> dict:
    """
    分块写作部节点函数 - 单次写一段

    Args:
        state: 主状态对象，包含剧情大纲和已写段落

    Returns:
        更新后的状态字典，包含新写的段落
    """
    # 获取当前段落索引
    idx = state.get("current_segment_index", 0)
    beat_sheet = state["plot"]["beat_sheet"]

    # 检查是否已写完所有段落
    if idx >= len(beat_sheet):
        return {}

    print("\n" + "=" * 60)
    print(f"[分块写作部] 正在写第 {idx + 1}/{len(beat_sheet)} 段")
    print("=" * 60)

    # 获取当前段落大纲
    beat = beat_sheet[idx]

    # 获取前文摘要
    segments = state.get("segments", [])
    previous_summary = segments[-1].get("summary", "故事开头") if segments else "故事开头"

    # 构建消息
    messages = [
        SystemMessage(content=PROMPT_SEGMENT_WRITER),
        HumanMessage(content=f"""
        索引：{idx + 1}/{len(beat_sheet)}
        时间：{beat.get('time', '未指定')}
        地点：{beat.get('location', '未指定')}
        在场人物：{beat.get('characters', ['主角'])}
        人物状态：{beat.get('character_states', {})}
        前文摘要：{previous_summary}
        当前段落大纲：{beat.get('plot_summary', '')}
        风格要求：短句密集、黑色幽默、强对比、不圣母、复仇狠辣
        """)
    ]

    # 调用 LLM
    response = llm.invoke(messages)

    # 提取正文和摘要
    text, summary = extract_text_and_summary(response.content)

    # 构建段落状态对象
    segment = {
        "segment_index": idx,
        "content": text,
        "summary": summary,
        "word_count": len(text),
        "time": beat.get('time', ''),
        "location": beat.get('location', ''),
        "characters": beat.get('characters', []),
        "character_states": beat.get('character_states', {}),
        "key_props": beat.get('key_props', []),
        "qa_status": "PENDING",
        "qa_feedback": ""
    }

    # 添加到 segments 列表
    segments.append(segment)

    # 打印工作日志
    print(f"[分块写作部] ✅ 完成第 {idx + 1} 段，生成 {segment['word_count']} 字")

    # 返回状态更新
    return {
        "segments": segments,
        "current_segment_index": idx + 1
    }
