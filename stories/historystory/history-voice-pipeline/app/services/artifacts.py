"""产物版本管理（执行方案 §6.2）：文件落盘 + DB 版本记录，重跑不覆盖。"""
from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import select

from .. import config
from ..db import session
from ..models import Artifact

_EXT = {"script": "md", "subtitle": "json"}


def _project_dir(run_id: str) -> Path:
    with session() as s:
        a = s.exec(select(Artifact).where(Artifact.run_id == run_id)).first()
    # 目录按 run 存：data/projects/{project_id}/{run_id}/——project_id 由调用方传入更直接
    raise NotImplementedError  # 占位防误用


def artifact_dir(project_id: str, run_id: str, node_id: str) -> Path:
    d = config.DATA_DIR / "projects" / project_id / run_id / node_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def next_version(run_id: str, node_id: str, kind: str) -> int:
    with session() as s:
        rows = s.exec(
            select(Artifact).where(
                Artifact.run_id == run_id, Artifact.node_id == node_id, Artifact.kind == kind
            )
        ).all()
        return max([r.version for r in rows], default=0) + 1


def save_artifact(project_id: str, run_id: str, node_id: str, kind: str,
                  content, origin: str = "ai") -> Artifact:
    """content: dict/list → 存 json；str → 存 md/txt。返回 Artifact 行。"""
    version = next_version(run_id, node_id, kind)
    d = artifact_dir(project_id, run_id, node_id)
    ext = _EXT.get(kind, "json" if not isinstance(content, str) else "txt")
    path = d / f"{kind}_v{version}.{ext}"
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    with session() as s:
        a = Artifact(run_id=run_id, node_id=node_id, kind=kind,
                     version=version, origin=origin, file_path=str(path))
        s.add(a)
        s.commit()
        s.refresh(a)
        return a


def load_artifact_content(a: Artifact):
    p = Path(a.file_path)
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    if p.suffix == ".json":
        return json.loads(text)
    return text


def latest_artifact(run_id: str, node_id: str, kind: str) -> Artifact | None:
    with session() as s:
        rows = s.exec(
            select(Artifact).where(
                Artifact.run_id == run_id, Artifact.node_id == node_id, Artifact.kind == kind
            ).order_by(Artifact.version.desc())
        ).all()
        return rows[0] if rows else None
