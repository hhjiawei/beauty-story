"""
wechatessay.graphs.graph

LangGraph 图定义。

职责：
1. 定义 8 个节点（source/collect/analyse/plot/write/composition/legality/publish）
2. 定义节点间的路由逻辑
3. 实现人机协同的 interrupt 机制
4. 管理重试逻辑

路由逻辑：
- source_node -> collect_node（自动）
- collect_node -> human_review -> collect_node（retry）/ analyse_node（approve）
- analyse_node -> human_review -> analyse_node（retry）/ plot_node（approve）
- plot_node -> human_review -> plot_node（retry）/ write_node（approve）
- write_node -> human_review -> write_node（retry）/ composition_node（approve）
- composition_node -> human_review -> composition_node（retry）/ legality_node（approve）
- legality_node -> publish_node（自动通过）/ human_review（未通过）
- publish_node -> END
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from wechatessay.config import HITL_CONFIG
from wechatessay.nodes.analyse_node import analyse_node
from wechatessay.nodes.collect_node import collect_node
from wechatessay.nodes.composition_node import composition_node
from wechatessay.nodes.legality_node import legality_node
from wechatessay.nodes.plot_node import plot_node
from wechatessay.nodes.publish_node import publish_node
from wechatessay.nodes.source_node import source_node
from wechatessay.nodes.write_node import write_node
from wechatessay.states.vx_state import GraphState, HumanReviewRecord, ReviewDecision


# ═══════════════════════════════════════════════
# 人机协同路由函数
# ═══════════════════════════════════════════════

def human_review_router(state: GraphState) -> str:
    """
    人工审核路由。

    检查 pending_human_review，根据人工决策路由：
    - approve: 继续下一节点
    - revise/retry: 返回当前节点重新执行
    - reject: 返回上一节点
    """
    pending = state.get("pending_human_review")
    if not pending:
        return "approve"

    current_node = state.get("current_node", "")
    retry_counts = state.get("retry_counts", {})
    max_retry = HITL_CONFIG["max_retry"]

    # 获取人工评审记录
    reviews = state.get("human_reviews", [])
    last_review = reviews[-1] if reviews else None

    if not last_review:
        return "waiting"

    decision = last_review.decision
    node_name = last_review.node_name

    # 清理 pending
    state["pending_human_review"] = None

    if decision == ReviewDecision.APPROVE:
        print(f"[router] {node_name} 人工审核通过")
        return "approve"

    elif decision == ReviewDecision.RETRY or decision == ReviewDecision.REVISE:
        current_retries = retry_counts.get(node_name, 0)
        if current_retries >= max_retry:
            print(f"[router] {node_name} 已达到最大重试次数({max_retry})，强制通过")
            return "approve"

        retry_counts[node_name] = current_retries + 1
        state["retry_counts"] = retry_counts
        state["revision_notes"] = last_review.comment
        print(f"[router] {node_name} 需要修改/重试 (第{current_retries + 1}次)")
        return "retry"

    elif decision == ReviewDecision.REJECT:
        print(f"[router] {node_name} 被拒绝，返回上一节点")
        return "reject"

    return "waiting"


def route_after_human(state: GraphState, current_node: str) -> Command:
    """
    人工审核后的路由决策。

    返回 Command 对象以控制流程走向。
    """
    decision = human_review_router(state)

    if decision == "approve":
        # 根据当前节点确定下一节点
        node_flow = {
            "collect_node": "analyse_node",
            "analyse_node": "plot_node",
            "plot_node": "write_node",
            "write_node": "composition_node",
            "composition_node": "legality_node",
        }
        next_node = node_flow.get(current_node)
        if next_node:
            return Command(goto=next_node)
        return Command(goto=END)

    elif decision == "retry":
        # 返回当前节点重新执行
        return Command(goto=current_node)

    elif decision == "reject":
        # 返回上一节点
        node_reverse = {
            "collect_node": "source_node",
            "analyse_node": "collect_node",
            "plot_node": "analyse_node",
            "write_node": "plot_node",
            "composition_node": "write_node",
        }
        prev_node = node_reverse.get(current_node, "source_node")
        return Command(goto=prev_node)

    else:
        # waiting: 继续等待人工输入（保持当前状态）
        return Command(goto=current_node)


# ═══════════════════════════════════════════════
# 节点包装器（人机协同中断）
# ═══════════════════════════════════════════════

def source_node_wrapper(state: GraphState) -> GraphState:
    """source_node 包装器 — 无需人工审核。"""
    try:
        return source_node(state)
    except Exception as e:
        state["error_message"] = str(e)
        state["error_node"] = "source_node"
        state["node_status"]["source_node"] = "failed"
        return state


def collect_node_wrapper(state: GraphState) -> GraphState:
    """collect_node 包装器 — 需要人工审核。"""
    # 检查是否需要重试
    revision = state.get("revision_notes")
    if revision:
        # 在 agent 调用中注入修改意见
        # 这里通过 memory 或 prompt 注入
        state["revision_notes"] = None  # 消费掉

    try:
        state = collect_node(state)
    except Exception as e:
        state["error_message"] = str(e)
        state["error_node"] = "collect_node"
        state["node_status"]["collect_node"] = "failed"

    # 如果需要人工审核，触发 interrupt
    if state.get("pending_human_review"):
        return state  # 等待外部注入人工决策
    return state


def analyse_node_wrapper(state: GraphState) -> GraphState:
    """analyse_node 包装器 — 需要人工审核。"""
    revision = state.get("revision_notes")
    if revision:
        state["revision_notes"] = None

    try:
        state = analyse_node(state)
    except Exception as e:
        state["error_message"] = str(e)
        state["error_node"] = "analyse_node"
        state["node_status"]["analyse_node"] = "failed"

    if state.get("pending_human_review"):
        return state
    return state


def plot_node_wrapper(state: GraphState) -> GraphState:
    """plot_node 包装器 — 需要人工审核。"""
    revision = state.get("revision_notes")
    if revision:
        state["revision_notes"] = None

    try:
        state = plot_node(state)
    except Exception as e:
        state["error_message"] = str(e)
        state["error_node"] = "plot_node"
        state["node_status"]["plot_node"] = "failed"

    if state.get("pending_human_review"):
        return state
    return state


def write_node_wrapper(state: GraphState) -> GraphState:
    """write_node 包装器 — 需要人工审核。"""
    revision = state.get("revision_notes")
    if revision:
        state["revision_notes"] = None

    try:
        state = write_node(state)
    except Exception as e:
        state["error_message"] = str(e)
        state["error_node"] = "write_node"
        state["node_status"]["write_node"] = "failed"

    if state.get("pending_human_review"):
        return state
    return state


def composition_node_wrapper(state: GraphState) -> GraphState:
    """composition_node 包装器 — 需要人工审核。"""
    revision = state.get("revision_notes")
    if revision:
        state["revision_notes"] = None

    try:
        state = composition_node(state)
    except Exception as e:
        state["error_message"] = str(e)
        state["error_node"] = "composition_node"
        state["node_status"]["composition_node"] = "failed"

    if state.get("pending_human_review"):
        return state
    return state


def legality_node_wrapper(state: GraphState) -> GraphState:
    """legality_node 包装器 — 自动通过或人工审核。"""
    try:
        state = legality_node(state)
    except Exception as e:
        state["error_message"] = str(e)
        state["error_node"] = "legality_node"
        state["node_status"]["legality_node"] = "failed"

    if state.get("pending_human_review"):
        return state
    return state


def publish_node_wrapper(state: GraphState) -> GraphState:
    """publish_node 包装器 — 无需人工审核。"""
    try:
        return publish_node(state)
    except Exception as e:
        state["error_message"] = str(e)
        state["error_node"] = "publish_node"
        state["node_status"]["publish_node"] = "failed"
        return state


# ═══════════════════════════════════════════════
# 条件路由函数
# ═══════════════════════════════════════════════

def route_after_source(state: GraphState) -> str:
    """source_node 后的路由。"""
    if state.get("error_message"):
        return END
    return "collect_node"


def route_after_collect(state: GraphState) -> str:
    """collect_node 后的路由。"""
    if state.get("error_message"):
        return END
    status = state.get("node_status", {}).get("collect_node", "")
    if status == "waiting_human":
        return "human_review"
    return "analyse_node"


def route_after_analyse(state: GraphState) -> str:
    """analyse_node 后的路由。"""
    if state.get("error_message"):
        return END
    status = state.get("node_status", {}).get("analyse_node", "")
    if status == "waiting_human":
        return "human_review"
    return "plot_node"


def route_after_plot(state: GraphState) -> str:
    """plot_node 后的路由。"""
    if state.get("error_message"):
        return END
    status = state.get("node_status", {}).get("plot_node", "")
    if status == "waiting_human":
        return "human_review"
    return "write_node"


def route_after_write(state: GraphState) -> str:
    """write_node 后的路由。"""
    if state.get("error_message"):
        return END
    status = state.get("node_status", {}).get("write_node", "")
    if status == "waiting_human":
        return "human_review"
    return "composition_node"


def route_after_composition(state: GraphState) -> str:
    """composition_node 后的路由。"""
    if state.get("error_message"):
        return END
    status = state.get("node_status", {}).get("composition_node", "")
    if status == "waiting_human":
        return "human_review"
    return "legality_node"


def route_after_legality(state: GraphState) -> str:
    """legality_node 后的路由。"""
    if state.get("error_message"):
        return END
    status = state.get("node_status", {}).get("legality_node", "")
    if status == "waiting_human":
        return "human_review"
    return "publish_node"


def human_review_node(state: GraphState) -> GraphState:
    """
    人工审核节点。

    此节点使用 LangGraph 的 interrupt 机制暂停图执行，
    等待外部输入人工评审决策。

    外部需要：
    1. 读取 state["pending_human_review"] 获取待审核内容
    2. 将人工决策写入 state["human_reviews"]
    3. 调用 graph.invoke 继续执行
    """
    pending = state.get("pending_human_review")
    if not pending:
        return state

    # 使用 interrupt 暂停执行
    decision = interrupt({
        "type": "human_review",
        "node": pending.get("node"),
        "content": pending.get("content"),
        "instruction": pending.get("instruction"),
    })

    # 处理外部传入的决策
    if decision:
        review = HumanReviewRecord(
            node_name=pending.get("node", "unknown"),
            decision=decision.get("decision", "retry"),
            comment=decision.get("comment", ""),
            reviewed_at=datetime.now().isoformat(),
            retry_count=state.get("retry_counts", {}).get(pending.get("node"), 0),
        )

        reviews = state.get("human_reviews", [])
        reviews.append(review)
        state["human_reviews"] = reviews

        # 清理 pending
        state["pending_human_review"] = None

        # 根据决策更新节点状态
        node_name = pending.get("node")
        if review.decision == ReviewDecision.APPROVE:
            state["node_status"][node_name] = "approved"
        elif review.decision in (ReviewDecision.RETRY, ReviewDecision.REVISE):
            state["node_status"][node_name] = "retrying"
            state["revision_notes"] = review.comment
        elif review.decision == ReviewDecision.REJECT:
            state["node_status"][node_name] = "rejected"

    return state


def route_after_human_review(state: GraphState) -> str:
    """人工审核后的路由决策。"""
    reviews = state.get("human_reviews", [])
    if not reviews:
        return END

    last_review = reviews[-1]
    node_name = last_review.node_name

    # 获取当前节点流程映射
    node_flow = {
        "collect_node": "analyse_node",
        "analyse_node": "plot_node",
        "plot_node": "write_node",
        "write_node": "composition_node",
        "composition_node": "legality_node",
    }
    node_reverse = {
        "collect_node": "source_node",
        "analyse_node": "collect_node",
        "plot_node": "analyse_node",
        "write_node": "plot_node",
        "composition_node": "write_node",
        "legality_node": "composition_node",
    }

    if last_review.decision == ReviewDecision.APPROVE:
        next_node = node_flow.get(node_name)
        if next_node:
            # 将对应节点状态更新为 ready 以继续流程
            return next_node
        return "publish_node"

    elif last_review.decision in (ReviewDecision.RETRY, ReviewDecision.REVISE):
        return node_name  # 返回当前节点重新执行

    elif last_review.decision == ReviewDecision.REJECT:
        return node_reverse.get(node_name, "source_node")

    return END


# ═══════════════════════════════════════════════
# 构建图
# ═══════════════════════════════════════════════

def build_graph() -> StateGraph:
    """
    构建完整的 LangGraph 工作流。

    返回编译后的 StateGraph 实例。
    """
    workflow = StateGraph(GraphState)

    # ── 添加节点 ──
    workflow.add_node("source_node", source_node_wrapper)
    workflow.add_node("collect_node", collect_node_wrapper)
    workflow.add_node("analyse_node", analyse_node_wrapper)
    workflow.add_node("plot_node", plot_node_wrapper)
    workflow.add_node("write_node", write_node_wrapper)
    workflow.add_node("composition_node", composition_node_wrapper)
    workflow.add_node("legality_node", legality_node_wrapper)
    workflow.add_node("publish_node", publish_node_wrapper)
    workflow.add_node("human_review", human_review_node)

    # ── 定义入口 ──
    workflow.set_entry_point("source_node")

    # ── 定义边 ──
    # source -> collect
    workflow.add_conditional_edges(
        "source_node",
        route_after_source,
        {"collect_node": "collect_node", END: END},
    )

    # collect -> human_review / analyse
    workflow.add_conditional_edges(
        "collect_node",
        route_after_collect,
        {"human_review": "human_review", "analyse_node": "analyse_node", END: END},
    )

    # analyse -> human_review / plot
    workflow.add_conditional_edges(
        "analyse_node",
        route_after_analyse,
        {"human_review": "human_review", "plot_node": "plot_node", END: END},
    )

    # plot -> human_review / write
    workflow.add_conditional_edges(
        "plot_node",
        route_after_plot,
        {"human_review": "human_review", "write_node": "write_node", END: END},
    )

    # write -> human_review / composition
    workflow.add_conditional_edges(
        "write_node",
        route_after_write,
        {"human_review": "human_review", "composition_node": "composition_node", END: END},
    )

    # composition -> human_review / legality
    workflow.add_conditional_edges(
        "composition_node",
        route_after_composition,
        {"human_review": "human_review", "legality_node": "legality_node", END: END},
    )

    # legality -> human_review / publish
    workflow.add_conditional_edges(
        "legality_node",
        route_after_legality,
        {"human_review": "human_review", "publish_node": "publish_node", END: END},
    )

    # publish -> END
    workflow.add_edge("publish_node", END)

    # human_review -> 路由回各节点
    workflow.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "source_node": "source_node",
            "collect_node": "collect_node",
            "analyse_node": "analyse_node",
            "plot_node": "plot_node",
            "write_node": "write_node",
            "composition_node": "composition_node",
            "legality_node": "legality_node",
            "publish_node": "publish_node",
            END: END,
        },
    )

    return workflow.compile()


def build_graph_no_hitl() -> StateGraph:
    """
    构建无人工干预的 LangGraph 工作流（用于自动化测试）。

    所有人工审核节点自动通过。
    """
    workflow = StateGraph(GraphState)

    # 包装器：自动通过人工审核
    def auto_approve(state: GraphState) -> GraphState:
        pending = state.get("pending_human_review")
        if pending:
            review = HumanReviewRecord(
                node_name=pending.get("node", "unknown"),
                decision=ReviewDecision.APPROVE,
                comment="auto approve",
                reviewed_at=datetime.now().isoformat(),
            )
            reviews = state.get("human_reviews", [])
            reviews.append(review)
            state["human_reviews"] = reviews
            state["pending_human_review"] = None
            state["node_status"][pending.get("node", "")] = "approved"
        return state

    workflow.add_node("source_node", source_node_wrapper)
    workflow.add_node("collect_node", collect_node_wrapper)
    workflow.add_node("analyse_node", analyse_node_wrapper)
    workflow.add_node("plot_node", plot_node_wrapper)
    workflow.add_node("write_node", write_node_wrapper)
    workflow.add_node("composition_node", composition_node_wrapper)
    workflow.add_node("legality_node", legality_node_wrapper)
    workflow.add_node("publish_node", publish_node_wrapper)
    workflow.add_node("auto_approve", auto_approve)

    workflow.set_entry_point("source_node")

    workflow.add_edge("source_node", "collect_node")
    workflow.add_edge("collect_node", "auto_approve")
    workflow.add_edge("auto_approve", "analyse_node")
    workflow.add_edge("analyse_node", "auto_approve")
    workflow.add_edge("auto_approve", "plot_node")
    workflow.add_edge("plot_node", "auto_approve")
    workflow.add_edge("auto_approve", "write_node")
    workflow.add_edge("write_node", "auto_approve")
    workflow.add_edge("auto_approve", "composition_node")
    workflow.add_edge("composition_node", "auto_approve")
    workflow.add_edge("auto_approve", "legality_node")
    workflow.add_edge("legality_node", "publish_node")
    workflow.add_edge("publish_node", END)

    return workflow.compile()
