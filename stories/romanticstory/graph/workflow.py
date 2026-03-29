# romantic_story/workflow.py
from langgraph.graph import StateGraph, END

from romanticstory.nodes.character_node import character_node
from romanticstory.nodes.plan_node import planner_node
from romanticstory.nodes.plot_node import plot_node
from romanticstory.nodes.write_node import writer_node
from romanticstory.nodes.polish_node import polish_node  # ✅ 新增导入
from romanticstory.states.romantic_story_state import MainState


def should_continue_writing(state: MainState) -> str:
    """
    判断是否还有段落需要写作
    返回 'write' 继续循环，返回 'polish' 进入抛光节点
    """
    current_index = state.get("current_segment_index", 0)
    plot_state = state.get("plot_state", {})
    beat_sheet = plot_state.get("beat_sheet", [])
    total_paragraphs = len(beat_sheet)

    if current_index < total_paragraphs:
        return "write"
    else:
        print("\n[工作流] ✅ 所有段落写作完成，进入抛光阶段")
        return "polish"


def should_continue_polishing(state: MainState) -> str:
    """
    判断是否还有段落需要抛光
    返回 'polish' 继续循环，返回 'end' 结束
    """
    current_polish_index = state.get("current_polish_index", 0)
    segments = state.get("segments", [])
    total_segments = len(segments)

    if current_polish_index < total_segments:
        print(f"[工作流] 📝 继续抛光：段落 {current_polish_index + 1}/{total_segments}")
        return "polish"
    else:
        print(f"\n[工作流] ✅ 所有段落抛光完成 ({total_segments}段)")
        return "end"


def create_workflow():
    # 初始化图
    workflow = StateGraph(MainState)

    # 1. 添加节点
    workflow.add_node("planner", planner_node)
    workflow.add_node("character", character_node)
    workflow.add_node("plot", plot_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("polish", polish_node)  # ✅ 新增抛光节点

    # 2. 设置入口
    workflow.set_entry_point("planner")

    # 3. 添加边 (线性流程)
    workflow.add_edge("planner", "character")
    workflow.add_edge("character", "plot")
    workflow.add_edge("plot", "writer")

    # 4. 添加写作循环条件边
    workflow.add_conditional_edges(
        "writer",
        should_continue_writing,
        {
            "write": "writer",
            "polish": "polish"
        }
    )

    # 5. 添加抛光循环条件边
    workflow.add_conditional_edges(
        "polish",
        should_continue_polishing,
        {
            "polish": "polish",  # 继续抛光下一段
            "end": END  # 所有段落抛光完成
        }
    )

    # 编译图
    app = workflow.compile()
    return app
