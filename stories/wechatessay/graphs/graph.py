"""
微信公众号文章创作工作流 - LangGraph 图定义（v2 架构）

核心改进：
1. CompositeBackend 初始化并注入每个节点
2. Memory 机制集成（Context + RAG + Summarization）
3. Skill 自动加载
4. 聊天记录通过 CompositeBackend 持久化到 records
5. 节点通过 kwargs 接收 backend/store/thread_id

工作流：
source → total_analysis → collect → analyse → plot → write → composition → legality → publish
"""

import json
from typing import Dict, Any, Literal
from pathlib import Path

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from wechatessay.states.vx_state import GraphState
from wechatessay.config import (
    HUMAN_IN_THE_LOOP,
    MAX_REVISION_ROUNDS,
    MEMORY_DIR,
    WORKSPACE_DIR,
    SKILLS_DIR,
    AUTO_LOAD_SKILLS,
    BACKEND_ROOT,
    BACKEND_VIRTUAL_MODE,
)

# ── 节点 ──
from wechatessay.nodes.source_node import source_node, total_analysis_node
from wechatessay.nodes.collect_node import collect_node
from wechatessay.nodes.analyse_node import analyse_node
from wechatessay.nodes.plot_node import plot_node
from wechatessay.nodes.write_node import write_node
from wechatessay.nodes.composition_node import composition_node
from wechatessay.nodes.legality_node import legality_node
from wechatessay.nodes.publish_node import publish_node

# ── Agent 基础设施 ──
from wechatessay.agents.agent_factory import load_skills
from wechatessay.agents.memory_manager import get_memory_manager
from wechatessay.agents.chat_history_store import get_chat_history_store


# ═══════════════════════════════════════════════════════════
# 1. CompositeBackend 初始化
# ═══════════════════════════════════════════════════════════

def init_deepagents_backend():
    """
    初始化 DeepAgents CompositeBackend

    返回 (composite_backend, store) 元组
    """
    from dotenv import find_dotenv

    root = Path(find_dotenv()).parent if find_dotenv() else Path(__file__).parent.parent

    _MEMORY_DIR = (root / "backends" / "memories").as_posix()
    _SKILLS_DIR = (root / "backends" / "skills").as_posix()
    _WORKSPACE_DIR = (root / "backends" / "workspaces").as_posix()

    try:
        from deepagents.backends import CompositeBackend, FilesystemBackend

        composite_backend = CompositeBackend(
            default=FilesystemBackend(root_dir=root, virtual_mode=True),
            routes={
                "/memories/": FilesystemBackend(root_dir=_MEMORY_DIR, virtual_mode=True),
                "/skills/": FilesystemBackend(root_dir=_SKILLS_DIR, virtual_mode=True),
                "/workplaces/": FilesystemBackend(root_dir=_WORKSPACE_DIR, virtual_mode=True)
            },
        )

        store = InMemoryStore()
        print("✅ CompositeBackend 初始化成功")
        return composite_backend, store

    except ImportError as e:
        print(f"⚠️ DeepAgents 导入失败: {e}，使用本地 fallback")
        return None, InMemoryStore()


# ═══════════════════════════════════════════════════════════
# 2. 节点包装器（注入 backend/store/thread_id）
# ═══════════════════════════════════════════════════════════

class NodeWrapper:
    """
    节点包装器

    将 backend、store、thread_id 通过 kwargs 注入到每个节点函数中。
    同时记录节点生命周期事件到 ChatHistoryStore。
    """

    def __init__(self, node_func, backend, store, thread_id: str):
        self.node_func = node_func
        self.backend = backend
        self.store = store
        self.thread_id = thread_id

    def __call__(self, state: GraphState) -> Dict[str, Any]:
        node_name = self.node_func.__name__

        # 记录节点开始
        try:
            chat_store = get_chat_history_store(self.backend, self.thread_id)
            chat_store.record_node_event(node_name, "start", {"state_keys": list(state.keys())})
        except Exception:
            pass

        # 注入依赖并执行节点
        result = self.node_func(
            state,
            backend=self.backend,
            store=self.store,
            thread_id=self.thread_id,
        )

        # 记录节点结束
        try:
            chat_store = get_chat_history_store(self.backend, self.thread_id)
            chat_store.record_node_event(node_name, "end", {"result_keys": list(result.keys()) if result else []})
        except Exception:
            pass

        return result


