#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_outline.py — 历史短视频大纲质检硬闸门

用法:
    python3 check_outline.py 大纲.md [--events 事件卡.txt] [--minutes 20] [--no-fail]

判定级别:
    FAIL → 不过闸, 退出码 1 (除非 --no-fail), 修完复检
    WARN → 退出码 0, 但须在交付说明中列出未处理项及理由

卡面格式约定见 references/card-spec.md。
"""

import argparse
import re
import sys

# ---------------------------------------------------------------- 常量

CARD_HEADER = re.compile(r"【段级施工卡】\s*S-(\d+)\s*｜\s*模块归属\s*[:：]\s*([①②③④⑤⑥])")
MASTER_HEADER = re.compile(r"【篇级总卡】")
FIELD_LINE = re.compile(r"^([一-鿿A-Za-z/]{2,8})\s*[：:]\s*(.*)$")
FENCE = re.compile(r"^─{3,}")

# 段级卡必填字段(字段必须存在且非空; 弹药/史料等清单允许填"空")
REQUIRED_FIELDS = [
    "段意", "功能类型", "时间码", "使用史料卡", "节点分级", "指定技法",
    "因果接口", "弹药清单", "史料清单", "歇后语清单", "相似事件",
    "炸点", "伏笔", "情绪坐标", "预计字数", "备注",
]

TECH_TOKENS = ["心理代入", "词汇降维", "场景重构", "反讽", "设问", "史料引用"]
GRADE_TOKENS = {"强化", "关键", "过渡", "—", "-"}
FUNC_TOKENS = {"钩子", "锚定", "主线节点", "插件", "高潮", "收束", "衔接"}
BOOM_LAYERS = ["语言", "结构", "情绪"]

TIMECODE = re.compile(r"(\d+)\s*[:：]\s*(\d+)\s*[–—-]\s*(\d+)\s*[:：]\s*(\d+)")


# ---------------------------------------------------------------- 解析

class Card:
    def __init__(self, num, module, line_no):
        self.num = num            # S-编号(整数)
        self.module = module      # 模块归属 ①~⑥
        self.line_no = line_no
        self.fields = {}          # 字段名 -> 值(多行拼接)

    def get(self, name, default=""):
        return self.fields.get(name, default).strip()


def parse_outline(text):
    """解析大纲, 返回 (master_fields, cards, errors)。"""
    master_fields, cards = {}, []
    current_fields = None
    last_field = None
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if FENCE.match(line) or not line:
            continue
        m = CARD_HEADER.search(line)
        if m:
            card = Card(int(m.group(1)), m.group(2), i)
            cards.append(card)
            current_fields = card.fields
            last_field = None
            continue
        if MASTER_HEADER.search(line):
            current_fields = master_fields
            last_field = None
            continue
        if current_fields is None:
            continue
        fm = FIELD_LINE.match(line)
        # 表格行、伏笔续行等拼到上一字段
        if fm and fm.group(1) in _all_field_names():
            current_fields[fm.group(1)] = fm.group(2).strip()
            last_field = fm.group(1)
        elif last_field and (line.startswith("|") or line.startswith("F-") or
                             re.match(r"^[｜/、]", line) or not FIELD_LINE.match(line)):
            current_fields[last_field] += " " + line
    return master_fields, cards


_ALL_FIELDS = None

def _all_field_names():
    global _ALL_FIELDS
    if _ALL_FIELDS is None:
        _ALL_FIELDS = set(REQUIRED_FIELDS) | {
            "题目/集名", "叙事路由", "目标时长", "主线因果链", "开头前置",
            "结尾呼应", "声音素材", "伏笔总台账", "炸点总表", "情绪地图",
            "弹药总表", "字数预算表", "自补清单", "模块归属",
        }
    return _ALL_FIELDS


class Report:
    def __init__(self):
        self.items = []

    def fail(self, check, msg):
        self.items.append(("FAIL", check, msg))

    def warn(self, check, msg):
        self.items.append(("WARN", check, msg))

    def passed(self, check):
        self.items.append(("PASS", check, ""))

    @property
    def fail_count(self):
        return sum(1 for lv, _, _ in self.items if lv == "FAIL")

    @property
    def warn_count(self):
        return sum(1 for lv, _, _ in self.items if lv == "WARN")


# ---------------------------------------------------------------- 检查项

def check_card_fields(cards, report):
    """卡面必填字段完整: FAIL 级。"""
    bad = []
    for c in cards:
        missing = [f for f in REQUIRED_FIELDS
                   if f not in c.fields or not c.fields[f].strip()]
        if missing:
            bad.append(f"S-{c.num:03d} 缺: {'/'.join(missing)}")
    if bad:
        report.fail("卡面完整", "; ".join(bad))
    else:
        report.passed("卡面完整")


def check_sequence(cards, report):
    """段号连续无重号: FAIL 级。"""
    nums = [c.num for c in cards]
    dup = sorted({n for n in nums if nums.count(n) > 1})
    expected = list(range(1, len(cards) + 1))
    gaps = sorted(set(expected) - set(nums))
    msgs = []
    if dup:
        msgs.append(f"重号: {dup}")
    if gaps:
        msgs.append(f"缺号: {gaps}")
    if msgs:
        report.fail("段号连续", "; ".join(msgs))
    else:
        report.passed("段号连续")


def check_modules(cards, report):
    """六模块齐全: ①~⑤ 缺失 FAIL, ⑥ 缺失 WARN。"""
    have = {c.module for c in cards}
    missing_core = [m for m in "①②③④⑤" if m not in have]
    if missing_core:
        report.fail("六模块", f"缺失核心模块: {' '.join(missing_core)}")
    elif "⑥" not in have:
        report.warn("六模块", "缺失 ⑥尾声预告模块 —— 单集可省，系列篇建议保留")
    else:
        report.passed("六模块")


def check_foreshadow(cards, report):
    """伏笔闭合: 埋设必有回收且回收在后: FAIL 级。"""
    plants, payoffs = {}, {}
    for c in cards:
        for kind, fid in re.findall(r"(埋设|回收)\s*F-(\d+)", c.get("伏笔")):
            (plants if kind == "埋设" else payoffs).setdefault(fid, []).append(c.num)
    problems = []
    for fid, segs in plants.items():
        if len(segs) > 1:
            problems.append(f"F-{fid} 重复埋设于 {[f'S-{s:03d}' for s in segs]}")
        if fid not in payoffs:
            problems.append(f"F-{fid} 埋设于 S-{segs[0]:03d} 但无回收")
        elif min(payoffs[fid]) <= segs[0]:
            problems.append(f"F-{fid} 回收段 S-{min(payoffs[fid]):03d} 不在埋设段 S-{segs[0]:03d} 之后")
    orphan = [f"F-{f}" for f in payoffs if f not in plants]
    if orphan:
        problems.append(f"回收无埋设: {orphan}")
    if problems:
        report.fail("伏笔闭合", "; ".join(problems))
    else:
        report.passed("伏笔闭合")


def check_grading(cards, report):
    """节点分级配额: 强化3-5, 过渡≤1/3: WARN 级。"""
    graded = [c for c in cards if c.get("节点分级") in {"强化", "关键", "过渡"}]
    if not graded:
        report.warn("分级配额", "无任何节点分级(强化/关键/过渡)")
        return
    strong = sum(1 for c in graded if c.get("节点分级") == "强化")
    transit = sum(1 for c in graded if c.get("节点分级") == "过渡")
    msgs = []
    if not 3 <= strong <= 5:
        msgs.append(f"强化节点 {strong} 个(应为 3–5)")
    if transit > len(graded) / 3:
        msgs.append(f"过渡节点 {transit}/{len(graded)} 超 1/3")
    if msgs:
        report.warn("分级配额", "; ".join(msgs))
    else:
        report.passed("分级配额")


def check_word_budget(cards, minutes, report):
    """字数预算: WARN 级。"""
    total, bad = 0, []
    for c in cards:
        m = re.search(r"(\d+)", c.get("预计字数"))
        if m:
            total += int(m.group(1))
        else:
            bad.append(f"S-{c.num:03d}")
    if bad:
        report.warn("字数预算", f"以下卡预计字数无法解析: {bad}")
        return
    if minutes:
        target = minutes * 270
        lo, hi = int(target * 0.9), int(target * 1.1)
        if not lo <= total <= hi:
            report.warn("字数预算", f"合计 {total} 字, 目标 {minutes}分钟×270={target} 字(±10%: {lo}–{hi})")
        else:
            report.passed("字数预算")
    else:
        report.passed("字数预算")
        report.items[-1] = ("PASS", "字数预算", f"合计 {total} 字(未指定 --minutes, 未做时长核对)")


def check_boom_rotation(cards, report):
    """炸点相邻不同型 + 钩子段唯一: WARN 级。"""
    boom_cards = [(c.num, layer) for c in cards
                  for layer in BOOM_LAYERS
                  if c.get("炸点") and c.get("炸点") != "无" and layer in c.get("炸点")]
    problems = []
    for (n1, l1), (n2, l2) in zip(boom_cards, boom_cards[1:]):
        if l1 == l2:
            problems.append(f"S-{n1:03d} 与 S-{n2:03d} 同为{l1}层炸点")
    hooks = [c.num for c in cards if c.get("功能类型") == "钩子"]
    if len(hooks) > 1:
        problems.append(f"功能类型=钩子 的段有 {len(hooks)} 个(主钩子应唯一)")
    if problems:
        report.warn("炸点轮换", "; ".join(problems))
    else:
        report.passed("炸点轮换")


def check_dialect_quota(cards, report):
    """方言全篇 ≤3 处: WARN 级。"""
    dialect = [c.num for c in cards if "方言" in c.get("弹药清单")]
    if len(dialect) > 3:
        report.warn("方言额度", f"含方言弹药的段 {len(dialect)} 个(上限 3): {[f'S-{n:03d}' for n in dialect]}")
    else:
        report.passed("方言额度")


def check_event_refs(cards, events_text, report):
    """事件卡引用有效: FAIL 级(仅在提供 --events 时)。"""
    valid = set(re.findall(r"C-\d+", events_text))
    refs = set()
    for c in cards:
        refs.update(re.findall(r"C-\d+", c.get("使用史料卡")))
    dangling = sorted(r for r in refs if r != "C-—" and r not in valid)
    if dangling:
        report.fail("事件卡引用", f"引用了事件卡列表中不存在的卡号: {dangling}")
    else:
        report.passed("事件卡引用")


def check_elegy_cards(cards, report):
    """悲悯段技法与弹药合规: FAIL 级。"""
    problems = []
    for c in cards:
        if "悲悯" not in c.get("情绪坐标"):
            continue
        techs = [t for t in TECH_TOKENS if t in c.get("指定技法")]
        if techs != ["史料引用"]:
            problems.append(f"S-{c.num:03d} 悲悯段技法={techs}(只许[史料引用])")
        ammo = c.get("弹药清单")
        if ammo and ammo not in {"空", "—", "无"}:
            problems.append(f"S-{c.num:03d} 悲悯段弹药清单非空")
    if problems:
        report.fail("悲悯段合规", "; ".join(problems))
    else:
        report.passed("悲悯段合规")


def check_causal_links(cards, report):
    """因果接口成链: FAIL 级(dangling) + WARN 级(首尾规范)。"""
    nums = {c.num for c in cards}
    problems, warns = [], []
    for c in cards:
        link = c.get("因果接口")
        if not link:
            continue  # 卡面完整检查已覆盖缺失
        refs = re.findall(r"S-(\d+)", link)
        for r in refs:
            if int(r) not in nums:
                problems.append(f"S-{c.num:03d} 因果接口指向不存在的 S-{int(r):03d}")
        if not refs and "—" not in link and "-" not in link:
            warns.append(f"S-{c.num:03d} 因果接口未见任何指向")
        if c.module == "①" and re.search(r"因\s*←\s*S-", link):
            warns.append(f"S-{c.num:03d} 为①钩子段, 之因应填 —")
        if c.module == "⑥" and re.search(r"果\s*→\s*S-", link):
            warns.append(f"S-{c.num:03d} 为⑥尾声段, 之果应填 —（下集）")
    if problems:
        msg = "; ".join(problems)
        if warns:
            msg += " ｜ 另需修正: " + "; ".join(warns)
        report.fail("因果接口", msg)
    elif warns:
        report.warn("因果接口", "; ".join(warns))
    else:
        report.passed("因果接口")


def check_timecodes(cards, report):
    """时间码格式与单调性: WARN 级。"""
    prev_end, problems = -1, []
    for c in cards:
        m = TIMECODE.search(c.get("时间码"))
        if not m:
            problems.append(f"S-{c.num:03d} 时间码格式无法解析: {c.get('时间码')!r}")
            continue
        start = int(m.group(1)) * 60 + int(m.group(2))
        end = int(m.group(3)) * 60 + int(m.group(4))
        if end <= start:
            problems.append(f"S-{c.num:03d} 时间码结束早于开始")
        if prev_end >= 0 and start < prev_end - 1:
            problems.append(f"S-{c.num:03d} 时间码与上一段重叠/倒退")
        prev_end = end
    if problems:
        report.warn("时间码", "; ".join(problems))
    else:
        report.passed("时间码")


def check_master_card(master_fields, report):
    """篇级总卡存在且关键字段非空: WARN 级。"""
    if not master_fields:
        report.warn("篇级总卡", "未检出【篇级总卡】——写作节点阶段一将缺少全局上下文")
        return
    key = ["叙事路由", "主线因果链", "伏笔总台账", "字数预算表"]
    missing = [f for f in key if not master_fields.get(f, "").strip()]
    if missing:
        report.warn("篇级总卡", f"篇级总卡关键字段为空: {'/'.join(missing)}")
    else:
        report.passed("篇级总卡")


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="历史短视频大纲质检硬闸门")
    ap.add_argument("file", help="大纲 md/txt 路径")
    ap.add_argument("--events", help="事件卡列表文件(启用事件卡引用有效性检查)")
    ap.add_argument("--minutes", type=int, help="目标时长(分钟, 启用字数预算核对)")
    ap.add_argument("--no-fail", action="store_true", help="只看报告, 不因 FAIL 退出")
    args = ap.parse_args()

    try:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"无法读取大纲文件: {e}", file=sys.stderr)
        sys.exit(2)

    events_text = None
    if args.events:
        try:
            with open(args.events, encoding="utf-8") as f:
                events_text = f.read()
        except OSError as e:
            print(f"无法读取事件卡文件: {e}", file=sys.stderr)
            sys.exit(2)

    master_fields, cards = parse_outline(text)
    report = Report()

    if not cards:
        print("❌ 未解析到任何【段级施工卡】——请检查卡面格式(见 references/card-spec.md)")
        sys.exit(1)

    check_card_fields(cards, report)                 # FAIL
    check_sequence(cards, report)                    # FAIL
    check_modules(cards, report)                     # FAIL/WARN
    check_foreshadow(cards, report)                  # FAIL
    check_grading(cards, report)                     # WARN
    check_word_budget(cards, args.minutes, report)   # WARN
    check_boom_rotation(cards, report)               # WARN
    check_dialect_quota(cards, report)               # WARN
    if events_text is not None:
        check_event_refs(cards, events_text, report)  # FAIL
    check_elegy_cards(cards, report)                 # FAIL
    check_causal_links(cards, report)                # FAIL/WARN
    check_timecodes(cards, report)                   # WARN
    check_master_card(master_fields, report)         # WARN

    icons = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}
    width = max(len(c) for _, c, _ in report.items)
    print("=" * 64)
    print(f"大纲质检报告: {args.file}")
    print(f"段级施工卡: {len(cards)} 张 | 篇级总卡: {'有' if master_fields else '无'}")
    print("=" * 64)
    for lv, check, msg in report.items:
        print(f"{icons[lv]} [{lv:<4}] {check.ljust(width)}" + (f"  {msg}" if msg else ""))
    print("-" * 64)
    n_pass = len(report.items) - report.fail_count - report.warn_count
    print(f"FAIL {report.fail_count} 项 | WARN {report.warn_count} 项 | PASS {n_pass} 项")

    if report.fail_count:
        print("判定: ❌ 不过闸 —— 修完对应项后复检")
        if not args.no_fail:
            sys.exit(1)
    elif report.warn_count:
        print("判定: ⚠️ 过闸但有 WARN —— 交付说明中须列出未处理项及理由")
    else:
        print("判定: ✅ 全绿过闸, 大纲包可交付写作节点")
    sys.exit(0)


if __name__ == "__main__":
    main()
