"""修复回归测试：JSON 加固 / 出错重试 / 项目删除 / 节点记录与日志。"""
import json
import time

import pytest
from fastapi.testclient import TestClient

from app import mock_llm_responses
from app.db import session
from app.llm import extract_json
from app.main import app
from app.models import Project, Run
from app.services import artifacts, runner


# ---------------------------------------------------------------- extract_json 加固

def test_extract_json_empty():
    with pytest.raises(ValueError, match="空内容"):
        extract_json("   ")


def test_extract_json_think_block():
    assert extract_json('<think>思考一下……</think>[{"a": 1}]') == [{"a": 1}]


def test_extract_json_code_fence_and_prose():
    assert extract_json('好的，结果如下：\n```json\n{"b": 2}\n```\n希望对你有帮助') == {"b": 2}


def test_extract_json_invalid_clear_error():
    with pytest.raises(ValueError, match="找不到合法 JSON"):
        extract_json("我今天不想输出JSON")


# ---------------------------------------------------------------- 出错 → 原地重试

def _mk_project(pid="retryproj", rid="retryrun"):
    with session() as s:
        s.add(Project(id=pid, title="重试测试", source_type="person",
                      source_text="桀为虐政淫荒。", target_minutes=10, episode_no=1))
        s.add(Run(id=rid, project_id=pid, thread_id=f"thread-{rid}"))
        s.commit()


def _wait(run_id, want=("waiting_review", "done", "error"), timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        runner.wait(run_id, timeout=5)
        with session() as s:
            r = s.get(Run, run_id)
            if r.status in want:
                return r.status
        time.sleep(0.3)
    raise TimeoutError(f"等 {want} 超时")


def test_node_error_then_retry(tmp_env, monkeypatch):
    """N1 连续两次返回垃圾 → 节点报错 run=error → 恢复后 retry → 原地续跑成功。"""
    _mk_project()
    real = mock_llm_responses.n1_event_cards
    calls = {"n": 0}

    def garbage(system, user):
        calls["n"] += 1
        if calls["n"] <= 2:                       # _llm_json 内部重试那次也废掉
            return "这不是JSON，模型瞎说了"
        return real(system, user)

    monkeypatch.setitem(mock_llm_responses.ROUTERS, "NODE:n1_event_card_mining", garbage)
    runner.start_run("retryrun")
    assert _wait("retryrun") == "error"
    with session() as s:
        r = s.get(Run, "retryrun")
        assert "解析失败" in (r.error or "") or "JSON" in (r.error or "")

    monkeypatch.setitem(mock_llm_responses.ROUTERS, "NODE:n1_event_card_mining", real)
    runner.retry_run("retryrun")
    assert _wait("retryrun") == "waiting_review"   # 原地重跑成功，到达闸门
    assert artifacts.latest_artifact("retryrun", "n1_event_card_mining", "event_cards")

    # 非 error 状态不允许重试
    with pytest.raises(ValueError):
        runner.retry_run("retryrun")


def test_internal_llm_json_retry(tmp_env, monkeypatch):
    """第一次返回垃圾、第二次返回合法 JSON → 节点内部自动重试，不进入 error。"""
    _mk_project("retryproj2", "retryrun2")
    real = mock_llm_responses.n1_event_cards
    calls = {"n": 0}

    def flaky(system, user):
        calls["n"] += 1
        return "乱说一通" if calls["n"] == 1 else real(system, user)

    monkeypatch.setitem(mock_llm_responses.ROUTERS, "NODE:n1_event_card_mining", flaky)
    runner.start_run("retryrun2")
    assert _wait("retryrun2") == "waiting_review"
    assert calls["n"] == 2                          # 内部重试了一次


# ---------------------------------------------------------------- 项目删除 / 查看端点

def test_delete_project_cascades(tmp_env):
    client = TestClient(app)
    pid = client.post("/api/projects", json={
        "title": "待删除", "source_type": "person", "source_text": "……",
        "target_minutes": 10, "episode_no": 1}).json()["id"]
    run_id = client.post(f"/api/projects/{pid}/runs").json()["run_id"]
    # 等到第一个闸门，产生产物与运行记录
    t0 = time.time()
    while time.time() - t0 < 90:
        snap = client.get(f"/api/runs/{run_id}").json()
        if snap["status"] == "waiting_review":
            break
        time.sleep(1)
    assert snap["status"] == "waiting_review"

    # 节点运行记录可查（查看选项）
    nrs = client.get(f"/api/runs/{run_id}/node-runs").json()
    assert any(n["node_id"] == "n1_event_card_mining" and n["status"] == "ok" for n in nrs)

    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 200 and r.json()["deleted_runs"] == 1
    assert client.get(f"/api/projects/{pid}").status_code == 404
    assert client.get(f"/api/runs/{run_id}").status_code == 404
    import pathlib
    from app import config
    assert not (config.DATA_DIR / "projects" / pid).exists()


def test_logs_tail_endpoint(tmp_env):
    client = TestClient(app)
    r = client.get("/api/logs/tail?lines=50")
    assert r.status_code == 200 and isinstance(r.json()["lines"], list)
