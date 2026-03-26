# romantic_story/workflow.py
from langgraph.graph import StateGraph, END

from romanticstory.nodes.character_node import character_node
from romanticstory.nodes.conditions import should_continue_writing
from romanticstory.nodes.plan_node import planner_node
from romanticstory.nodes.plot_node import plot_node
from romanticstory.nodes.write_node import writer_node
from romanticstory.states.romantic_story_state import MainState



def create_workflow():
    # 初始化图
    workflow = StateGraph(MainState)

    # 1. 添加节点
    workflow.add_node("planner", planner_node)
    workflow.add_node("character", character_node)
    workflow.add_node("plot", plot_node)
    workflow.add_node("writer", writer_node)

    # 2. 设置入口
    workflow.set_entry_point("planner")

    # 3. 添加边 (线性流程)
    workflow.add_edge("planner", "character")
    workflow.add_edge("character", "plot")

    # 4. 添加写作循环条件边
    # 从 plot 节点出来后，进入条件判断
    workflow.add_conditional_edges(
        source="plot",
        condition=should_continue_writing,
        mapping={
            "write": "writer",
            "end": END
        }
    )

    # 5. 写作节点完成后，再次回到条件判断
    workflow.add_conditional_edges(
        source="writer",
        condition=should_continue_writing,
        mapping={
            "write": "writer",
            "end": END
        }
    )

    # 编译图
    app = workflow.compile()
    return app
