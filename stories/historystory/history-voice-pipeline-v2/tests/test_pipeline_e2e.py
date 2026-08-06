"""端到端测试：mock LLM + mock TTS，从 N0 跑到 G2 签发归档。

覆盖执行方案的核心纪律：
- interrupt 闸门闭环（放行/编辑放行/打回重跑）
- 打回注入 + 版本递增（重跑不覆盖）
- N7 定点重生（不重跑全稿）/ G2 标塌段回退
- 归档沉淀（lessons.md、读音词典入库）
"""
import time

from app import config
from app.db import session
from app.models import Project, PronunciationEntry, Run
from app.services import artifacts, runner


def _mk_project() -> Project:
    proj = Project(
        id="testproj01", title="夏桀·第一集", source_type="person",
        source_text="桀为虐政淫荒。伐有施氏，得妺喜。筑倾宫瑶台。囚汤于夏台，已而释之。汤伐桀，战于鸣条，夏师败绩。桀走南巢，遂放而死。",
        target_minutes=10, episode_no=1,
    )
    with session() as s:
        s.add(proj)
        run = Run(id="testrun001", project_id=proj.id, thread_id="thread-e2e-1")
        s.add(run); s.commit(); s.refresh(proj)
    return proj


def _wait_gate(run_id: str, timeout: int = 120) -> str:
    """等到 waiting_review / done / error，返回 run.status。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        runner.wait(run_id, timeout=5)
        with session() as s:
            r = s.get(Run, run_id)
            if r.status in ("waiting_review", "done", "error"):
                return r.status
        time.sleep(0.3)
    raise TimeoutError("等闸门超时")


def _run_row(run_id: str) -> Run:
    with session() as s:
        return s.get(Run, run_id)


def test_full_pipeline(tmp_env):
    _mk_project()
    runner.start_run("testrun001")
    assert _wait_gate("testrun001") == "waiting_review"
    assert _run_row("testrun001").current_node == "gate_n1_event_cards"

    # ── 闸门1：打回（验证重跑注入 + 版本递增）──
    runner.resume_run("testrun001", {"action": "reject", "feedback": "卡片拆细一点"})
    assert _wait_gate("testrun001") == "waiting_review"
    assert artifacts.latest_artifact("testrun001", "n1_event_card_mining", "event_cards").version == 2

    # ── 闸门1：放行 → N2 ──
    runner.resume_run("testrun001", {"action": "approve"})
    assert _wait_gate("testrun001") == "waiting_review"
    assert _run_row("testrun001").current_node == "gate_n2_style_card"

    # ── 闸门2：人工编辑外衣卡后放行（origin=human_edit）──
    my_card = {"风格名": "当年明月式+昆汀式", "核心气质": "白话藏刀",
               "本期语气示例": "他输得连命都没剩下。", "核心技巧": ["口语化叙事"]}
    runner.resume_run("testrun001", {"action": "approve", "edited_content": my_card})
    assert _wait_gate("testrun001") == "waiting_review"
    assert _run_row("testrun001").current_node == "gate_g1_theme_veto"
    sc = artifacts.latest_artifact("testrun001", "n2_style_robe_selection", "style_card")
    assert sc.origin == "human_edit"

    # ── ⛔G1 主题否决关：放行 → N4 旁白施工 ──
    runner.resume_run("testrun001", {"action": "approve"})
    assert _wait_gate("testrun001") == "waiting_review"
    assert _run_row("testrun001").current_node == "gate_n4_script"
    assert artifacts.latest_artifact("testrun001", "n4_narration_construction", "script")

    # ── N4 放行 → N5 三道门禁（mock 全绿）──
    runner.resume_run("testrun001", {"action": "approve"})
    assert _wait_gate("testrun001") == "waiting_review"
    assert _run_row("testrun001").current_node == "gate_n5_audit_verdict"

    # ── N5 放行 → N6 画本 ──
    runner.resume_run("testrun001", {"action": "approve"})
    assert _wait_gate("testrun001") == "waiting_review"
    assert _run_row("testrun001").current_node == "gate_n6_storyboard"

    # ── N6 放行 → N7 分段合成 ──
    runner.resume_run("testrun001", {"action": "approve"})
    assert _wait_gate("testrun001") == "waiting_review"
    assert _run_row("testrun001").current_node == "gate_n7_unit_listening"
    units_a = artifacts.latest_artifact("testrun001", "n7_unit_voice_synthesis", "audio_unit")
    units = artifacts.load_artifact_content(units_a)
    assert len(units) >= 3
    import os
    assert all(os.path.exists(u["path"]) for u in units)

    # ── N7 试听：勾选 1 个单元定点重生 ──
    runner.resume_run("testrun001", {"action": "regen_units", "unit_ids": [units[0]["unit_id"]]})
    assert _wait_gate("testrun001") == "waiting_review"
    assert _run_row("testrun001").current_node == "gate_n7_unit_listening"

    # ── N7 再放行 → N8 后期 → ⛔G2 ──
    runner.resume_run("testrun001", {"action": "approve"})
    assert _wait_gate("testrun001") == "waiting_review"
    assert _run_row("testrun001").current_node == "gate_g2_final_listening"

    # ── ⛔G2 标塌段 → 回 N7 定点重生 → 再过 N8 → G2 ──
    runner.resume_run("testrun001", {"action": "regen_units", "unit_ids": [units[1]["unit_id"]]})
    assert _wait_gate("testrun001") == "waiting_review"
    assert _run_row("testrun001").current_node == "gate_n7_unit_listening"
    runner.resume_run("testrun001", {"action": "approve"})
    assert _wait_gate("testrun001") == "waiting_review"
    assert _run_row("testrun001").current_node == "gate_g2_final_listening"

    # ── ⛔G2 签发 → 归档 → done ──
    runner.resume_run("testrun001", {"action": "approve"})
    assert _wait_gate("testrun001") == "done"

    # ── 成品验证 ──
    fa = artifacts.load_artifact_content(
        artifacts.latest_artifact("testrun001", "n8_audio_mastering", "final_audio"))
    import os
    assert os.path.exists(fa["final_wav"]) and fa["duration_s"] > 1
    assert os.path.exists(fa["subtitle"])
    from app.tts import postprocess
    assert postprocess.wav_duration(fa["final_wav"]) > 1

    # ── 归档沉淀验证 ──
    with session() as s:
        assert s.get(PronunciationEntry, "妺喜") is not None  # 读音词典入库
        assert s.get(Project, "testproj01").status == "done"
    lessons = (config.MEMORY_DIR / "lessons.md").read_text(encoding="utf-8")
    assert "卡片拆细一点" in lessons  # 打回教训沉淀
    voice = (config.MEMORY_DIR / "voice_samples.md").read_text(encoding="utf-8")
    assert "他输得连命都没剩下" in voice  # 声口样句入库
