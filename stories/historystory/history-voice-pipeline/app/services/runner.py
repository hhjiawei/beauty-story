"""流水线运行调度：后台线程驱动 LangGraph，interrupt ↔ resume 的闭环。

- 图全局单例 + SqliteSaver checkpoint：服务重启、浏览器关闭不丢进度
- 每次 invoke 结束后把 Run 状态落库（前端轮询/SSE 的依据）
"""
from __future__ import annotations

import sqlite3
import threading

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from .. import config
from ..db import session
from ..graph.pipeline import build_graph
from ..models import Project, Run

_graph = None
_graph_lock = threading.Lock()
_run_threads: dict[str, threading.Thread] = {}


def get_graph():
    global _graph
    with _graph_lock:
        if _graph is None:
            config.ensure_dirs()
            conn = sqlite3.connect(str(config.CHECKPOINT_DB_PATH), check_same_thread=False)
            _graph = build_graph(checkpointer=SqliteSaver(conn))
        return _graph


def reset_graph(checkpoint_db=None):
    """测试用：重建图（指向临时 checkpoint 库）。"""
    global _graph
    with _graph_lock:
        if checkpoint_db is not None:
            config.CHECKPOINT_DB_PATH = checkpoint_db
        _graph = None
    return get_graph()


def _cfg(run: Run) -> dict:
    return {"configurable": {"thread_id": run.thread_id}}


def _update_run(run_id: str, **fields):
    with session() as s:
        r = s.get(Run, run_id)
        if r:
            for k, v in fields.items():
                setattr(r, k, v)
            s.commit()


def _drive(run_id: str, payload):
    """在线程里跑图直到 interrupt 或结束，然后落库状态。"""
    graph = get_graph()
    with session() as s:
        run = s.get(Run, run_id)
        cfg = _cfg(run)
    try:
        result = graph.invoke(payload, cfg)
        state = graph.get_state(cfg)
        if "__interrupt__" in result and result["__interrupt__"]:
            gate_info = result["__interrupt__"][0].value
            _update_run(run_id, status="waiting_review",
                        current_node=gate_info.get("gate", str(state.next)))
        elif not state.next:
            _update_run(run_id, status="done", current_node="finalize_episode_archive")
        else:
            _update_run(run_id, status="running", current_node=str(state.next))
    except Exception as e:  # noqa: BLE001
        _update_run(run_id, status="error", error=str(e)[:800])


def start_run(run_id: str) -> None:
    """从 N0 任务信息启动流水线（N1 开跑）。"""
    with session() as s:
        run = s.get(Run, run_id)
        proj = s.get(Project, run.project_id)
        proj.status = "running"
        s.commit()
        initial = {
            "project_id": proj.id, "run_id": run.id,
            "source_type": proj.source_type, "source_text": proj.source_text,
            "target_minutes": proj.target_minutes, "episode_no": proj.episode_no,
            "prev_episode_bridge": proj.prev_episode_bridge,
            "rework_count": {}, "rework_feedback": {}, "memories_loaded": [],
        }
    _update_run(run_id, status="running")
    t = threading.Thread(target=_drive, args=(run_id, initial), daemon=True)
    _run_threads[run_id] = t
    t.start()


def resume_run(run_id: str, decision: dict) -> None:
    """人工闸门裁决后继续（放行/编辑放行/打回/定点重生）。"""
    _update_run(run_id, status="running")
    t = threading.Thread(target=_drive, args=(run_id, Command(resume=decision)), daemon=True)
    _run_threads[run_id] = t
    t.start()


def wait(run_id: str, timeout: float | None = None):
    """测试用：等当前驱动线程结束。"""
    t = _run_threads.get(run_id)
    if t:
        t.join(timeout)
