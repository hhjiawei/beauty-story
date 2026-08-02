"""模型档案与节点绑定端点。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from ..db import session
from ..llm import test_profile_connection
from ..models import ModelProfile, NodeModelMap

router = APIRouter(prefix="/api", tags=["settings"])

CONTENT_NODES = [
    "n1_event_card_mining", "n2_style_robe_selection", "n3_outline_blueprinting",
    "n4_narration_construction", "n5_draft_three_gate_audit", "n6_storyboard_translation",
]


class ProfileIn(BaseModel):
    name: str
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.7
    provider: str = "openai"
    note: str = ""


def _safe(p: ModelProfile) -> dict:
    d = p.model_dump()
    d["api_key"] = "******" if p.api_key else ""
    return d


@router.get("/model-profiles")
def list_profiles():
    with session() as s:
        return [_safe(p) for p in s.exec(select(ModelProfile)).all()]


@router.post("/model-profiles")
def create_profile(p: ProfileIn):
    prof = ModelProfile(**p.model_dump())
    with session() as s:
        s.add(prof); s.commit(); s.refresh(prof)
        return {"id": prof.id}


@router.put("/model-profiles/{pid}")
def update_profile(pid: int, p: ProfileIn):
    with session() as s:
        prof = s.get(ModelProfile, pid)
        if not prof:
            raise HTTPException(404, "档案不存在")
        data = p.model_dump()
        if data["api_key"] in ("", "******"):
            data["api_key"] = prof.api_key
        for k, v in data.items():
            setattr(prof, k, v)
        s.commit()
        return {"ok": True}


@router.delete("/model-profiles/{pid}")
def delete_profile(pid: int):
    with session() as s:
        prof = s.get(ModelProfile, pid)
        if prof:
            s.delete(prof); s.commit()
        return {"ok": True}


@router.post("/model-profiles/{pid}/test")
def test_profile(pid: int):
    with session() as s:
        prof = s.get(ModelProfile, pid)
        if not prof:
            raise HTTPException(404, "档案不存在")
    return test_profile_connection(prof)


@router.get("/node-model-map")
def get_map():
    with session() as s:
        m = {r.node_id: r.profile_id for r in s.exec(select(NodeModelMap)).all()}
        return {"nodes": CONTENT_NODES, "map": m}


@router.put("/node-model-map")
def put_map(mapping: dict[str, int]):
    with session() as s:
        for node_id, profile_id in mapping.items():
            if node_id not in CONTENT_NODES:
                continue
            row = s.get(NodeModelMap, node_id)
            if row:
                row.profile_id = profile_id
            else:
                s.add(NodeModelMap(node_id=node_id, profile_id=profile_id))
        s.commit()
        return {"ok": True}
