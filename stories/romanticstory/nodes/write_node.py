# romantic_story/nodes/writer.py
import json
from romanticstory.config.config import get_agent
from romanticstory.prompts.romantic_story_prompt import WRITE_PROMPT
from romanticstory.states.romantic_story_state import MainState, SegmentState


def writer_node(state: MainState) -> dict:
    """
    分块写作部：根据大纲当前段落进行写作
    """
    current_index = state.get("current_segment_index", 0)
    plot_state = state.get("plot_state", {})
    beat_sheet = plot_state.get("beat_sheet", [])

    # 安全检查
    if current_index >= len(beat_sheet):
        return {"current_segment_index": current_index}

    current_paragraph = beat_sheet[current_index]

    # 准备写作上下文
    writing_context = {
        "paragraph_info": current_paragraph,
        "previous_segments": state.get("segments", [])[-2:]  # 带上最近两段以保持连贯
    }

    agent = get_agent(WRITE_PROMPT)
    messages = [
        {"role": "user",
         "content": f"请撰写第 {current_index + 1} 段内容：{json.dumps(writing_context, ensure_ascii=False)}"}
    ]

    response = agent.invoke(messages)
    content = response.content if hasattr(response, 'content') else str(response)

    # 构建 SegmentState
    new_segment: SegmentState = {
        "para_id": current_paragraph.get("para_id", f"para_{current_index}"),
        "content": content
    }

    # 更新 segments 列表 (LangGraph 默认是覆盖，所以需要手动合并)
    existing_segments = state.get("segments", [])
    updated_segments = existing_segments + [new_segment]

    return {
        "segments": updated_segments,
        "current_segment_index": current_index + 1
    }