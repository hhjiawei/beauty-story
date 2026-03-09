"""
图谱构建 - LangGraph 状态图和流程控制
"""
from langgraph.graph import StateGraph, END
from states.storyState import MainState
from nodes import (
    world_builder_node,
    golden_finger_node,
    character_node,
    plot_planner_node,
    segment_writer_node,
    continuity_node,
    rhythm_node,
    sensory_node,
    humor_node,
    format_node,
    node_qa_node,
    final_qa_node
)


def check_segment_finished(state: MainState) -> str:
    """检查是否所有段落写完"""
    current_idx = state.get("current_segment_index", 0)
    total = len(state.get("plot", {}).get("beat_sheet", []))

    print(f"[路由] 段落进度：{current_idx}/{total}")

    if current_idx >= total:
        return "finish"
    else:
        return "continue"


def check_final_qa(state: MainState) -> str:
    """检查终稿质检"""
    final_qa = state.get("final_qa", {})

    if final_qa.get("final_status") == "PASS":
        return "save"
    else:
        return "rewrite"


# ================= 构建主图 =================

main_graph = StateGraph(MainState)

# --- 添加所有节点 ---
# 前期中台
main_graph.add_node("world_builder", world_builder_node)
main_graph.add_node("golden_finger", golden_finger_node)
main_graph.add_node("character", character_node)
main_graph.add_node("plot_planner", plot_planner_node)

# 生产流水线
main_graph.add_node("segment_writer", segment_writer_node)
main_graph.add_node("continuity", continuity_node)
main_graph.add_node("rhythm", rhythm_node)

# 后期工坊
main_graph.add_node("sensory", sensory_node)
main_graph.add_node("humor", humor_node)
main_graph.add_node("format", format_node)

# 品控中心
main_graph.add_node("node_qa", node_qa_node)
main_graph.add_node("final_qa", final_qa_node)

# --- 设置流程 ---

# 入口点
main_graph.set_entry_point("world_builder")

# 前期中台流程
main_graph.add_edge("world_builder", "golden_finger")
main_graph.add_edge("golden_finger", "character")
main_graph.add_edge("character", "plot_planner")

# 生产流水线 - 分块写作循环
main_graph.add_edge("plot_planner", "segment_writer")

# 段落写作循环
main_graph.add_conditional_edges(
    "segment_writer",
    check_segment_finished,
    {
        "continue": "segment_writer",
        "finish": "continuity"
    }
)

# 连贯性→节奏→感官→幽默→格式
main_graph.add_edge("continuity", "rhythm")
main_graph.add_edge("rhythm", "sensory")
main_graph.add_edge("sensory", "humor")
main_graph.add_edge("humor", "format")

# 品控流程
main_graph.add_edge("format", "final_qa")

# 终稿质检
main_graph.add_conditional_edges(
    "final_qa",
    check_final_qa,
    {
        "save": END,
        "rewrite": "segment_writer"
    }
)

# --- 编译图谱 ---
app = main_graph.compile()

# 导出 app 供 main.py 使用
__all__ = ["app"]
