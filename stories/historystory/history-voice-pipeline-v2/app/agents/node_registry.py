"""内容节点登记表：节点清单与 §5.1 默认技能挂载表。

单独成模块（无重依赖），供 factory / prompts / API / 前端共用一份真源。
"""
from __future__ import annotations

# 六个内容节点（LLM 驱动；N7 合成 / N8 后期为确定性工序，不走 agent）
CONTENT_NODES = [
    "n1_event_card_mining", "n2_style_robe_selection", "n3_outline_blueprinting",
    "n4_narration_construction", "n5_draft_three_gate_audit", "n6_storyboard_translation",
]

# 执行方案 §5.1 节点技能挂载表（默认种子，前端可逐节点调整）
DEFAULT_SKILL_MOUNTS: dict[str, list[str]] = {
    "n1_event_card_mining": ["historical-event-cards"],
    "n2_style_robe_selection": ["style-library", "persona-writer"],
    "n3_outline_blueprinting": ["outline-architect", "persona-writer", "ammo-depot"],
    "n4_narration_construction": ["narration-writer", "persona-writer",
                                  "style-library", "ammo-depot"],
    "n5_draft_three_gate_audit": ["narration-auditor", "persona-writer", "narration-writer"],
    "n6_storyboard_translation": ["tts-script-doctor"],
}
