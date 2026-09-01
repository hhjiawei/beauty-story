#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_cards.py — 历史资料卡质检硬闸门

用法:
    python3 validate_cards.py cards.json [--no-fail] [--min-events 5]

判定级别:
    FAIL → 不过闸, 退出码 1 (除非 --no-fail), 修完复检
    WARN → 退出码 0, 但须在交付说明中列出未处理项及理由

字段规格见 references/schema.md, 拆卡纪律见 references/discipline.md。
"""

import argparse
import json
import re
import sys

# ---------------------------------------------------------------- 规格定义

# 卡型 ↔ 前缀 ↔ 必填字段
CARD_TYPES = {
    "事件": {"prefix": "C", "required": ["卡号", "卡型", "时间", "地点", "人物", "冲突", "史料出处", "可信度"]},
    "人物": {"prefix": "P", "required": ["卡号", "卡型", "人物名", "身份", "核心特质", "史料出处", "可信度"]},
    "关系": {"prefix": "R", "required": ["卡号", "卡型", "双方", "关系性质", "关键事件指向", "史料出处", "可信度"]},
    "背景": {"prefix": "B", "required": ["卡号", "卡型", "主题", "要点", "史料出处", "可信度"]},
    "数据": {"prefix": "D", "required": ["卡号", "卡型", "指标", "数值", "时间范围", "史料出处", "可信度"]},
    "彩蛋": {"prefix": "E", "required": ["卡号", "卡型", "类型", "内容", "史料出处", "可信度"]},
}

CREDIBILITY = {"正史", "诸子", "传说", "出土文献"}
NARRATIVE_ROLES = {"钩子", "锚定", "主线节点", "插件", "高潮", "收束", "衔接"}
RELATION_TYPES = {"恩怨", "同盟", "君臣", "血缘", "利益", "师徒"}
EASTER_TYPES = {"歇后语", "相似事件", "冷知识", "名言"}
USE_FLAGS = {"用", "备用", "不用"}

# 弹药潜质推荐词表(开放词表, 词表外仅 WARN)
AMMO_TAGS = {
    "钩子", "锚定", "转折", "情绪峰值", "侧写", "对照组", "拆账",
    "古文炸点", "心理推演", "因果缝合", "制度织入", "地图节点",
    "数据可视化", "蝴蝶效应", "环境氛围", "沙盘决策", "谜案证据",
    "造势", "博弈入场", "胜负手", "制度案例", "制度漏洞", "现代对照",
    "地理奠基", "地域演进", "战役沙盘", "意外变量", "士兵视角",
    "战后复盘", "节奏钩子", "节奏危机", "节奏高潮", "节奏留钩",
    "知识彩蛋", "收尾", "场景重构", "数字轰炸", "无",
}

CARD_ID = re.compile(r"^[CPRBDE]-\d{3,}$")
REF_ID = re.compile(r"[CPRBDE]-\d{3,}")


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

def check_type_and_fields(cards, report):
    """卡型合法 + 前缀匹配 + 必填字段: FAIL 级。"""
    problems = []
    for i, c in enumerate(cards, 1):
        cid = c.get("卡号", f"?{i}")
        ctype = c.get("卡型")
        if ctype not in CARD_TYPES:
            problems.append(f"{cid}: 卡型非法或未填(合法值: {'/'.join(CARD_TYPES)})")
            continue
        spec = CARD_TYPES[ctype]
        if not CARD_ID.match(str(cid)):
            problems.append(f"{cid}: 卡号格式错误(应如 {spec['prefix']}-001)")
        elif not cid.startswith(spec["prefix"]):
            problems.append(f"{cid}: 前缀与卡型「{ctype}」不符(应为 {spec['prefix']}-)")
        missing = [f for f in spec["required"]
                   if f not in c or c[f] is None or str(c[f]).strip() == ""]
        if missing:
            problems.append(f"{cid}: 缺必填字段 {'/'.join(missing)}")
    if problems:
        report.fail("卡型与必填", "; ".join(problems[:10]) +
                    (f" 等{len(problems)}处" if len(problems) > 10 else ""))
    else:
        report.passed("卡型与必填")


def check_unique_ids(cards, report):
    """卡号唯一: FAIL 级。"""
    seen, dup = {}, []
    for c in cards:
        cid = str(c.get("卡号", ""))
        if cid in seen:
            dup.append(cid)
        seen[cid] = True
    if dup:
        report.fail("卡号唯一", f"重复卡号: {sorted(set(dup))}")
    else:
        report.passed("卡号唯一")


def check_enums(cards, report):
    """枚举合法: 可信度 FAIL, 其余 WARN。"""
    cred_bad, other_bad = [], []
    for c in cards:
        cid = str(c.get("卡号", "?"))
        v = c.get("可信度", "")
        if v and v not in CREDIBILITY:
            cred_bad.append(f"{cid} 可信度={v!r}")
        for role in re.split(r"[/、]", str(c.get("叙事角色", ""))):
            if role.strip() and role.strip() not in NARRATIVE_ROLES:
                other_bad.append(f"{cid} 叙事角色={role.strip()!r}")
        for rel in re.split(r"[/、]", str(c.get("关系性质", ""))):
            if rel.strip() and rel.strip() not in RELATION_TYPES:
                other_bad.append(f"{cid} 关系性质={rel.strip()!r}")
        t = str(c.get("类型", ""))
        if c.get("卡型") == "彩蛋" and t and t not in EASTER_TYPES:
            other_bad.append(f"{cid} 彩蛋类型={t!r}")
        u = str(c.get("本集用不用", ""))
        if u and u not in USE_FLAGS:
            other_bad.append(f"{cid} 本集用不用={u!r}")
    if cred_bad:
        msg = "可信度非法: " + "; ".join(cred_bad[:6])
        if other_bad:
            msg += " ｜ 另需修正: " + "; ".join(other_bad[:8])
        report.fail("枚举合法", msg)
    elif other_bad:
        report.warn("枚举合法", "; ".join(other_bad[:8]))
    else:
        report.passed("枚举合法")


def check_conditional_fields(cards, report):
    """条件必填: 弹药潜质含'古文炸点'则古文原句必填(纪律3.3): FAIL 级。"""
    problems = []
    for c in cards:
        tags = str(c.get("弹药潜质", ""))
        if "古文炸点" in tags and not str(c.get("古文原句", "")).strip():
            problems.append(f"{c.get('卡号', '?')}: 标了古文炸点但古文原句为空(纪律3.3)")
    if problems:
        report.fail("古文原句", "; ".join(problems))
    else:
        report.passed("古文原句")


def check_references(cards, report):
    """关联引用有效: R→C、E→C、P→R: FAIL 级。"""
    ids = {str(c.get("卡号", "")) for c in cards}
    problems = []
    for c in cards:
        cid = str(c.get("卡号", "?"))
        for field in ("关键事件指向", "挂接事件", "关系指向"):
            for ref in REF_ID.findall(str(c.get(field, ""))):
                if ref not in ids:
                    problems.append(f"{cid}: {field} 引用不存在的 {ref}")
    if problems:
        report.fail("引用有效", "; ".join(problems[:8]))
    else:
        report.passed("引用有效")


def check_legend_restriction(cards, report):
    """传说限位(纪律3.7): 传说+高潮 FAIL, 传说+主线节点 WARN。"""
    fails, warns = [], []
    for c in cards:
        if c.get("可信度") != "传说":
            continue
        roles = set(re.split(r"[/、]", str(c.get("叙事角色", ""))))
        cid = str(c.get("卡号", "?"))
        if "高潮" in roles:
            fails.append(f"{cid}: 传说级材料禁止用于高潮(纪律3.7)")
        if "主线节点" in roles:
            warns.append(f"{cid}: 传说级材料不建议用于主线节点")
    if fails:
        report.fail("传说限位", "; ".join(fails))
    elif warns:
        report.warn("传说限位", "; ".join(warns))
    else:
        report.passed("传说限位")


def check_ammo_tags(cards, report):
    """弹药潜质开放词表提示 + 空值字段清理建议: WARN 级。"""
    unknown, empty_fields = [], []
    for c in cards:
        cid = str(c.get("卡号", "?"))
        for tag in re.split(r"[/、]", str(c.get("弹药潜质", ""))):
            tag = tag.strip()
            if tag and tag not in AMMO_TAGS:
                unknown.append(f"{cid} 弹药潜质={tag!r}")
        for k, v in c.items():
            if isinstance(v, str) and v.strip() in {"", "无", "—"} and k not in {"备注"}:
                empty_fields.append(f"{cid}.{k}")
    msgs = []
    if unknown:
        msgs.append("词表外标签(确认有意为之即可): " + "; ".join(unknown[:6]))
    if empty_fields:
        msgs.append("含空值字段(纪律3.10建议直接省略): " + "、".join(empty_fields[:8]))
    if msgs:
        report.warn("弹药与空值", " | ".join(msgs))
    else:
        report.passed("弹药与空值")


def check_event_count(cards, min_events, report):
    """主干事件卡数量: WARN 级。"""
    n = sum(1 for c in cards if c.get("卡型") == "事件")
    if n < min_events:
        report.warn("事件卡数量", f"事件卡 {n} 张 < 建议下限 {min_events} 张(大纲节点 N≥5 才能订纲)")
    else:
        report.passed("事件卡数量")


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="历史资料卡质检硬闸门")
    ap.add_argument("file", help="资料卡 JSON 路径")
    ap.add_argument("--min-events", type=int, default=5, help="事件卡建议下限(默认5)")
    ap.add_argument("--no-fail", action="store_true", help="只看报告, 不因 FAIL 退出")
    args = ap.parse_args()

    try:
        with open(args.file, encoding="utf-8") as f:
            cards = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"❌ 无法读取/解析 JSON: {e}", file=sys.stderr)
        sys.exit(2)

    if not isinstance(cards, list) or not cards:
        print("❌ 根对象必须是非空 JSON 数组", file=sys.stderr)
        sys.exit(2)
    for i, c in enumerate(cards, 1):
        if not isinstance(c, dict):
            print(f"❌ 第 {i} 个元素不是对象", file=sys.stderr)
            sys.exit(2)

    report = Report()
    check_type_and_fields(cards, report)      # FAIL
    check_unique_ids(cards, report)           # FAIL
    check_enums(cards, report)                # FAIL/WARN
    check_conditional_fields(cards, report)   # FAIL
    check_references(cards, report)           # FAIL
    check_legend_restriction(cards, report)   # FAIL/WARN
    check_ammo_tags(cards, report)            # WARN
    check_event_count(cards, args.min_events, report)  # WARN

    # ---- 统计
    by_type, by_cred = {}, {}
    for c in cards:
        by_type[c.get("卡型", "?")] = by_type.get(c.get("卡型", "?"), 0) + 1
        by_cred[c.get("可信度", "?")] = by_cred.get(c.get("可信度", "?"), 0) + 1

    icons = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}
    width = max(len(c) for _, c, _ in report.items)
    print("=" * 64)
    print(f"资料卡质检报告: {args.file}")
    print(f"卡数: {len(cards)} ｜ 卡型分布: {by_type} ｜ 可信度分布: {by_cred}")
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
        print("判定: ✅ 全绿过闸, 卡包可交付大纲节点")
    sys.exit(0)


if __name__ == "__main__":
    main()
