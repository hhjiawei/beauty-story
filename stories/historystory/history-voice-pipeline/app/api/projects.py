"""项目与运行端点。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from ..db import session
from ..models import Project, Run
from ..services import runner

router = APIRouter(prefix="/api", tags=["projects"])


class ProjectIn(BaseModel):
    title: str
    source_type: str                    # dynasty | person | event
    source_text: str
    target_minutes: int = 10
    episode_no: int = 1
    prev_episode_bridge: str | None = None


@router.post("/projects")
def create_project(p: ProjectIn):
    if p.source_type not in ("dynasty", "person", "event"):
        raise HTTPException(400, "source_type 须为 dynasty/person/event")
    if p.episode_no > 1 and not p.prev_episode_bridge:
        raise HTTPException(400, "第2集起必填上集衔接段（prev_episode_bridge）")
    proj = Project(id=uuid.uuid4().hex[:12], **p.model_dump())
    with session() as s:
        s.add(proj); s.commit(); s.refresh(proj)
        return {"id": proj.id, "title": proj.title}


@router.get("/projects")
def list_projects():
    with session() as s:
        projs = s.exec(select(Project).order_by(Project.created_at.desc())).all()
        runs = s.exec(select(Run)).all()
        cur = {r.project_id: r for r in runs}
        return [{
            "id": p.id, "title": p.title, "source_type": p.source_type,
            "episode_no": p.episode_no, "target_minutes": p.target_minutes,
            "status": p.status, "created_at": p.created_at.isoformat(),
            "run_id": cur[p.id].id if p.id in cur else None,
            "run_status": cur[p.id].status if p.id in cur else None,
            "current_node": cur[p.id].current_node if p.id in cur else None,
        } for p in projs]


@router.get("/projects/{pid}")
def get_project(pid: str):
    with session() as s:
        p = s.get(Project, pid)
        if not p:
            raise HTTPException(404, "项目不存在")
        return p.model_dump()


@router.post("/projects/{pid}/runs")
def start_run(pid: str):
    with session() as s:
        p = s.get(Project, pid)
        if not p:
            raise HTTPException(404, "项目不存在")
        run = Run(id=uuid.uuid4().hex[:12], project_id=pid, thread_id=uuid.uuid4().hex)
        s.add(run); s.commit(); s.refresh(run)
        rid = run.id
    runner.start_run(rid)
    return {"run_id": rid, "status": "running"}
