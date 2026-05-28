"""
wechatessay.graphs.graph

LangGraph 图定义（含多模型评审择优）。

职责：
1. 定义 9 个节点（source/collect/analyse/plot/write/review/composition/legality/publish）
2. 定义节点间的路由逻辑（全自动推进）
3. write → review：review 内完成多模型评审+择优+替换文章
4. 异常时流程终止

节点流向：
    source_node → collect_node → analyse_node → plot_node
        → write_node → review_node（多模型评审择优，替换文章）
        → composition_node → legality_node → publish_node → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from wechatessay.nodes.analyse_node import analyse_node
from wechatessay.nodes.collect_node import collect_node
from wechatessay.nodes.composition_node import composition_node
from wechatessay.nodes.legality_node import legality_node
from wechatessay.nodes.plot_node import plot_node
from wechatessay.nodes.publish_node import publish_node
from wechatessay.nodes.review_node import review_node
from wechatessay.nodes.source_node import source_node
from wechatessay.nodes.write_node import write_node
from wechatessay.states.vx_state import GraphState


# ═══════════════════════════════════════════════
# 节点包装器（统一异常处理）
# ═══════════════════════════════════════════════

def _wrap_node(node_func, node_name: str):
    """通用节点包装器：异常捕获 + 状态标记。"""
    def wrapper(state: GraphState) -> GraphState:
        revision = state.get("revision_notes")
        if revision:
            state["revision_notes"] = None

        try:
            result = node_func(state)
            if isinstance(result, dict):
                state.update(result)
            return state
        except Exception as e:
            state["error_message"] = str(e)
            state["error_node"] = node_name
            state["node_status"][node_name] = "failed"
            return state
    return wrapper


source_node_wrapper = _wrap_node(source_node, "source_node")
collect_node_wrapper = _wrap_node(collect_node, "collect_node")
analyse_node_wrapper = _wrap_node(analyse_node, "analyse_node")
plot_node_wrapper = _wrap_node(plot_node, "plot_node")
write_node_wrapper = _wrap_node(write_node, "write_node")
review_node_wrapper = _wrap_node(review_node, "review_node")
composition_node_wrapper = _wrap_node(composition_node, "composition_node")
legality_node_wrapper = _wrap_node(legality_node, "legality_node")
publish_node_wrapper = _wrap_node(publish_node, "publish_node")


# ═══════════════════════════════════════════════
# 条件路由函数
# ═══════════════════════════════════════════════

def _check_error(state: GraphState) -> bool:
    """检查是否有错误。"""
    return bool(state.get("error_message"))


def route_after_source(state: GraphState) -> str:
    """source_node → collect_node / END"""
    if _check_error(state):
        return END
    return "collect_node"


def route_after_collect(state: GraphState) -> str:
    """collect_node → analyse_node / END"""
    if _check_error(state):
        return END
    return "analyse_node"


def route_after_analyse(state: GraphState) -> str:
    """analyse_node → plot_node / END"""
    if _check_error(state):
        return END
    return "plot_node"


def route_after_plot(state: GraphState) -> str:
    """plot_node → write_node / END"""
    if _check_error(state):
        return END
    return "write_node"


def route_after_write(state: GraphState) -> str:
    """write_node → review_node / END"""
    if _check_error(state):
        return END
    return "review_node"


def route_after_review(state: GraphState) -> str:
    """
    review_node 路由 — 评审择优后直接排版。

    review_node 内部已完成：多模型评审 → 择优 → 替换 article_output。
    因此 review 后直接进 composition，不再需要回到 write_node。

    - 正常 → composition_node
    - 出错 → END
    """
    if _check_error(state):
        return END
    return "composition_node"


def route_after_composition(state: GraphState) -> str:
    """composition_node → legality_node / END"""
    if _check_error(state):
        return END
    return "legality_node"


def route_after_legality(state: GraphState) -> str:
    """legality_node → publish_node / END"""
    if _check_error(state):
        return END
    return "publish_node"


# ═══════════════════════════════════════════════
# 构建图
# ═══════════════════════════════════════════════

def build_graph() -> StateGraph:
    """
    构建全自动 LangGraph 工作流（含多模型自动评审）。

    所有节点自动推进，无需人工审阅。
    write → review 循环实现根据评审意见自动修改。
    """
    workflow = StateGraph(GraphState)

    # ── 添加节点 ──
    workflow.add_node("source_node", source_node_wrapper)
    workflow.add_node("collect_node", collect_node_wrapper)
    workflow.add_node("analyse_node", analyse_node_wrapper)
    workflow.add_node("plot_node", plot_node_wrapper)
    workflow.add_node("write_node", write_node_wrapper)
    workflow.add_node("review_node", review_node_wrapper)
    workflow.add_node("composition_node", composition_node_wrapper)
    workflow.add_node("legality_node", legality_node_wrapper)
    workflow.add_node("publish_node", publish_node_wrapper)

    # ── 定义入口 ──
    workflow.set_entry_point("source_node")

    # ── 定义条件边 ──
    # source → collect
    workflow.add_conditional_edges(
        "source_node",
        route_after_source,
        {"collect_node": "collect_node", END: END},
    )

    # collect → analyse
    workflow.add_conditional_edges(
        "collect_node",
        route_after_collect,
        {"analyse_node": "analyse_node", END: END},
    )

    # analyse → plot
    workflow.add_conditional_edges(
        "analyse_node",
        route_after_analyse,
        {"plot_node": "plot_node", END: END},
    )

    # plot → write
    workflow.add_conditional_edges(
        "plot_node",
        route_after_plot,
        {"write_node": "write_node", END: END},
    )

    # write → review
    workflow.add_conditional_edges(
        "write_node",
        route_after_write,
        {"review_node": "review_node", END: END},
    )

    # review → composition（review 内部已完成择优替换）
    workflow.add_conditional_edges(
        "review_node",
        route_after_review,
        {
            "composition_node": "composition_node",
            END: END,
        },
    )

    # composition → legality
    workflow.add_conditional_edges(
        "composition_node",
        route_after_composition,
        {"legality_node": "legality_node", END: END},
    )

    # legality → publish
    workflow.add_conditional_edges(
        "legality_node",
        route_after_legality,
        {"publish_node": "publish_node", END: END},
    )

    # publish → END
    workflow.add_edge("publish_node", END)

    return workflow.compile()