# ═══════════════════════════════════════════════════════════
# 3. 路由函数
# ═══════════════════════════════════════════════════════════

def route_after_human_feedback(state: GraphState) -> str:
    """
    根据人工反馈决定下一步走向
    """
    awaiting_human = state.get("awaiting_human", False)
    human_feedback = state.get("human_feedback")
    should_continue = state.get("should_continue", True)

    if not should_continue:
        return "end"

    if not awaiting_human:
        return "continue"

    if human_feedback:
        fb = human_feedback.lower().strip()
        if fb in ["ok", "满意", "continue", "y", "yes", "通过"]:
            return "continue"
        if fb in ["stop", "终止", "结束", "exit", "quit", "n", "no"]:
            return "end"
        return "revise"

    return "wait"


def route_from_source(state: GraphState) -> str:
    if state.get("error_message"):
        return "end"
    return "total_analysis"


def route_from_total_analysis(state: GraphState) -> str:
    if state.get("error_message"):
        return "end"
    return "collect"


def route_from_collect(state: GraphState) -> str:
    r = route_after_human_feedback(state)
    return {"end": "end", "revise": "collect", "wait": "wait", "continue": "analyse"}.get(r, "wait")


def route_from_analyse(state: GraphState) -> str:
    r = route_after_human_feedback(state)
    return {"end": "end", "revise": "analyse", "wait": "wait", "continue": "plot"}.get(r, "wait")


def route_from_plot(state: GraphState) -> str:
    r = route_after_human_feedback(state)
    return {"end": "end", "revise": "plot", "wait": "wait", "continue": "write"}.get(r, "wait")


def route_from_write(state: GraphState) -> str:
    r = route_after_human_feedback(state)
    return {"end": "end", "revise": "write", "wait": "wait", "continue": "composition"}.get(r, "wait")


def route_from_composition(state: GraphState) -> str:
    r = route_after_human_feedback(state)
    return {"end": "end", "revise": "composition", "wait": "wait", "continue": "legality"}.get(r, "wait")


def route_from_legality(state: GraphState) -> str:
    if state.get("error_message"):
        return "end"
    return "publish"


# ═══════════════════════════════════════════════════════════
# 4. 记忆加载/保存节点
# ═══════════════════════════════════════════════════════════

def make_load_memories_node(backend, store, thread_id: str):
    """创建加载记忆节点"""
    def load_memories(state: GraphState) -> Dict[str, Any]:
        memory = get_memory_manager(backend=backend, store=store, thread_id=thread_id)

        # 从 context 加载用户记忆
        user_memories = memory.context.get_context("user_memories", default=[])

        # 从 RAG 加载历史文档
        docs = memory.rag.get_all_documents()

        print(f"📚 记忆加载: {len(user_memories)} 条用户记忆, {len(docs)} 条历史文档")

        return {
            "user_memories": user_memories,
            "current_node": "load_memories"
        }

    return load_memories


def make_save_memory_node(backend, store, thread_id: str):
    """创建保存记忆节点"""
    def save_memory(state: GraphState) -> Dict[str, Any]:
        human_feedback = state.get("human_feedback")
        current_node = state.get("current_node", "")

        if not human_feedback or human_feedback.lower() in ["ok", "满意", "continue", "y", "yes"]:
            return {}

        memory = get_memory_manager(backend=backend, store=store, thread_id=thread_id)

        # 记录到 RAG
        memory.record_human_feedback(current_node, human_feedback)

        # 记录到 context
        existing = memory.context.get_context("user_memories", default=[])
        if human_feedback not in existing:
            existing.append(human_feedback)
            memory.context.set_context("user_memories", existing)

        print(f"🧠 已保存记忆: {human_feedback[:80]}...")
        return {}

    return save_memory


# ═══════════════════════════════════════════════════════════
# 5. 构建图
# ═══════════════════════════════════════════════════════════

