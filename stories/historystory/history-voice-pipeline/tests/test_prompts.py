"""prompts.py 单测：人格 L1 常驻、节点标记、references 挂载、打回注入。"""
from app import prompts
from app.skills_loader import load_skill

BASE_STATE = {
    "source_type": "person", "source_text": "桀为虐政淫荒……", "target_minutes": 10,
    "episode_no": 1, "prev_episode_bridge": None,
    "event_cards": [{"卡号": "C-001", "冲突": "桀即位", "本集用不用": "用", "弹药潜质": ["钩子"]}],
    "style_card": {"风格名": "当年明月式", "本期语气示例": "示例句"},
    "outline": [{"段号": 1, "功能类型": "钩子", "章节标题": "章一", "预计字数": "60（容差 ±40%）"}],
    "script_md": "【段1·钩子】\n正文。",
}

ALL_BUILDERS = [
    lambda: prompts.build_n1_event_card_mining(BASE_STATE),
    lambda: prompts.build_n2_style_robe_selection(BASE_STATE),
    lambda: prompts.build_n3_outline_blueprinting(BASE_STATE),
    lambda: prompts.build_n4_chapter_construction(BASE_STATE, BASE_STATE["outline"], None),
    lambda: prompts.build_n4_full_script_stitch(BASE_STATE, ["章一稿"]),
    lambda: prompts.build_n5_three_gate_audit(BASE_STATE, {"AI腔禁词": []}),
    lambda: prompts.build_n6_storyboard_translation(BASE_STATE, {}),
]

EXPECTED_MARKERS = [
    "NODE:n1_event_card_mining", "NODE:n2_style_robe_selection",
    "NODE:n3_outline_blueprinting", "NODE:n4_narration_construction",
    "NODE:n4_full_script_stitch", "NODE:n5_three_gate_audit",
    "NODE:n6_storyboard_translation",
]


def test_every_system_has_node_marker_and_persona():
    persona = load_skill("persona-writer")
    for build, marker in zip(ALL_BUILDERS, EXPECTED_MARKERS):
        system, user, *_ = build()
        assert system.startswith(f"<!-- {marker} -->"), marker
        assert persona in system, f"{marker} 人格 L1 未常驻注入"


def test_n3_mounts_ammo_depot():
    system, *_ = prompts.build_n3_outline_blueprinting(BASE_STATE)
    assert load_skill("ammo-depot") in system


def test_n4_mounts_style_and_ammo():
    system, *_ = prompts.build_n4_chapter_construction(BASE_STATE, BASE_STATE["outline"], None)
    assert load_skill("ammo-depot") in system


def test_rework_section_injected_only_with_feedback():
    _, user1, _ = prompts.build_n1_event_card_mining(BASE_STATE)
    assert "打回重跑指令" not in user1
    _, user2, _ = prompts.build_n1_event_card_mining(
        BASE_STATE, feedback="卡片粒度太粗，重新拆", prev="[旧卡]")
    assert "打回重跑指令" in user2 and "卡片粒度太粗" in user2 and "按打回条目逐条修改" in user2


def test_memories_loaded_reported():
    _, _, loaded = prompts.build_n1_event_card_mining(BASE_STATE)
    assert "lessons.md" in loaded


def test_n2_user_contains_event_cards_and_schema():
    _, user, _ = prompts.build_n2_style_robe_selection(BASE_STATE)
    assert "C-001" in user and "本期语气示例" in user
