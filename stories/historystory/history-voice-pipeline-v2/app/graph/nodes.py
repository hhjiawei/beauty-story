"""流水线节点实现。

命名即含义（执行方案 §4.0 深化）：
  产出节点                          闸门节点（人工）
  n1_event_card_mining     史料选矿  gate_n1_event_cards
  n2_style_robe_selection  外衣选定  gate_n2_style_card
  n3_outline_blueprinting  大纲蓝图  gate_g1_theme_veto      ⛔主题否决关（强制）
  n4_narration_construction 旁白施工 gate_n4_script
  n5_draft_three_gate_audit 三道门禁 gate_n5_audit_verdict
  n6_storyboard_translation 画本翻译 gate_n6_storyboard
  n7_unit_voice_synthesis  分段合成  gate_n7_unit_listening
  n7_failed_unit_regeneration 塌段定点重生
  n8_audio_mastering       质检后期  gate_g2_final_listening ⛔审听签发
  finalize_episode_archive 归档（教训沉淀/读音入库）

闸门纪律（§6.3）：打回重跑 = 原始输入 + 上一版产物 + 打回意见，
prompt 明确要求「按条目修改，不重写全文」。
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from langgraph.types import interrupt
from sqlmodel import select

from .. import config, prompts
from ..agents import factory
from ..db import session
from ..llm import extract_json
from ..models import NodeRun, Project, PronunciationEntry, Review
from ..services import artifacts
from ..services.scans import has_hard_violations, run_all_scans
from ..tts import engine as tts_engine
from ..tts import postprocess

# ---------------------------------------------------------------- 工具

def _node_log(run_id: str, node_id: str, fn):
    """节点运行日志（耗时/状态/错误）：node_runs 表 + pipeline.log 文件双写。"""
    from ..logging_setup import get_logger
    log = get_logger()
    log.info("节点开始 run=%s node=%s", run_id, node_id)
    with session() as s:
        nr = NodeRun(run_id=run_id, node_id=node_id, status="running")
        s.add(nr); s.commit(); s.refresh(nr)
        nid = nr.id
    try:
        result = fn()
    except Exception as e:
        log.error("节点失败 run=%s node=%s err=%s", run_id, node_id, e, exc_info=True)
        with session() as s:
            nr = s.get(NodeRun, nid)
            nr.status = "error"; nr.error = str(e)[:500]
            nr.finished_at = datetime.now(UTC); s.commit()
        raise
    with session() as s:
        nr = s.get(NodeRun, nid)
        nr.status = "ok"; nr.finished_at = datetime.now(UTC); s.commit()
    log.info("节点完成 run=%s node=%s", run_id, node_id)
    return result


def _llm(node_id: str, system: str, user: str):
    """内容节点的 LLM 调用一律走 deepagents 实例（独立模型 + 挂载技能 + MCP 工具）。"""
    return factory.run_node_agent(node_id, system, user)


def _mounted_skills(node_id: str) -> list[str]:
    """该节点当前实际挂载的技能清单（与 agent 工作区同源，prompt 清单随之同步）。"""
    return factory.get_node_agent_config(node_id)["skills"]


def _llm_json(node_id: str, system: str, user: str, retries: int = 1, expect: type | None = None):
    """调用 LLM 并解析 JSON；解析失败/顶层类型不符自动重试一次（附强约束）。

    expect：指定期望的顶层类型（dict 或 list）。模型常见翻车是「该给对象时
    给了数组」——下游 .get() 会炸出 'list' object has no attribute 'get'，
    这里提前拦下并走格式重试。
    """
    from ..logging_setup import get_logger
    log = get_logger()
    last_err = None
    cur_user = user
    for attempt in range(retries + 1):
        try:
            raw = _llm(node_id, system, cur_user)
        except Exception as e:  # noqa: BLE001
            # 调用层错误（MCP 工具失败/网络/鉴权等）：直接报真实原因，
            # 不做「只输出 JSON」的格式重试——重试也治不好它。
            log.error("%s agent 调用失败: %s", node_id, e, exc_info=True)
            raise RuntimeError(f"[{node_id}] agent 调用失败: {e}") from e
        log.info("%s LLM 返回 %d 字（第 %d 次）", node_id, len(raw or ""), attempt + 1)
        try:
            obj = extract_json(raw)
            # 容错：模型常把对象包成单元素数组 [{...}]，自动拆包（记日志可审计）
            if expect is dict and isinstance(obj, list) \
                    and len(obj) == 1 and isinstance(obj[0], dict):
                log.warning("%s 输出为单元素数组包对象，已自动拆包", node_id)
                obj = obj[0]
            if expect is not None and not isinstance(obj, expect):
                want = "JSON 对象 {...}" if expect is dict else "JSON 数组 [...]"
                got = "数组" if isinstance(obj, list) else ("对象" if isinstance(obj, dict) else type(obj).__name__)
                raise ValueError(f"顶层应为 {want}，实际返回了{got}")
            return obj
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("%s 第 %d 次解析失败: %s", node_id, attempt + 1, e)
            want_hint = ""
            if expect is dict:
                want_hint = "（必须是一个 JSON 对象 {...}，不是数组）"
            elif expect is list:
                want_hint = "（必须是一个 JSON 数组 [...]，不是对象）"
            cur_user = user + (
                "\n\n## ⚠️ 格式重试\n你上一次的输出不符合要求。"
                f"这次请只输出一个合法 JSON{want_hint}（不要 markdown 代码块、不要任何解释文字）。")
    raise RuntimeError(f"[{node_id}] LLM 输出解析失败（已重试 {retries} 次）: {last_err}")


def _record_review(state, node_id: str, artifact_id, action: str, feedback=None):
    with session() as s:
        s.add(Review(artifact_id=artifact_id or 0, run_id=state["run_id"],
                     node_id=node_id, action=action, feedback=feedback))
        s.commit()


def _bump_rework(state, node_id: str) -> dict:
    rc = dict(state.get("rework_count", {}))
    rc[node_id] = rc.get(node_id, 0) + 1
    return rc


def _gate(state, *, gate_node: str, artifact_node: str, kinds: list[str]):
    """闸门公共件：把最新产物打包给前端，interrupt 等人工裁决。"""
    payload = {"gate": gate_node, "node": artifact_node, "run_id": state["run_id"],
               "artifacts": {}, "rework_count": state.get("rework_count", {}).get(artifact_node, 0)}
    for kind in kinds:
        a = artifacts.latest_artifact(state["run_id"], artifact_node, kind)
        if a:
            payload["artifacts"][kind] = {
                "artifact_id": a.id, "version": a.version, "origin": a.origin,
                "content": artifacts.load_artifact_content(a),
            }
    return interrupt(payload)


def _save_human_edit(state, gate_node: str, artifact_node: str, kind: str,
                     edited_content, origin="human_edit"):
    """人工编辑后放行：存新版本，不覆盖。"""
    return artifacts.save_artifact(state["project_id"], state["run_id"],
                                   artifact_node, kind, edited_content, origin=origin)


# ---------------------------------------------------------------- N1 史料分析 · 事件卡选矿

def n1_event_card_mining(state):
    node = "n1_event_card_mining"
    fb = state.get("rework_feedback", {}).get(node)

    def work():
        prev = json.dumps(state.get("event_cards"), ensure_ascii=False) if fb else None
        system, user, loaded = prompts.build_n1_event_card_mining(state, feedback=fb, prev=prev, mounted_skills=_mounted_skills(node))
        cards = _llm_json(node, system, user, expect=list)
        a = artifacts.save_artifact(state["project_id"], state["run_id"], node,
                                    "event_cards", cards, origin="rework" if fb else "ai")
        return cards, loaded, a
    cards, loaded, a = _node_log(state["run_id"], node, work)
    return {"event_cards": cards, "current_node": node,
            "memories_loaded": state.get("memories_loaded", []) + loaded}


def gate_n1_event_cards(state):
    review = _gate(state, gate_node="gate_n1_event_cards",
                   artifact_node="n1_event_card_mining", kinds=["event_cards"])
    if review.get("action") == "reject":
        _record_review(state, "n1_event_card_mining", None, "reject", review.get("feedback"))
        fb = dict(state.get("rework_feedback", {}))
        fb["n1_event_card_mining"] = review.get("feedback", "")
        return {"gate_decision": review, "rework_feedback": fb,
                "rework_count": _bump_rework(state, "n1_event_card_mining")}
    if review.get("edited_content") is not None:
        _save_human_edit(state, "gate_n1_event_cards", "n1_event_card_mining",
                         "event_cards", review["edited_content"])
        return {"gate_decision": review, "event_cards": review["edited_content"]}
    _record_review(state, "n1_event_card_mining", None, "approve")
    return {"gate_decision": review}


# ---------------------------------------------------------------- N2 风格选定 · 本期外衣

def n2_style_robe_selection(state):
    node = "n2_style_robe_selection"
    fb = state.get("rework_feedback", {}).get(node)

    def work():
        prev = json.dumps(state.get("style_candidates"), ensure_ascii=False) if fb else None
        system, user, loaded = prompts.build_n2_style_robe_selection(state, feedback=fb, prev=prev, mounted_skills=_mounted_skills(node))
        result = _llm_json(node, system, user, expect=dict)

        # 键名兼容：旧版出「候选风格」数组；新方法论直接定案唯一风格，取「风格定案」单件
        candidates = result.get("候选风格") or ([result["风格定案"]] if result.get("风格定案") else [])

        a = artifacts.save_artifact(state["project_id"], state["run_id"], node,
                                    "style_candidates", result, origin="rework" if fb else "ai")
        return candidates, result, loaded, a
    candidates, result, loaded, a = _node_log(state["run_id"], node, work)
    return {"style_candidates": candidates, "current_node": node,
            "memories_loaded": state.get("memories_loaded", []) + loaded}


def gate_n2_style_card(state):
    """人工拍板（必选动作）：确认或改选风格 → 写入 style_card。"""
    review = _gate(state, gate_node="gate_n2_style_card",
                   artifact_node="n2_style_robe_selection", kinds=["style_candidates"])
    if review.get("action") == "reject":
        _record_review(state, "n2_style_robe_selection", None, "reject", review.get("feedback"))
        fb = dict(state.get("rework_feedback", {}))
        fb["n2_style_robe_selection"] = review.get("feedback", "")
        return {"gate_decision": review, "rework_feedback": fb,
                "rework_count": _bump_rework(state, "n2_style_robe_selection")}
    # 拍板：edited_content 为最终外衣卡；未改则默认取第一个候选
    card = review.get("edited_content")
    if card is None:
        card = (state.get("style_candidates") or [{}])[0]
    _save_human_edit(state, "gate_n2_style_card", "n2_style_robe_selection", "style_card", card)
    _record_review(state, "n2_style_robe_selection", None, "approve")
    # 声口样句入库（人格 L2）
    from .. import memory_store
    yj = card.get("本期语气示例") or (card.get("风格定案") or {}).get("本期语气示例")
    if yj:
        fname = card.get("风格名") or (card.get("风格定案") or {}).get("风格名", "?")
        memory_store.append_memory(memory_store.VOICE_SAMPLES,
                                   f"外衣「{fname}」语气示例：{yj}")
    return {"gate_decision": review, "style_card": card}


# ---------------------------------------------------------------- N3 大纲生成 · 蓝图绘制

def n3_outline_blueprinting(state):
    node = "n3_outline_blueprinting"
    fb = state.get("rework_feedback", {}).get(node)

    def work():
        prev = json.dumps({"主题卡": state.get("theme_card"), "大纲": state.get("outline")},
                          ensure_ascii=False) if fb else None
        system, user, loaded = prompts.build_n3_outline_blueprinting(state, feedback=fb, prev=prev, mounted_skills=_mounted_skills(node))
        result = _llm_json(node, system, user, expect=dict)

        # 大纲包键名兼容：新方法论「段级施工卡 / 篇级总卡」，旧版「单集大纲文件 / 主题卡」
        outline = result.get("段级施工卡") or result.get("单集大纲文件") or []
        theme = result.get("篇级总卡") or result.get("主题卡") or {}
        checklist = result.get("签发清单", [])

        if not outline:
            raise RuntimeError(
                f"[{node}] 大纲包里没有可用的段落清单（段级施工卡/单集大纲文件均为空）。"
                f"实际返回的顶层键：{list(result.keys())}"
                "——请核对 prompts.py 的 N3 输出 Schema 键名是否与此处提取键一致。")
        artifacts.save_artifact(state["project_id"], state["run_id"], node,
                                "outline", result, origin="rework" if fb else "ai")
        artifacts.save_artifact(state["project_id"], state["run_id"], node, "theme_card", theme)
        return outline, theme, checklist, loaded
    outline, theme, checklist, loaded = _node_log(state["run_id"], node, work)
    return {"outline": outline, "theme_card": theme, "outline_checklist": checklist,
            "current_node": node, "memories_loaded": state.get("memories_loaded", []) + loaded}


def gate_g1_theme_veto(state):
    """⛔ 主题否决关：只展示主题卡三样东西，不过不进 N4。"""
    review = _gate(state, gate_node="gate_g1_theme_veto",
                   artifact_node="n3_outline_blueprinting", kinds=["theme_card", "outline"])
    if review.get("action") == "reject":
        _record_review(state, "n3_outline_blueprinting", None, "reject", review.get("feedback"))
        fb = dict(state.get("rework_feedback", {}))
        fb["n3_outline_blueprinting"] = review.get("feedback", "")
        return {"gate_decision": review, "rework_feedback": fb,
                "rework_count": _bump_rework(state, "n3_outline_blueprinting")}
    _record_review(state, "n3_outline_blueprinting", None, "approve")
    return {"gate_decision": review}


# ---------------------------------------------------------------- N4 旁白写作 · 逐章施工+全稿缝合

def _group_chapters(outline: list[dict]) -> list[list[dict]]:
    chapters: dict[str, list[dict]] = {}
    order: list[str] = []
    for seg in outline:

        # 分章键名兼容：旧版「章节标题」，新方法论段级施工卡用「模块归属」（①钩子…⑥尾声）
        title = seg.get("章节标题") or seg.get("模块归属") or f"章{seg.get('段号')}"

        if title not in chapters:
            chapters[title] = []
            order.append(title)
        chapters[title].append(seg)
    return [chapters[t] for t in order]


def n4_narration_construction(state):
    node = "n4_narration_construction"
    fb = state.get("rework_feedback", {}).get(node)

    def work():
        outline = state.get("outline", [])
        if not outline:
            raise RuntimeError(
                f"[{node}] 收到空大纲（state['outline'] 为空），拒绝空跑模型浪费 token。"
                "请回退到 G1 闸门检查 N3 产物：大纲包里是否真有段级施工卡，"
                "以及 N3 输出键名是否与提取键一致。")
        chapters = _group_chapters(outline)

        drafts, prev_tail, switches = [], None, []
        for ch in chapters:
            system, user, _ = prompts.build_n4_chapter_construction(
                state, ch, prev_tail, feedback=fb if not drafts else None,
                mounted_skills=_mounted_skills(node))
            r = _llm_json(node, system, user, expect=dict)
            drafts.append(r.get("本章正文", ""))
            prev_tail = r.get("本章正文", "")[-300:]

            # 键名兼容：新方法论「技法弹药调整声明」，旧版「技法切换声明」
            switches += r.get("技法弹药调整声明") or r.get("技法切换声明") or []

        system, user, _ = prompts.build_n4_full_script_stitch(state, drafts, mounted_skills=_mounted_skills(node))
        final = _llm_json(node, system, user, expect=dict)
        script = final.get("成稿", "")
        self_check = final.get("自查清单", []) + [{"item": "技法切换声明", "verdict": "过",
                                                  "location": "; ".join(switches) or "无"}]
        artifacts.save_artifact(state["project_id"], state["run_id"], node,
                                "script", script, origin="rework" if fb else "ai")
        return script, self_check
    script, self_check = _node_log(state["run_id"], node, work)
    return {"script_md": script, "self_check": self_check, "current_node": node}


def gate_n4_script(state):
    review = _gate(state, gate_node="gate_n4_script",
                   artifact_node="n4_narration_construction", kinds=["script"])
    if review.get("action") == "reject":
        _record_review(state, "n4_narration_construction", None, "reject", review.get("feedback"))
        fb = dict(state.get("rework_feedback", {}))
        fb["n4_narration_construction"] = review.get("feedback", "")
        return {"gate_decision": review, "rework_feedback": fb,
                "rework_count": _bump_rework(state, "n4_narration_construction")}
    if review.get("edited_content") is not None:
        _save_human_edit(state, "gate_n4_script", "n4_narration_construction",
                         "script", review["edited_content"])
        return {"gate_decision": review, "script_md": review["edited_content"]}
    _record_review(state, "n4_narration_construction", None, "approve")
    return {"gate_decision": review}


# ---------------------------------------------------------------- N5 成稿审核 · 三道门禁

def n5_draft_three_gate_audit(state):
    node = "n5_draft_three_gate_audit"

    def work():
        script = state.get("script_md", "")
        scan_findings = run_all_scans(script, state.get("outline", []))
        system, user, loaded = prompts.build_n5_three_gate_audit(state, scan_findings, mounted_skills=_mounted_skills(node))
        report = _llm_json(node, system, user, expect=dict)
        report["确定性扫描"] = scan_findings
        hard = has_hard_violations(scan_findings)
        passed = bool(report.get("passed")) and not hard
        if hard:
            report.setdefault("打回条目", []).insert(
                0, "确定性扫描发现硬伤（AI腔禁词/过渡套话/零信息量感慨），逐条清除")
            report["passed"] = False
        artifacts.save_artifact(state["project_id"], state["run_id"], node,
                                "audit_report", report)
        return report, passed
    report, passed = _node_log(state["run_id"], node, work)
    return {"audit_report": report, "audit_passed": passed, "current_node": node}


def gate_n5_audit_verdict(state):
    """全绿放行 / 按条目打回 N4（send_back_to_n4 或 reject 同义）。"""
    review = _gate(state, gate_node="gate_n5_audit_verdict",
                   artifact_node="n5_draft_three_gate_audit", kinds=["audit_report"])
    if review.get("action") in ("reject", "send_back_to_n4"):
        items = state.get("audit_report", {}).get("打回条目", [])
        composed = "审核打回条目：\n" + "\n".join(f"- {x}" for x in items)
        if review.get("feedback"):
            composed += "\n人工补充意见：\n" + review["feedback"]
        _record_review(state, "n5_draft_three_gate_audit", None, "reject", composed)
        fb = dict(state.get("rework_feedback", {}))
        fb["n4_narration_construction"] = composed
        return {"gate_decision": {"action": "send_back_to_n4"}, "rework_feedback": fb,
                "rework_count": _bump_rework(state, "n4_narration_construction")}
    _record_review(state, "n5_draft_three_gate_audit", None, "approve")
    return {"gate_decision": review}


# ---------------------------------------------------------------- N6 画本加工 · 声音翻译

def _pronunciation_dict() -> dict:
    with session() as s:
        return {e.word: e.pinyin for e in s.exec(select(PronunciationEntry)).all()}


def n6_storyboard_translation(state):
    node = "n6_storyboard_translation"
    fb = state.get("rework_feedback", {}).get(node)

    def work():
        prev = json.dumps(state.get("storyboard"), ensure_ascii=False) if fb else None
        system, user, loaded = prompts.build_n6_storyboard_translation(
            state, _pronunciation_dict(), feedback=fb, prev=prev,
            mounted_skills=_mounted_skills(node))
        result = _llm_json(node, system, user, expect=dict)
        pages = result.get("画本", [])
        artifacts.save_artifact(state["project_id"], state["run_id"], node,
                                "storyboard", result, origin="rework" if fb else "ai")
        return pages, result, loaded
    pages, result, loaded = _node_log(state["run_id"], node, work)
    return {"storyboard": pages, "current_node": node,
            "_n6_new_pronunciations": result.get("新增读音", {}),
            "_n6_return_to_writer": result.get("打回写作层条目", []),
            "memories_loaded": state.get("memories_loaded", []) + loaded}


def gate_n6_storyboard(state):
    review = _gate(state, gate_node="gate_n6_storyboard",
                   artifact_node="n6_storyboard_translation", kinds=["storyboard"])
    if review.get("action") == "reject":
        _record_review(state, "n6_storyboard_translation", None, "reject", review.get("feedback"))
        fb = dict(state.get("rework_feedback", {}))
        fb["n6_storyboard_translation"] = review.get("feedback", "")
        return {"gate_decision": review, "rework_feedback": fb,
                "rework_count": _bump_rework(state, "n6_storyboard_translation")}
    if review.get("edited_content") is not None:
        pages = review["edited_content"].get("画本", review["edited_content"]) if isinstance(review["edited_content"], dict) else review["edited_content"]
        _save_human_edit(state, "gate_n6_storyboard", "n6_storyboard_translation",
                         "storyboard", review["edited_content"])
        return {"gate_decision": review, "storyboard": pages}
    _record_review(state, "n6_storyboard_translation", None, "approve")
    return {"gate_decision": review}


# ---------------------------------------------------------------- N7 分段合成 / 定点重生

def _unit_id(page: dict, idx: int) -> str:
    return f"seg{int(page.get('段号', 0)):03d}_u{idx}"


def _synth_all(state) -> list[dict]:
    """按画本逐单元合成（弹药的击发工序）。"""
    out_dir = artifacts.artifact_dir(state["project_id"], state["run_id"], "n7_unit_voice_synthesis")
    units = []
    pages = state.get("storyboard", [])
    for pi, page in enumerate(pages):
        for i, text in enumerate(page.get("拆分", [])):
            uid = _unit_id(page, i)
            path = str(out_dir / f"{uid}.wav")
            tts_engine.synthesize_unit(
                text=text, out_path=path,
                emotion=page.get("情感", ""), emo_alpha=page.get("情感强度", 0.7),
                speed=page.get("语速", 1.0), duration_target_s=page.get("时长目标_s"),
            )
            units.append({
                "unit_id": uid, "text": text, "path": path, "status": "ok",
                "regen_count": 0, "page_index": pi,
                "前停顿_ms": page.get("前停顿_ms", 0) if i == 0 else 0,
                "后停顿_ms": page.get("后停顿_ms", 0) if i == len(page.get("拆分", [])) - 1 else 0,
                "chapter_break": False,
            })
    # 章间静音：每章首单元标记
    titles = []
    for seg in state.get("outline", []):
        t = seg.get("章节标题") or seg.get("模块归属")
        if t and t not in titles:
            titles.append(t)
    chapter_first_seg = {}
    for seg in state.get("outline", []):
        t = seg.get("章节标题") or seg.get("模块归属")
        if t and t not in chapter_first_seg:
            chapter_first_seg[t] = seg.get("段号")
    first_segs = set(chapter_first_seg.values()) - {1}
    for u in units:
        if int(u["unit_id"][3:6]) in first_segs:
            u["chapter_break"] = True
    return units


def n7_unit_voice_synthesis(state):
    node = "n7_unit_voice_synthesis"

    def work():
        units = _synth_all(state)
        artifacts.save_artifact(state["project_id"], state["run_id"], node,
                                "audio_unit", units)
        return units
    units = _node_log(state["run_id"], node, work)
    return {"audio_units": units, "current_node": node}


def n7_failed_unit_regeneration(state):
    """定点重生：只重生勾选/塌段单元，不重跑全稿（语音层手册 Step 3 返工纪律）。"""
    node = "n7_failed_unit_regeneration"
    ids = set((state.get("gate_decision") or {}).get("unit_ids") or [])

    def work():
        units = [dict(u) for u in state.get("audio_units", [])]
        for u in units:
            if u["unit_id"] in ids:
                page = state["storyboard"][u["page_index"]]
                tts_engine.synthesize_unit(
                    text=u["text"], out_path=u["path"],
                    emotion=page.get("情感", ""), emo_alpha=page.get("情感强度", 0.7),
                    speed=page.get("语速", 1.0), duration_target_s=page.get("时长目标_s"),
                )
                u["regen_count"] = u.get("regen_count", 0) + 1
                u["status"] = "ok"
        artifacts.save_artifact(state["project_id"], state["run_id"], node,
                                "audio_unit", units, origin="rework")
        return units
    units = _node_log(state["run_id"], node, work)
    return {"audio_units": units, "current_node": node,
            "gate_decision": {"action": "approve"}}  # 复位路由标记


def gate_n7_unit_listening(state):
    review = _gate(state, gate_node="gate_n7_unit_listening",
                   artifact_node="n7_unit_voice_synthesis", kinds=["audio_unit"])
    if review.get("action") == "regen_units":
        _record_review(state, "n7_unit_voice_synthesis", None, "regen_units",
                       ",".join(review.get("unit_ids", [])))
        return {"gate_decision": review}
    _record_review(state, "n7_unit_voice_synthesis", None, "approve")
    return {"gate_decision": review}


# ---------------------------------------------------------------- N8 质检后期（FFmpeg 全自动）

def n8_audio_mastering(state):
    node = "n8_audio_mastering"

    def work():
        out_dir = artifacts.artifact_dir(state["project_id"], state["run_id"], node)
        raw = str(out_dir / "concat_raw.wav")
        final = str(out_dir / "final.wav")
        timeline = postprocess.concat_units(state.get("audio_units", []), raw)
        master_info = postprocess.ffmpeg_master(raw, final)
        mp3 = str(out_dir / "final.mp3")
        has_mp3 = postprocess.to_mp3(final, mp3)
        sub = str(out_dir / "subtitle_timeline.json")
        postprocess.write_subtitle(timeline, sub)
        result = {
            "final_wav": final, "final_mp3": mp3 if has_mp3 else None,
            "subtitle": sub, "duration_s": postprocess.wav_duration(final),
            "units": len(timeline), "master": master_info,
        }
        artifacts.save_artifact(state["project_id"], state["run_id"], node, "final_audio", result)
        artifacts.save_artifact(state["project_id"], state["run_id"], node, "subtitle", timeline)
        return result
    result = _node_log(state["run_id"], node, work)
    return {"final_audio": result, "current_node": node}


def gate_g2_final_listening(state):
    """⛔ 审听签发：三条过关线（无错字/情绪曲线一致/忘掉是AI）。"""
    review = _gate(state, gate_node="gate_g2_final_listening",
                   artifact_node="n8_audio_mastering", kinds=["final_audio", "subtitle"])
    if review.get("action") == "regen_units":  # 标塌段 → 回 N7 定点重生
        _record_review(state, "n8_audio_mastering", None, "regen_units",
                       ",".join(review.get("unit_ids", [])))
        return {"gate_decision": review}
    if review.get("action") == "reject":
        _record_review(state, "n8_audio_mastering", None, "reject", review.get("feedback"))
        fb = dict(state.get("rework_feedback", {}))
        fb["n8_audio_mastering"] = review.get("feedback", "")
        return {"gate_decision": review, "rework_feedback": fb,
                "rework_count": _bump_rework(state, "n8_audio_mastering")}
    _record_review(state, "n8_audio_mastering", None, "approve")
    return {"gate_decision": review}


# ---------------------------------------------------------------- 归档

def finalize_episode_archive(state):
    """任务归档：打回教训沉淀（人格 L2）+ 读音词典增量入库。"""
    node = "finalize_episode_archive"

    def work():
        from .. import memory_store
        with session() as s:
            rejects = s.exec(select(Review).where(
                Review.run_id == state["run_id"], Review.action == "reject")).all()
            if rejects:
                entry = f"任务 {state['run_id']} 打回教训：\n" + "\n".join(
                    f"- [{r.node_id}] {r.feedback}" for r in rejects if r.feedback)
                memory_store.append_memory(memory_store.LESSONS, entry)
            for word, pinyin in (state.get("_n6_new_pronunciations") or {}).items():
                if not s.get(PronunciationEntry, word):
                    s.add(PronunciationEntry(word=word, pinyin=pinyin,
                                             source_run_id=state["run_id"]))
            proj = s.get(Project, state["project_id"])
            if proj:
                proj.status = "done"
            s.commit()
        return True
    _node_log(state["run_id"], node, work)
    return {"current_node": node}
