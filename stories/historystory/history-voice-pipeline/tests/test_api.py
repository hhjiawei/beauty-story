"""API 集成测试：HTTP 层建任务 → 启动 → 等到闸门 → 快照含 pending_gate。"""
import time

from fastapi.testclient import TestClient

from app.main import app


def test_api_flow(tmp_env):
    client = TestClient(app)
    r = client.post("/api/projects", json={
        "title": "API测试·妺喜", "source_type": "person",
        "source_text": "有施氏女妺喜，桀伐有施得之。",
        "target_minutes": 10, "episode_no": 1,
    })
    assert r.status_code == 200, r.text
    pid = r.json()["id"]

    r = client.post(f"/api/projects/{pid}/runs")
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    deadline = time.time() + 90
    snap = {}
    while time.time() < deadline:
        snap = client.get(f"/api/runs/{run_id}").json()
        if snap["status"] in ("waiting_review", "error", "done"):
            break
        time.sleep(1)
    assert snap["status"] == "waiting_review", snap
    assert snap["pending_gate"] and snap["pending_gate"]["gate"] == "gate_n1_event_cards"
    assert "event_cards" in snap["pending_gate"]["artifacts"]
    # 流程条有全部节点
    assert len(snap["sequence"]) == 17

    # 放行 → 到下一个闸门
    client.post(f"/api/runs/{run_id}/approve", json={"action": "approve"})
    deadline = time.time() + 90
    while time.time() < deadline:
        snap = client.get(f"/api/runs/{run_id}").json()
        if snap["status"] == "waiting_review" and snap["pending_gate"] and            snap["pending_gate"]["gate"] != "gate_n1_event_cards":
            break
        time.sleep(1)
    assert snap["pending_gate"]["gate"] == "gate_n2_style_card"

    # 打回必须带意见
    r = client.post(f"/api/runs/{run_id}/reject", json={"action": "reject"})
    assert r.status_code == 400

    # 设置页端点
    assert client.get("/api/model-profiles").status_code == 200
    m = client.get("/api/node-model-map").json()
    assert "n1_event_card_mining" in m["map"] or m["map"].get("n1_event_card_mining") is not None
    # 读音词典
    assert client.post("/api/pronunciation-dict",
                       json={"word": "斟鄩", "pinyin": "zhēn xún"}).status_code == 200
    assert any(d["word"] == "斟鄩" for d in client.get("/api/pronunciation-dict").json())


def test_second_episode_requires_bridge(tmp_env):
    client = TestClient(app)
    r = client.post("/api/projects", json={
        "title": "第二集无衔接段", "source_type": "dynasty",
        "source_text": "……", "target_minutes": 20, "episode_no": 2,
    })
    assert r.status_code == 400
    r = client.post("/api/projects", json={
        "title": "第二集有衔接段", "source_type": "dynasty",
        "source_text": "……", "target_minutes": 20, "episode_no": 2,
        "prev_episode_bridge": "上一集讲到桀放走了汤。",
    })
    assert r.status_code == 200
