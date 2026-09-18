"""prompts.py 单测：人格 L1 常驻、节点标记、技能挂载清单、打回注入。

deepagents 架构下，技能正文不再全文注入 system，改为「挂载清单」引导
agent 渐进加载（read_file /skills/<name>/SKILL.md）。
"""
from app import prompts
from app.skills_loader import load_skill

BASE_STATE = {
    "source_type": "person", "source_text": "桀为虐政淫荒……", "target_minutes": 10,
    "episode_no": 1, "prev_episode_bridge": None,
    "event_cards": [{"卡号": "C-001", "冲突": "桀即位", "本集用不用": "用", "弹药潜质": ["钩子"]}],
    "style_card": {"风格名": "当年明月式", "本期语气示例": "示例句"},
    "outline": [{"段号": 1, "相位": "起", "段意": "现象链第1层", "关系类型": "递进",
                 "挂卡": "C-001", "情绪坐标": "戏谑（强度 3/5）",
                 "引出方式": "—（全篇起点）", "段尾欠条": "欠条", "预计字数": 200}],
    "script_md": "【段1·起】\n正文。",
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


def test_n3_mounts_outline_architect():
    """N3 默认挂载：outline-architect（主技能）+ persona-writer。"""
    system, *_ = prompts.build_n3_outline_blueprinting(BASE_STATE)
    assert "**outline-architect**（本节点主技能）" in system
    assert "persona-writer" in system
    assert "/skills/outline-architect/SKILL.md" in system or "渐进加载" in system
    # 技能正文不再全文注入（渐进加载），只有清单
    assert load_skill("outline-architect") not in system


def test_n4_mounts_narration_writer():
    system, *_ = prompts.build_n4_chapter_construction(BASE_STATE, BASE_STATE["outline"], None)
    assert "**narration-writer**（本节点主技能）" in system


def test_mounted_skills_override():
    """前端改挂载后，节点函数把实际清单传入 → prompt 清单与挂载一致。"""
    system, *_ = prompts.build_n1_event_card_mining(
        BASE_STATE, mounted_skills=["ammo-depot"])
    assert "**ammo-depot**（本节点主技能）" in system
    assert "historical-event-cards" not in system


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
    """N2 装配契约：消费旁白裸稿＋大纲段落表（情绪坐标），输出挂弹后成稿＋弹药装配报告。"""
    _, user, _ = prompts.build_n2_style_robe_selection(BASE_STATE)
    assert "C-001" in user
    assert "挂弹后成稿" in user and "弹药装配报告" in user
    assert "情绪坐标" in user and "悲悯" in user
    assert "抽走测验" in user and "筛句" in user  # 四步施工 SOP 在场
    assert "只做原地词级替换与句内微调" in user  # 结构铁律在场


def test_n4_prompt_strips_ammo_engine():
    """N4 裸稿纪律：无弹药投放引擎，段间咬合三问在场。"""
    _, user, _ = prompts.build_n4_chapter_construction(BASE_STATE, BASE_STATE["outline"], None)
    assert "写裸稿，弹药一律不碰" in user
    assert "弹药投放" not in user and "照单兑现" not in user
    assert "段间咬合三问" in user and "段尾欠条" in user
