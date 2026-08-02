"""LangGraph 主图：节点 + 闸门 + 回退边（执行方案 §6.1 深化）。

架构要点：每个 AI 环节拆成「产出节点 → 闸门节点」两个图节点——
interrupt 只放在闸门里，resume 时闸门节点重跑是零成本，
避免 resume 重复调用 LLM 烧 token。
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ..state import PipelineState
from . import nodes

# 流水线节点顺序（前端状态条用）
PIPELINE_SEQUENCE = [
    ("n1_event_card_mining", "史料选矿"),
    ("gate_n1_event_cards", "事件卡闸门"),
    ("n2_style_robe_selection", "外衣选定"),
    ("gate_n2_style_card", "风格拍板"),
    ("n3_outline_blueprinting", "大纲蓝图"),
    ("gate_g1_theme_veto", "⛔主题否决关"),
    ("n4_narration_construction", "旁白施工"),
    ("gate_n4_script", "成稿闸门"),
    ("n5_draft_three_gate_audit", "三道门禁"),
    ("gate_n5_audit_verdict", "审核裁决"),
    ("n6_storyboard_translation", "画本翻译"),
    ("gate_n6_storyboard", "画本闸门"),
    ("n7_unit_voice_synthesis", "分段合成"),
    ("gate_n7_unit_listening", "单元试听"),
    ("n8_audio_mastering", "质检后期"),
    ("gate_g2_final_listening", "⛔审听签发"),
    ("finalize_episode_archive", "归档"),
]


def _decision(state: PipelineState) -> str:
    return (state.get("gate_decision") or {}).get("action", "approve")


# 各闸门的路由表：action → 下一节点
ROUTES = {
    "gate_n1_event_cards": {"approve": "n2_style_robe_selection", "reject": "n1_event_card_mining"},
    "gate_n2_style_card": {"approve": "n3_outline_blueprinting", "reject": "n2_style_robe_selection"},
    "gate_g1_theme_veto": {"approve": "n4_narration_construction", "reject": "n3_outline_blueprinting"},
    "gate_n4_script": {"approve": "n5_draft_three_gate_audit", "reject": "n4_narration_construction"},
    "gate_n5_audit_verdict": {"approve": "n6_storyboard_translation",
                              "send_back_to_n4": "n4_narration_construction",
                              "reject": "n4_narration_construction"},
    "gate_n6_storyboard": {"approve": "n7_unit_voice_synthesis", "reject": "n6_storyboard_translation"},
    "gate_n7_unit_listening": {"approve": "n8_audio_mastering",
                               "regen_units": "n7_failed_unit_regeneration"},
    "gate_g2_final_listening": {"approve": "finalize_episode_archive",
                                "regen_units": "n7_failed_unit_regeneration",
                                "reject": "n8_audio_mastering"},
}


def _router(gate_name: str):
    def route(state: PipelineState) -> str:
        action = _decision(state)
        return ROUTES[gate_name].get(action, ROUTES[gate_name]["approve"])
    return route


def build_graph(checkpointer=None):
    g = StateGraph(PipelineState)

    g.add_node("n1_event_card_mining", nodes.n1_event_card_mining)
    g.add_node("gate_n1_event_cards", nodes.gate_n1_event_cards)
    g.add_node("n2_style_robe_selection", nodes.n2_style_robe_selection)
    g.add_node("gate_n2_style_card", nodes.gate_n2_style_card)
    g.add_node("n3_outline_blueprinting", nodes.n3_outline_blueprinting)
    g.add_node("gate_g1_theme_veto", nodes.gate_g1_theme_veto)
    g.add_node("n4_narration_construction", nodes.n4_narration_construction)
    g.add_node("gate_n4_script", nodes.gate_n4_script)
    g.add_node("n5_draft_three_gate_audit", nodes.n5_draft_three_gate_audit)
    g.add_node("gate_n5_audit_verdict", nodes.gate_n5_audit_verdict)
    g.add_node("n6_storyboard_translation", nodes.n6_storyboard_translation)
    g.add_node("gate_n6_storyboard", nodes.gate_n6_storyboard)
    g.add_node("n7_unit_voice_synthesis", nodes.n7_unit_voice_synthesis)
    g.add_node("gate_n7_unit_listening", nodes.gate_n7_unit_listening)
    g.add_node("n7_failed_unit_regeneration", nodes.n7_failed_unit_regeneration)
    g.add_node("n8_audio_mastering", nodes.n8_audio_mastering)
    g.add_node("gate_g2_final_listening", nodes.gate_g2_final_listening)
    g.add_node("finalize_episode_archive", nodes.finalize_episode_archive)

    g.add_edge(START, "n1_event_card_mining")
    g.add_edge("n1_event_card_mining", "gate_n1_event_cards")
    g.add_edge("n2_style_robe_selection", "gate_n2_style_card")
    g.add_edge("n3_outline_blueprinting", "gate_g1_theme_veto")
    g.add_edge("n4_narration_construction", "gate_n4_script")
    g.add_edge("n5_draft_three_gate_audit", "gate_n5_audit_verdict")
    g.add_edge("n6_storyboard_translation", "gate_n6_storyboard")
    g.add_edge("n7_unit_voice_synthesis", "gate_n7_unit_listening")
    # 定点重生后回到单元试听闸门（G2 标塌段同理，重听后再进后期）
    g.add_edge("n7_failed_unit_regeneration", "gate_n7_unit_listening")
    g.add_edge("n8_audio_mastering", "gate_g2_final_listening")
    g.add_edge("finalize_episode_archive", END)

    for gate_name in ROUTES:
        g.add_conditional_edges(gate_name, _router(gate_name),
                                {v: v for v in set(ROUTES[gate_name].values())})

    return g.compile(checkpointer=checkpointer)