def build_workflow(backend=None, store=None, thread_id: str = "default") -> StateGraph:
    """构建工作流图"""
    print("🏗️ 构建工作流图...")

    workflow = StateGraph(GraphState)

    # 加载 skills
    if AUTO_LOAD_SKILLS:
        try:
            load_skills(SKILLS_DIR)
        except Exception as e:
            print(f"  ⚠️ Skill 加载失败: {e}")

    # 包装节点
    nodes = {
        "load_memories": make_load_memories_node(backend, store, thread_id),
        "source_node": NodeWrapper(source_node, backend, store, thread_id),
        "total_analysis_node": NodeWrapper(total_analysis_node, backend, store, thread_id),
        "collect_node": NodeWrapper(collect_node, backend, store, thread_id),
        "analyse_node": NodeWrapper(analyse_node, backend, store, thread_id),
        "plot_node": NodeWrapper(plot_node, backend, store, thread_id),
        "write_node": NodeWrapper(write_node, backend, store, thread_id),
        "composition_node": NodeWrapper(composition_node, backend, store, thread_id),
        "legality_node": NodeWrapper(legality_node, backend, store, thread_id),
        "publish_node": NodeWrapper(publish_node, backend, store, thread_id),
        "save_memory": make_save_memory_node(backend, store, thread_id),
    }

    for name, node in nodes.items():
        workflow.add_node(name, node)

    # ── 边 ──
    workflow.add_edge(START, "load_memories")
    workflow.add_edge("load_memories", "source_node")

    workflow.add_conditional_edges(
        "source_node", route_from_source,
        {"total_analysis": "total_analysis_node", "end": END}
    )

    workflow.add_conditional_edges(
        "total_analysis_node", route_from_total_analysis,
        {"collect": "collect_node", "end": END}
    )

    workflow.add_conditional_edges(
        "collect_node", route_from_collect,
        {"collect": "collect_node", "analyse": "analyse_node", "wait": END, "end": END}
    )

    workflow.add_conditional_edges(
        "analyse_node", route_from_analyse,
        {"analyse": "analyse_node", "plot": "plot_node", "wait": END, "end": END}
    )

    workflow.add_conditional_edges(
        "plot_node", route_from_plot,
        {"plot": "plot_node", "write": "write_node", "wait": END, "end": END}
    )

    workflow.add_conditional_edges(
        "write_node", route_from_write,
        {"write": "write_node", "composition": "composition_node", "wait": END, "end": END}
    )

    workflow.add_conditional_edges(
        "composition_node", route_from_composition,
        {"composition": "composition_node", "legality": "legality_node", "wait": END, "end": END}
    )

    workflow.add_conditional_edges(
        "legality_node", route_from_legality,
        {"publish": "publish_node", "end": END}
    )

    workflow.add_edge("publish_node", END)

    print("✅ 工作流图构建完成")
    return workflow


def create_graph(checkpointer=None, store=None, backend=None, thread_id: str = "default"):
    """
    创建编译后的图实例

    Args:
        checkpointer: 检查点保存器
        store: Store 实例
        backend: CompositeBackend 实例
        thread_id: 线程 ID

    Returns:
        编译后的图
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    if store is None:
        store = InMemoryStore()

    workflow = build_workflow(backend=backend, store=store, thread_id=thread_id)

    graph = workflow.compile(
        checkpointer=checkpointer,
        store=store,
    )

    print("✅ 图编译完成")
    return graph


# ═══════════════════════════════════════════════════════════
# 6. 可视化
# ═══════════════════════════════════════════════════════════

def visualize_graph(graph, output_path: str = "workflow_graph"):
    """可视化工作流图"""
    try:
        mermaid_code = graph.get_graph().draw_mermaid()

        mermaid_file = Path(output_path).with_suffix(".mmd")
        with open(mermaid_file, "w", encoding="utf-8") as f:
            f.write(mermaid_code)

        print(f"📊 Mermaid 图已保存: {mermaid_file}")
        print("💡 可在 https://mermaid.live/ 预览")

    except Exception as e:
        print(f"⚠️ 可视化失败: {e}")
