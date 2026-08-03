"""运行状态、SSE、闸门裁决端点。"""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import select

from ..db import session
from ..graph.pipeline import PIPELINE_SEQUENCE
from ..models import Artifact, NodeRun, Review, Run
from ..services import artifacts as art_svc
from ..services import runner

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _snapshot(run_id: str) -> dict:
    with session() as s:
        run = s.get(Run, run_id)
        if not run:
            raise HTTPException(404, "运行不存在")
        reviews = s.exec(select(Review).where(Review.run_id == run_id)).all()
    approved_nodes = {r.node_id for r in reviews if r.action == "approve"}
    current = run.current_node
    seq = []
    seen_current = False
    for nid, label in PIPELINE_SEQUENCE:
        if nid in approved_nodes or nid == "finalize_episode_archive" and run.status == "done":
            st = "done"
        elif nid == current and run.status == "waiting_review":
            st = "waiting"; seen_current = True
        elif nid == current and run.status in ("running",):
            st = "running"; seen_current = True
        elif not seen_current and run.status == "running" and nid == current:
            st = "running"; seen_current = True
        else:
            st = "pending"
        seq.append({"node": nid, "label": label, "status": st})
    # 已过当前节点但未显式 approve 的产出节点标 done
    if seen_current:
        for item in seq:
            if item["status"] == "pending" and                PIPELINE_SEQUENCE.index((item["node"], item["label"])) <                [n for n, _ in PIPELINE_SEQUENCE].index(current):
                item["status"] = "done"
    pending = None
    if run.status == "waiting_review":
        try:
            graph = runner.get_graph()
            state = graph.get_state({"configurable": {"thread_id": run.thread_id}})
            for task in state.tasks:
                if getattr(task, "interrupts", None):
                    pending = task.interrupts[0].value
                    break
        except Exception:  # noqa: BLE001
            pending = None
    return {"run_id": run.id, "status": run.status, "error": run.error,
            "current_node": current, "sequence": seq, "pending_gate": pending}


@router.get("/{run_id}")
def run_status(run_id: str):
    return _snapshot(run_id)


@router.get("/{run_id}/events")
def run_events(run_id: str):
    """SSE：状态变化即推送（1s 心跳轮询 DB）。"""
    def stream():
        last = ""
        while True:
            try:
                snap = json.dumps(_snapshot(run_id), ensure_ascii=False)
            except HTTPException:
                yield "event: error\ndata: {}\n\n"
                return
            if snap != last:
                yield f"data: {snap}\n\n"
                last = snap
            data = json.loads(snap)
            if data["status"] in ("done", "error", "archived"):
                yield "event: end\ndata: {}\n\n"
                return
            time.sleep(1)
    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/{run_id}/nodes/{node_id}/artifact")
def node_artifact(run_id: str, node_id: str, kind: str):
    a = art_svc.latest_artifact(run_id, node_id, kind)
    if not a:
        raise HTTPException(404, "产物不存在")
    return {"artifact_id": a.id, "version": a.version, "origin": a.origin,
            "content": art_svc.load_artifact_content(a)}


@router.get("/{run_id}/nodes/{node_id}/versions")
def node_versions(run_id: str, node_id: str):
    with session() as s:
        rows = s.exec(select(Artifact).where(
            Artifact.run_id == run_id, Artifact.node_id == node_id
        ).order_by(Artifact.created_at.desc())).all()
        return [{"artifact_id": r.id, "kind": r.kind, "version": r.version,
                 "origin": r.origin, "created_at": r.created_at.isoformat()} for r in rows]


class Decision(BaseModel):
    action: str                              # approve | reject | regen_units
    edited_content: object | None = None     # 编辑后放行
    feedback: str | None = None              # 打回意见
    unit_ids: list[str] | None = None        # 勾选重生单元


@router.post("/{run_id}/approve")
def approve(run_id: str, d: Decision):
    runner.resume_run(run_id, {"action": "approve", "edited_content": d.edited_content,
                               "artifact_version": None})
    return {"ok": True}


@router.post("/{run_id}/reject")
def reject(run_id: str, d: Decision):
    if not d.feedback:
        raise HTTPException(400, "打回必须填写意见（feedback）")
    runner.resume_run(run_id, {"action": "reject", "feedback": d.feedback})
    return {"ok": True}


@router.post("/{run_id}/nodes/n7/regenerate")
def regen_units(run_id: str, d: Decision):
    if not d.unit_ids:
        raise HTTPException(400, "须指定重生单元 unit_ids")
    runner.resume_run(run_id, {"action": "regen_units", "unit_ids": d.unit_ids})
    return {"ok": True}


@router.post("/{run_id}/retry")
def retry(run_id: str):
    """出错后原地重试失败节点（invoke(None) 从 checkpoint 续跑，不从头再来）。"""
    try:
        runner.retry_run(run_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.get("/{run_id}/node-runs")
def node_runs(run_id: str):
    """节点运行记录（查看用）：每次节点执行的状态/耗时/错误。"""
    with session() as s:
        rows = s.exec(select(NodeRun).where(NodeRun.run_id == run_id)
                      .order_by(NodeRun.started_at)).all()
        return [{
            "node_id": r.node_id, "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "duration_s": round((r.finished_at - r.started_at).total_seconds(), 1)
                          if r.finished_at and r.started_at else None,
            "error": r.error,
        } for r in rows]
