from romanticstory.states.romantic_story_state import MainState


def should_continue_writing(state: MainState) -> str:
    """
    判断是否还有段落需要写作
    返回 'write' 继续循环，返回 'end' 结束
    """
    current_index = state.get("current_segment_index", 0)
    plot_state = state.get("plot_state", {})
    beat_sheet = plot_state.get("beat_sheet", [])
    total_paragraphs = len(beat_sheet)

    if current_index < total_paragraphs:
        return "write"
    else:
        return "end"