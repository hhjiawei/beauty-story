#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_outline.py —— 历史旁白大纲（段落表制）质检硬闸门

用法:
    python3 check_outline.py 大纲.md [--cards 素材卡.json] [--minutes 20] [--no-fail]

判定级别:
    FAIL → 不过闸, 退出码 1(除非 --no-fail), 修完复检
    WARN → 退出码 0, 但须在交付说明中列出未处理项及理由

大纲格式见 assets/outline-template.md(段落表制: 篇级总表＋段落表＋卡片消费闭环表)。
"""

import argparse
import json
import re
import sys

# ---------------------------------------------------------------- 常量

PHASES = ("起", "承", "转", "合")
LEAD_KINDS = ("问答", "因果", "递进", "镜头", "时间")
REL_TOKENS = ("因果", "条件", "潜在", "递进", "并列", "反差", "对照", "演化",
              "镜像", "伏应", "归属", "咬合", "缺口", "悬念", "象征", "映射")
EMO_TOKENS = ("戏谑", "悲悯", "热血")
CARD_REF = re.compile(r"(?<![A-Za-z])[CPRBDE]-\d+")
MASTER_HEADER = re.compile(r"【篇级总卡】")
MASTER_REQUIRED = ["一句话主线", "核心矛盾", "转形态", "起形态", "四相位任务", "时长与字数"]
FIELD_LINE = re.compile(r"^([一-鿿A-Za-z/]{2,6})\s*[：:]\s*(.+)$")
FENCE = re.compile(r"^─{3,}")
SEP_CELL = re.compile(r":?-{2,}:?")

# 段落表列序: 段号/相位/段意/关系类型/挂卡/情绪坐标/引出方式/段尾欠条/预计字数/备注
(COL_NUM, COL_PHASE, COL_GIST, COL_REL, COL_CARDS, COL_EMO,
 COL_LEAD, COL_IOU, COL_WORDS, COL_NOTE) = range(10)
N_COLS = 10


# ---------------------------------------------------------------- 解析

def parse_master(text):
    """解析篇级总卡字段（──── 包围块）。"""
    fields, in_master = {}, False
    for raw in text.splitlines():
        s = raw.strip()
        if MASTER_HEADER.search(s):
            in_master = True
            continue
        if not in_master:
            continue
        if FENCE.match(s):
            if fields:
                break  # 第二道栅栏, 总卡块结束
            continue
        m = FIELD_LINE.match(s)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return fields


def parse_tables(text, heading_kw):
    """提取指定小节(## 标题含 heading_kw)下的表格数据行(已去表头与分隔行)。"""
    rows, in_section = [], False
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("#"):
            in_section = (heading_kw in s)
            continue
        if in_section and s.startswith("|"):
            cells = [c.strip() for c in s.strip().strip("|").split("|")]
            if cells and all(SEP_CELL.fullmatch(c) for c in cells if c):
                continue  # 分隔行
            rows.append(cells)
    return rows


def load_card_ids(path):
    """读取素材卡文件: JSON 数组取'卡号'字段, 否则按文本正则。"""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        print(f"无法读取素材卡文件: {e}", file=sys.stderr)
        sys.exit(2)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return set(CARD_REF.findall(content))
    ids = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "卡号" and isinstance(v, str):
                    ids.add(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return ids or set(CARD_REF.findall(content))


class Report:
    def __init__(self):
        self.items = []

    def fail(self, check, msg):
        self.items.append(("FAIL", check, msg))

    def warn(self, check, msg):
        self.items.append(("WARN", check, msg))

    def passed(self, check, msg=""):
        self.items.append(("PASS", check, msg))

    @property
    def fail_count(self):
        return sum(1 for lv, _, _ in self.items if lv == "FAIL")

    @property
    def warn_count(self):
        return sum(1 for lv, _, _ in self.items if lv == "WARN")


# ---------------------------------------------------------------- 检查项

def check_master(master, report):
    """篇级总卡存在且关键字段非空: 存在性 FAIL, 字段缺失 WARN。"""
    if not master:
        report.fail("篇级总卡", "未检出【篇级总卡】")
        return
    missing = [f for f in MASTER_REQUIRED if not master.get(f, "").strip()]
    if missing:
        report.warn("篇级总卡", f"关键字段为空或缺失: {'/'.join(missing)}")
    else:
        report.passed("篇级总卡")


def check_rows(rows, report):
    """段落表行结构完整、相位齐备且分区连续: FAIL 级。"""
    problems = []
    for i, cells in enumerate(rows, 1):
        if len(cells) < N_COLS:
            problems.append(f"第{i}行仅 {len(cells)} 列(应 {N_COLS} 列)")
            continue
        if not re.search(r"\d+", cells[COL_NUM]):
            problems.append(f"第{i}行段号无法解析: {cells[COL_NUM]!r}")
        if not (cells[COL_PHASE] and cells[COL_PHASE][0] in PHASES):
            problems.append(f"第{i}行相位无法解析: {cells[COL_PHASE]!r}")
        for name, idx in (("段意", COL_GIST), ("关系类型", COL_REL), ("挂卡", COL_CARDS),
                          ("情绪坐标", COL_EMO), ("引出方式", COL_LEAD),
                          ("段尾欠条", COL_IOU), ("预计字数", COL_WORDS)):
            if not cells[idx]:
                problems.append(f"第{i}行[{name}]为空")
    if problems:
        report.fail("表格结构", "; ".join(problems))
    else:
        report.passed("表格结构")


def check_sequence(rows, report):
    """段号从 1 连续递增: FAIL 级。"""
    nums = [int(re.search(r"\d+", c[COL_NUM]).group()) for c in rows if re.search(r"\d+", c[COL_NUM])]
    msgs = []
    if nums != list(range(1, len(nums) + 1)):
        if len(nums) != len(set(nums)):
            msgs.append("存在重号")
        msgs.append(f"段号序列非 1..{len(nums)} 连续: {nums}")
    if msgs:
        report.fail("段号连续", "; ".join(msgs))
    else:
        report.passed("段号连续")


def check_phase_blocks(rows, report):
    """起承转合齐备且各自连续成块(不交错): FAIL 级。"""
    seq = [c[COL_PHASE][0] for c in rows if c[COL_PHASE] and c[COL_PHASE][0] in PHASES]
    compressed = [p for i, p in enumerate(seq) if i == 0 or seq[i - 1] != p]
    missing = [p for p in PHASES if p not in seq]
    if missing:
        report.fail("相位齐备", f"缺失相位: {'/'.join(missing)}")
    elif compressed != list(PHASES):
        report.fail("相位齐备", f"相位交错或顺序错误: {'→'.join(compressed)}(应 起→承→转→合 各成一块)")
    else:
        report.passed("相位齐备")


def check_relations(rows, report):
    """关系类型取值合法(含十一型任一关键词): FAIL 级。"""
    bad = []
    for i, c in enumerate(rows, 1):
        if len(c) >= N_COLS and c[COL_REL] and not any(t in c[COL_REL] for t in REL_TOKENS):
            bad.append(f"第{i}行: {c[COL_REL]!r}")
    if bad:
        report.fail("关系类型", "; ".join(bad))
    else:
        report.passed("关系类型")


def check_emotions(rows, report):
    """情绪坐标: 逐段必含三轨之一(FAIL); 标【悲悯】的段登记为悲悯禁区。"""
    problems, pity_segs = [], []
    for i, c in enumerate(rows, 1):
        if len(c) < N_COLS:
            continue
        emo = c[COL_EMO]
        if emo and not any(t in emo for t in EMO_TOKENS):
            problems.append(f"段{i:02d}: {emo!r} 未含 戏谑/悲悯/热血")
        if "悲悯" in emo:
            pity_segs.append(f"段{i:02d}")
    if problems:
        report.fail("情绪坐标", "; ".join(problems))
    elif pity_segs:
        report.passed("情绪坐标", f"悲悯禁区段: {'/'.join(pity_segs)}")
    else:
        report.passed("情绪坐标")


def check_leads(rows, report):
    """引出方式: 非首段必含五种之一(FAIL); 相位块首段应为镜头/问答(WARN)。"""
    problems, warns = [], []
    for i, c in enumerate(rows):
        if len(c) < N_COLS or not c[COL_LEAD]:
            continue  # 结构检查已覆盖
        if i == 0:
            if "—" not in c[COL_LEAD] and "全篇起点" not in c[COL_LEAD]:
                warns.append(f"首段引出方式应为 —（全篇起点）: {c[COL_LEAD]!r}")
            continue
        if not any(k in c[COL_LEAD] for k in LEAD_KINDS):
            problems.append(f"段{i:02d} 引出方式未含{'/'.join(LEAD_KINDS)}: {c[COL_LEAD]!r}")
    # 相位块首段(非全篇首段)的引出方式应为镜头式/问答式
    for i, c in enumerate(rows):
        if len(c) < N_COLS or i == 0:
            continue
        prev = rows[i - 1]
        if len(prev) >= N_COLS and prev[COL_PHASE] and c[COL_PHASE]:
            if prev[COL_PHASE][0] != c[COL_PHASE][0]:
                if not ("镜头" in c[COL_LEAD] or "问答" in c[COL_LEAD]):
                    warns.append(f"段{i + 1:02d} 为{c[COL_PHASE][0]}相位首段, 引出方式宜为镜头式/问答式")
    if problems:
        report.fail("引出方式", "; ".join(problems))
    elif warns:
        report.warn("引出方式", "; ".join(warns))
    else:
        report.passed("引出方式")


def check_iou_chain(rows, report):
    """段尾欠条: 全段非空(结构检查覆盖), 末段须为跨篇欠条: WARN。"""
    if rows and len(rows[-1]) >= N_COLS:
        last = rows[-1][COL_IOU]
        if "跨篇" not in last and "钩" not in last:
            report.warn("欠条链", f"末段段尾欠条应为跨篇欠条(钩): {last!r}")
        else:
            report.passed("欠条链")
    else:
        report.warn("欠条链", "无法定位末段")


def check_card_refs(rows, report):
    """挂卡列须含至少一个卡号(铁律: 没有无卡之段): FAIL。"""
    bad = []
    for i, c in enumerate(rows, 1):
        if len(c) >= N_COLS and c[COL_CARDS] and not CARD_REF.search(c[COL_CARDS]):
            bad.append(f"段{i:02d}: {c[COL_CARDS]!r}")
    if bad:
        report.fail("挂卡有效", "; ".join(bad))
    else:
        report.passed("挂卡有效")


def check_closure(rows, closed_rows, report):
    """卡片消费闭环: 挂卡全部入闭环表(FAIL); 封存须有理由(WARN); 重号(WARN)。"""
    refed = set()
    for c in rows:
        if len(c) >= N_COLS:
            refed.update(CARD_REF.findall(c[COL_CARDS]))
    closed, problems, warns = {}, [], []
    for i, c in enumerate(closed_rows, 1):
        if len(c) < 4 or not c[0]:
            problems.append(f"闭环表第{i}行格式不完整")
            continue
        cid = CARD_REF.findall(c[0])
        if not cid:
            problems.append(f"闭环表第{i}行卡号无法解析: {c[0]!r}")
            continue
        cid = cid[0]
        if cid in closed:
            warns.append(f"{cid} 在闭环表中重复")
        closed[cid] = c
    missing = sorted(refed - set(closed))
    if missing:
        problems.append(f"段落表挂卡未入闭环表: {missing}")
    for cid, c in closed.items():
        if "封存" in c[2] and not c[3].strip():
            warns.append(f"{cid} 封存但用途/理由为空")
    if problems:
        report.fail("卡片闭环", "; ".join(problems))
    elif warns:
        report.warn("卡片闭环", "; ".join(warns))
    else:
        report.passed("卡片闭环", f"闭环 {len(closed)} 张, 挂卡 {len(refed)} 张全覆盖")


def check_card_source(rows, closed_rows, valid_ids, report):
    """引用卡号须存在于素材卡列表(仅在提供 --cards 时): FAIL。"""
    refed = set()
    for c in rows:
        if len(c) >= N_COLS:
            refed.update(CARD_REF.findall(c[COL_CARDS]))
    for c in closed_rows:
        if c and CARD_REF.findall(c[0]):
            refed.add(CARD_REF.findall(c[0])[0])
    dangling = sorted(r for r in refed if r not in valid_ids)
    if dangling:
        report.fail("卡号有效", f"引用了素材卡列表中不存在的卡号: {dangling}")
    else:
        report.passed("卡号有效")


def check_words(rows, minutes, report):
    """字数预算: 解析 FAIL, 合计±10% WARN。"""
    total, bad = 0, []
    for i, c in enumerate(rows, 1):
        if len(c) < N_COLS:
            continue
        m = re.search(r"\d+", c[COL_WORDS])
        if m:
            total += int(m.group())
        else:
            bad.append(f"段{i:02d}")
    if bad:
        report.fail("字数预算", f"以下段预计字数无法解析: {bad}")
        return
    if minutes:
        target = minutes * 270
        lo, hi = int(target * 0.9), int(target * 1.1)
        if not lo <= total <= hi:
            report.warn("字数预算", f"合计 {total} 字, 目标 {minutes}分钟×270={target} 字(±10%: {lo}–{hi})")
        else:
            report.passed("字数预算", f"合计 {total} 字")
    else:
        report.passed("字数预算", f"合计 {total} 字(未指定 --minutes, 未做时长核对)")


def check_para_count(rows, report):
    """段数 sanity: WARN。"""
    n = len(rows)
    if n < 4 or n > 24:
        report.warn("段数", f"全篇 {n} 段(常见 6–16 段/20 分钟, 4–24 为硬边界)")
    else:
        report.passed("段数", f"全篇 {n} 段")


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="历史旁白大纲(段落表制)质检硬闸门")
    ap.add_argument("file", help="大纲 md/txt 路径")
    ap.add_argument("--cards", help="素材卡 JSON 文件(启用卡号有效性检查)")
    ap.add_argument("--minutes", type=int, help="目标时长(分钟, 启用字数预算核对)")
    ap.add_argument("--no-fail", action="store_true", help="只看报告, 不因 FAIL 退出")
    args = ap.parse_args()

    try:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"无法读取大纲文件: {e}", file=sys.stderr)
        sys.exit(2)

    valid_ids = set()
    if args.cards:
        valid_ids = load_card_ids(args.cards)
        if not valid_ids:
            print("警告: 素材卡文件中未解析到任何卡号", file=sys.stderr)

    master = parse_master(text)
    rows = [r for r in parse_tables(text, "段落表") if r and r[0] != "段号"]
    closed_rows = [r for r in parse_tables(text, "闭环表") if r and r[0] != "卡号"]
    report = Report()

    if not rows:
        print("❌ 未在「段落表」小节解析到任何表格行——请检查格式(见 assets/outline-template.md)")
        sys.exit(1)

    check_master(master, report)                      # FAIL/WARN
    check_rows(rows, report)                          # FAIL
    check_sequence(rows, report)                      # FAIL
    check_phase_blocks(rows, report)                  # FAIL
    check_relations(rows, report)                     # FAIL
    check_emotions(rows, report)                      # FAIL
    check_leads(rows, report)                         # FAIL/WARN
    check_iou_chain(rows, report)                     # WARN
    check_card_refs(rows, report)                     # FAIL
    check_closure(rows, closed_rows, report)          # FAIL/WARN
    if valid_ids:
        check_card_source(rows, closed_rows, valid_ids, report)  # FAIL
    check_words(rows, args.minutes, report)           # FAIL/WARN
    check_para_count(rows, report)                    # WARN

    icons = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}
    width = max(len(c) for _, c, _ in report.items)
    phases_seq = [c[COL_PHASE][0] for c in rows if len(c) > COL_PHASE and c[COL_PHASE]]
    dist = {p: phases_seq.count(p) for p in PHASES if p in phases_seq}
    print("=" * 64)
    print(f"大纲质检报告: {args.file}")
    print(f"段落: {len(rows)} 段 | 相位分布: {dist} | 篇级总卡: {'有' if master else '无'} | 闭环表: {len(closed_rows)} 行")
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
        print("判定: ✅ 全绿过闸, 大纲可交付写作节点")
    sys.exit(0)


if __name__ == "__main__":
    main()
