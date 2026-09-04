"""设置端点：模型档案、节点-模型绑定、节点 Agent 挂载（skills/MCP）、MCP 服务器登记。"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from ..agents import factory
from ..agents.node_registry import CONTENT_NODES, DEFAULT_SKILL_MOUNTS
from ..db import session
from ..llm import test_profile_connection
from ..models import McpServer, ModelProfile, NodeModelMap
from ..skills_loader import list_skills

router = APIRouter(prefix="/api", tags=["settings"])


# ---------------------------------------------------------------- 模型档案

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


# ---------------------------------------------------------------- 节点 Agent 挂载（skills / MCP）

@router.get("/skills")
def skills_catalog():
    """技能库目录（skills/ 目录下全部 SKILL.md 的名称+描述）。"""
    return {"skills": list_skills()}


@router.get("/node-agent-configs")
def get_node_agent_configs():
    """六个内容节点的 skills/MCP 挂载现状（未配置的按 §5.1 默认表显示）。"""
    factory.ensure_default_node_configs()
    return {
        "nodes": CONTENT_NODES,
        "defaults": DEFAULT_SKILL_MOUNTS,
        "configs": {n: factory.get_node_agent_config(n) for n in CONTENT_NODES},
    }


class NodeAgentConfigIn(BaseModel):
    skills: list[str] = []
    mcp_ids: list[int] = []


@router.put("/node-agent-configs/{node_id}")
def put_node_agent_config(node_id: str, cfg: NodeAgentConfigIn):
    try:
        saved = factory.save_node_agent_config(node_id, cfg.skills, cfg.mcp_ids)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "config": saved}


# ---------------------------------------------------------------- MCP 服务器登记

class McpServerIn(BaseModel):
    name: str
    transport: str = "http"          # http | sse | stdio | websocket
    url: str = ""
    command: str = ""
    args: list[str] = []
    env: dict[str, str] = {}
    headers: dict[str, str] = {}
    enabled: bool = True


def _mcp_out(srv: McpServer) -> dict:
    return {
        "id": srv.id, "name": srv.name, "transport": srv.transport,
        "url": srv.url, "command": srv.command,
        "args": json.loads(srv.args_json or "[]"),
        "env": json.loads(srv.env_json or "{}"),
        "headers": json.loads(srv.headers_json or "{}"),
        "enabled": srv.enabled,
    }


@router.get("/mcp-servers")
def list_mcp_servers():
    with session() as s:
        return {"servers": [_mcp_out(x) for x in s.exec(select(McpServer)).all()]}


@router.post("/mcp-servers")
def create_mcp_server(body: McpServerIn):
    if body.transport in ("http", "sse", "websocket") and not body.url:
        raise HTTPException(400, f"transport={body.transport} 需要 url")
    if body.transport == "stdio" and not body.command:
        raise HTTPException(400, "transport=stdio 需要 command")
    srv = McpServer(name=body.name, transport=body.transport, url=body.url,
                    command=body.command, args_json=json.dumps(body.args),
                    env_json=json.dumps(body.env), headers_json=json.dumps(body.headers),
                    enabled=body.enabled)
    with session() as s:
        s.add(srv); s.commit(); s.refresh(srv)
        return {"id": srv.id}


@router.put("/mcp-servers/{sid}")
def update_mcp_server(sid: int, body: McpServerIn):
    with session() as s:
        srv = s.get(McpServer, sid)
        if not srv:
            raise HTTPException(404, "MCP 服务器不存在")
        srv.name, srv.transport, srv.url, srv.command = body.name, body.transport, body.url, body.command
        srv.args_json = json.dumps(body.args)
        srv.env_json = json.dumps(body.env)
        srv.headers_json = json.dumps(body.headers)
        srv.enabled = body.enabled
        srv.updated_at = datetime.now(UTC)
        s.commit()
        return {"ok": True}


@router.delete("/mcp-servers/{sid}")
def delete_mcp_server(sid: int):
    with session() as s:
        srv = s.get(McpServer, sid)
        if srv:
            s.delete(srv); s.commit()
        return {"ok": True}


@router.post("/mcp-servers/{sid}/test")
def test_mcp_server(sid: int):
    """连通性测试：列出该服务器暴露的工具名。"""
    return factory.test_mcp_server(sid)

# ---------------------------------------------------------------- agent 运行轨迹回看

@router.get("/agent-traces")
def list_agent_traces(node_id: str | None = None, limit: int = 50):
    """列出最近的 agent 运行轨迹文件（新的在前），可按节点过滤。"""
    from .. import config
    d = config.DATA_DIR / "agent_traces"
    if not d.exists():
        return []
    files = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in files:
        nid = p.stem.split("_", 1)[1] if "_" in p.stem else ""
        if node_id and nid != node_id:
            continue
        out.append({"file": p.name, "node_id": nid,
                    "size": p.stat().st_size,
                    "mtime": datetime.fromtimestamp(p.stat().st_mtime, UTC).isoformat()})
        if len(out) >= limit:
            break
    return out


@router.get("/agent-traces/{fname}")
def read_agent_trace(fname: str):
    """读取单个轨迹文件全文。"""
    from .. import config
    if "/" in fname or "\\" in fname or ".." in fname:
        raise HTTPException(400, "非法文件名")
    p = config.DATA_DIR / "agent_traces" / fname
    if not p.exists() or p.suffix != ".md":
        raise HTTPException(404, "轨迹文件不存在")
    return {"file": fname, "content": p.read_text(encoding="utf-8")}