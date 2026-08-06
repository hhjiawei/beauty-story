"""测试公共夹具：临时数据目录 + mock 模型档案。"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    """把数据目录/数据库/checkpoint 全部指到临时目录，TTS 用 mock。"""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "data" / "pipeline.db")
    monkeypatch.setattr(config, "CHECKPOINT_DB_PATH", tmp_path / "data" / "checkpoints.db")
    monkeypatch.setattr(config, "MEMORY_DIR", tmp_path / "data" / "memory")
    monkeypatch.setattr(config, "REFS_DIR", tmp_path / "data" / "refs")
    monkeypatch.setattr(config, "AGENT_WORKSPACE_DIR", tmp_path / "data" / "agent_workspaces")
    monkeypatch.setattr(config, "TTS_BACKEND", "mock")
    config.ensure_dirs()
    from app import db
    db.reset_engine()
    from app.models import ModelProfile, NodeModelMap
    from app.agents.node_registry import CONTENT_NODES
    from app.db import session
    with session() as s:
        prof = ModelProfile(name="mock-test", provider="mock")
        s.add(prof); s.commit(); s.refresh(prof)
        for n in CONTENT_NODES:
            s.add(NodeModelMap(node_id=n, profile_id=prof.id))
        s.commit()
        pid = prof.id
    from app.agents import factory
    factory.ensure_default_node_configs()   # §5.1 默认挂载表播种
    factory.reset_agent_cache()
    from app.services import runner
    runner.reset_graph()
    yield {"profile_id": pid}
    factory.reset_agent_cache()
