"""全局状态契约（PipelineState）——先行定死，节点只读写自己的字段。

深化说明：LangGraph 的 state 在节点间以「合并」方式流转（本实现用 dict 合并，
list/dict 字段整体覆盖——节点返回自己字段的新值即可）。
大产物同时落盘文件（真相源），state 存内容与版本指针（索引）。
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict


class GateDecision(TypedDict, total=False):
    action: Literal["approve", "reject", "regen_units", "send_back_to_n4"]
    edited_content: Any          # 人工编辑后的产物内容（放行时携带 → 存新版本 origin=human_edit）
    feedback: str | None         # 打回意见（注入重跑 prompt）
    unit_ids: list[str]          # N7 勾选重生的单元 / G2 标塌段定位到的单元
    artifact_version: int | None


class PipelineState(TypedDict, total=False):
    # ── N0 任务信息（建任务时写入，全程只读）──
    project_id: str
    run_id: str
    source_type: Literal["dynasty", "person", "event"]
    source_text: str
    target_minutes: int
    episode_no: int
    prev_episode_bridge: str | None       # 上集承上启下段（第2集起必填）

    # ── N1 史料分析 ──
    event_cards: list[dict]               # 卡号/时间/地点/人物/冲突/史料出处/可信度/本集用不用/弹药潜质

    # ── N2 风格选定 ──
    style_candidates: list[dict]          # AI 推荐 1-2 种 + 理由 + 三维坐标评估
    style_card: dict                      # 风格名/核心气质/本期语气示例/技巧清单（人工拍板后写入）

    # ── N3 大纲生成 ──
    outline: list[dict]                   # 单集大纲文件（硬软字段全）
    theme_card: dict                      # 一句话主题/钩子选型+那一帧/主题自检三问答卷
    outline_checklist: list[dict]         # 举证式签发清单（过/不过+位置）

    # ── N4 旁白写作 ──
    script_md: str                        # 成稿（写作层第八节 schema）
    self_check: list[dict]                # 写作层自查清单记录

    # ── N5 成稿审核 ──
    audit_report: dict                    # 结构/语言/史实三门禁，逐项举证
    audit_passed: bool

    # ── N6 画本加工 ──
    storyboard: list[dict]                # 画本（语音层 Step 1 schema）

    # ── N7 分段合成 / N8 质检后期 ──
    audio_units: list[dict]               # 单元：unit_id/路径/状态(ok|ng)/重生次数
    final_audio: dict                     # 成品：路径/时长/字幕时间轴路径

    # ── 闸门通用 ──
    current_node: str
    gate_decision: GateDecision | None    # 最近一次闸门裁决（路由依据）
    rework_feedback: dict                 # {节点id: 打回意见}（注入重跑 prompt）
    rework_count: dict                    # {节点id: 次数}（≥3 触发告警）
    memories_loaded: list[str]            # 各节点加载的记忆文件（可审计）

    # ── 内部传递字段（下划线前缀，不进前端）──
    _n6_new_pronunciations: dict          # N6 画本扫出的新专名读音（归档时入库）
    _n6_return_to_writer: list[str]       # N6 发现的写作层问题（读不顺的句子）
