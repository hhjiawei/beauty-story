#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_output.py — 爆款历史旁白成稿质检硬闸门

用法:
    python3 check_output.py 成稿.txt [--outline 大纲.txt] [--no-fail]

判定级别:
    FAIL → 不过闸, 退出码 1 (除非 --no-fail), 回炉重写对应段后复检
    WARN → 退出码 0, 但须在交付说明中列出未处理项及理由

词表(AD_BLACKLIST / AI_CLICHE / AMMO_LEXICON / DISCLAIMERS)可直接编辑扩充:
新系列的绰号、新广告词、新弹药都应回写到这里, 让闸门越用越准。
"""

import argparse
import re
import sys

# ---------------------------------------------------------------- 可配置词表

# 广告黑名单: 带货口播残留(成稿必须剥离)
AD_BLACKLIST = [
    "电动牙刷", "护颈枕", "米诺地尔", "HFP", "果酸", "夸克",
    "萌牙家", "妙界", "望舒心", "拼多多", "淘宝", "京东", "旗舰店",
    "下单", "优惠券", "评论区链接", "橱窗", "小黄车", "甲方爸爸",
    "感谢赞助", "本视频由", "冠名播出",
]

# AI腔禁语: 书面腔/八股腔, 口播稿禁用
AI_CLICHE = [
    "值得注意的是", "综上所述", "总而言之", "由此可见一斑",
    "不禁让人", "毋庸置疑", "显而易见", "一言以蔽之", "总的来说",
    "值得一提", "发人深省", "引人深思",
]
AI_CLICHE_REGEX = [
    re.compile(r"在.{0,12}的背景下"),
    re.compile(r"随着.{0,12}的发展"),
]

# 弹药库: 分类黑话词表(用于密度检查与悲悯轨清零检查)
AMMO_LEXICON = {
    "职场": ["刷履历", "履历", "编制", "接班", "创业", "站队", "背锅",
             "KPI", "内推", "优化流程", "打工", "绩效", "离职", "入职",
             "人事安排", "职场"],
    "游戏": ["点亮", "最高成就", "培训班", "PK", "一波带走", "组团",
             "报销", "开挂", "副本", "装备", "血条", "buff"],
    "网络": ["赢麻了", "让子弹飞", "地狱笑话", "翻身把歌唱", "打包快递",
             "装犊子", "吃瓜", "破防", "塌房", "躺平", "内卷",
             "没惹你们任何人", "懂的都懂"],
    "影视": ["影帝", "演技", "表演归表演", "剧本", "导演", "杀青"],
    "绰号": ["老影帝", "老乌龟", "老狐狸", "曹老板", "好圣孙", "顶级丑女",
             "老板", "保安队长", "话事人"],
}

# 声明牌: 脑补/推测处必须悬挂
DISCLAIMERS = ["或许", "估计", "可以想象", "大概率", "以下为个人观点",
               "个人观点", "不排除", "存疑", "大约", "约莫", "推测"]

# 强推测句式: 出现且同句无声明牌 → WARN
SPECULATION = ["应该是", "很可能是", "想必", "一定是", "肯定是", "八成是"]

# 收束特征词(结尾300字内至少命中一个)
CLOSING_SIGNALS = ["下期", "下一期", "咱们准备", "总结", "拜拜", "预告",
                   "敬请期待", "且听下回"]

# 埋钩句式: 检出即列入人工兑现核对清单(盖了不掀=挖坑不填)
HOOK_PATTERNS = [
    "后面说", "后面讲", "后面慢慢", "后面再", "这个后面",
    "下期", "下一期", "且听下回", "先按下不表", "留了一手",
    "埋个伏笔", "记住这个", "记住这", "后面会讲", "咱们以后",
]

# 领属词: 我(大)+朝代字
POSSESSIVE_REGEX = re.compile(r"我大?[秦汉魏晋隋唐宋元明清周赵蜀吴燕]")

# 年号锚定: 两个汉字 + 元年/二年...二十九年, 且附近无"公元"
ERA_REGEX = re.compile(r"(?<![公元])[一-鿿]{2}(?:元年|[一二三四五六七八九]十[一二三四五六七八九]?年|[二三四五六七八九]年)")

# 段号标注: 【段N】或【段N·悲悯】
SEG_TAG_REGEX = re.compile(r"【段(\d+)(·悲悯)?】")

# 阈值
MAX_SENTENCE_CHARS = 120   # 单句超长流水句阈值
MAX_PARA_CHARS = 450       # 单段超长阈值
MAX_AMMO_PER_SEG = 2       # 单段弹药上限
CLOSING_WINDOW = 300       # 收束检查窗口(字)


# ---------------------------------------------------------------- 数据结构

class Report:
    def __init__(self):
        self.items = []  # (level, check, message)

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


# ---------------------------------------------------------------- 工具函数

def split_segments(text):
    """按空行切段, 返回 [(起始行号, 段文本)]。"""
    segs, buf, start = [], [], 1
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip():
            if not buf:
                start = i
            buf.append(line.strip())
        else:
            if buf:
                segs.append((start, "\n".join(buf)))
                buf = []
    if buf:
        segs.append((start, "\n".join(buf)))
    return segs


def split_sentences(text):
    """按句末标点切句。"""
    parts = re.split(r"(?<=[。！？…])", text)
    return [p.strip() for p in parts if p.strip()]


def ammo_hits(text, categories=None):
    """统计弹药命中, 返回 {类别: [(词, 次数)]}。"""
    hits = {}
    for cat, words in AMMO_LEXICON.items():
        if categories and cat not in categories:
            continue
        found = [(w, text.count(w)) for w in words if w in text]
        if found:
            hits[cat] = found
    return hits


def total_hits(hits):
    return sum(c for pairs in hits.values() for _, c in pairs)


# ---------------------------------------------------------------- 检查项

def check_seg_tags(text, outline_text, report):
    """段号覆盖: FAIL 级。"""
    tags = [(int(m.group(1)), bool(m.group(2))) for m in SEG_TAG_REGEX.finditer(text)]
    if not tags:
        report.fail("段号覆盖", "全文未检出任何【段N】标注 —— 不满足逐段对齐大纲的成稿规格")
        return
    nums = [n for n, _ in tags]
    dup = sorted({n for n in nums if nums.count(n) > 1})
    if dup:
        report.fail("段号覆盖", f"段号重复: {dup}")
    if outline_text:
        o_nums = set()
        for line in outline_text.splitlines():
            m = re.match(r"\s*(?:段\s*)?(\d+)[.、．:：\s]", line)
            if m:
                o_nums.add(int(m.group(1)))
        if o_nums:
            missing = sorted(o_nums - set(nums))
            extra = sorted(set(nums) - o_nums)
            if missing:
                report.fail("段号覆盖", f"大纲有而正文缺的段: {missing}")
            if extra:
                report.warn("段号覆盖", f"正文有而大纲未列的段: {extra}")
            if not missing and not extra and not dup:
                report.passed("段号覆盖")
            return
    if not dup:
        report.passed("段号覆盖")


def check_ads(text, report):
    """广告词残留: FAIL 级。"""
    found = [w for w in AD_BLACKLIST if w in text]
    if found:
        report.fail("广告残留", f"检出广告/带货词: {found} —— 口播噪声必须剥离")
    else:
        report.passed("广告残留")


def check_ai_cliche(text, report):
    """AI腔禁语: FAIL 级。"""
    found = [w for w in AI_CLICHE if w in text]
    for rx in AI_CLICHE_REGEX:
        found += [m.group(0) for m in rx.finditer(text)]
    if found:
        report.fail("AI腔禁语", f"检出书面八股腔: {sorted(set(found))}")
    else:
        report.passed("AI腔禁语")


def check_elegy_segments(text, report):
    """悲悯轨弹药清零: FAIL 级。"""
    bad = []
    for m in SEG_TAG_REGEX.finditer(text):
        if not m.group(2):
            continue
        seg_text = text[m.end():]
        nxt = SEG_TAG_REGEX.search(seg_text)
        if nxt:
            seg_text = seg_text[:nxt.start()]
        hits = ammo_hits(seg_text)
        if hits:
            detail = {c: [w for w, _ in p] for c, p in hits.items()}
            bad.append((m.group(1), detail))
    if bad:
        for n, detail in bad:
            report.fail("悲悯轨弹药", f"【段{n}·悲悯】内检出弹药/绰号: {detail} —— 悲悯轨必须清零")
    else:
        report.passed("悲悯轨弹药")


def check_disclaimers(text, report):
    """声明牌缺失: WARN 级(启发式, 人工复核)。"""
    issues = []
    for sent in split_sentences(text):
        if any(k in sent for k in SPECULATION):
            if not any(d in sent for d in DISCLAIMERS):
                issues.append(sent[:40] + ("…" if len(sent) > 40 else ""))
    if issues:
        report.warn("声明牌", f"{len(issues)} 处强推测句式未见声明牌(或许/估计/可以想象), 请人工复核: "
                    + " | ".join(issues[:5]))
    else:
        report.passed("声明牌")


def check_era_anchor(text, report):
    """时间锚定 年号+公元双标: WARN 级(启发式)。"""
    issues = []
    for m in ERA_REGEX.finditer(text):
        window = text[m.start():m.end() + 25]
        if "公元" not in window:
            issues.append(m.group(0))
    if issues:
        report.warn("时间锚定", f"{len(issues)} 处年号附近未见公元纪年(新时间点须年号+公元双标): "
                    + "、".join(sorted(set(issues))[:8]))
    else:
        report.passed("时间锚定")


def check_ammo_density(segs, report):
    """弹药密度: WARN 级。单段>上限 或 同类弹药连续两段。"""
    problems = []
    prev_cats = set()
    for line_no, seg in segs:
        body = SEG_TAG_REGEX.sub("", seg)
        hits = ammo_hits(body)
        n = total_hits(hits)
        cats = set(hits.keys())
        if n > MAX_AMMO_PER_SEG:
            problems.append(f"第{line_no}行段 弹药 {n} 处(上限 {MAX_AMMO_PER_SEG})")
        overlap = cats & prev_cats
        if overlap:
            problems.append(f"第{line_no}行段 与上一段连续使用同类弹药: {sorted(overlap)}")
        prev_cats = cats
    if problems:
        report.warn("弹药密度", "; ".join(problems[:6]))
    else:
        report.passed("弹药密度")


def check_ammo_repeat(text, report):
    """黑话重复: 同一弹药词全篇 >2 次 → WARN(绰号类豁免, 绰号本就要全篇统一)。"""
    repeated = []
    for cat, words in AMMO_LEXICON.items():
        if cat == "绰号":
            continue
        for w in words:
            n = text.count(w)
            if n > 2:
                repeated.append(f"{w}×{n}")
    if repeated:
        report.warn("黑话重复", f"以下弹药词全篇出现超 2 次, 请换说法避免脱敏: "
                    + "、".join(sorted(repeated)))
    else:
        report.passed("黑话重复")


def check_hook_ledger(text, report):
    """埋钩兑现提示: WARN 级(列出全部埋钩句, 人工逐条核对兑现位置)。"""
    PREVIEW_WORDS = {"下期", "下一期", "且听下回", "咱们以后"}
    hooks, previews = [], []
    for p in HOOK_PATTERNS:
        n = text.count(p)
        if not n:
            continue
        (previews if p in PREVIEW_WORDS else hooks).append(f"{p}×{n}")
    msgs = []
    if hooks:
        msgs.append("检出埋钩 " + "、".join(hooks) +
                    " —— 请对照钩子台账逐条核对兑现位置(盖了不掀=挖坑不填)")
    if previews:
        msgs.append("系列预告 " + "、".join(previews) + " —— 确认与下期选题一致即可")
    if msgs:
        report.warn("埋钩兑现", "; ".join(msgs))
    else:
        report.passed("埋钩兑现")


def check_runon(segs, report):
    """超长流水句/段: WARN 级。"""
    long_sents, long_paras = [], []
    for line_no, seg in segs:
        if len(seg) > MAX_PARA_CHARS:
            long_paras.append((line_no, len(seg)))
        for sent in split_sentences(seg):
            if len(sent) > MAX_SENTENCE_CHARS:
                long_sents.append((line_no, len(sent), sent[:30] + "…"))
    msgs = []
    if long_sents:
        msgs.append(f"{len(long_sents)} 句超 {MAX_SENTENCE_CHARS} 字: "
                    + " | ".join(f"第{l}行({n}字)“{p}”" for l, n, p in long_sents[:4]))
    if long_paras:
        msgs.append(f"{len(long_paras)} 段超 {MAX_PARA_CHARS} 字: "
                    + "、".join(f"第{l}行({n}字)" for l, n in long_paras[:4]))
    if msgs:
        report.warn("流水句", "; ".join(msgs))
    else:
        report.passed("流水句")


def check_possessive(text, report):
    """领属词一致性: WARN 级。"""
    found = sorted(set(POSSESSIVE_REGEX.findall(text) and
                       [m.group(0) for m in POSSESSIVE_REGEX.finditer(text)]))
    # 归一: 我大晋 → 我晋
    normalized = sorted({re.sub(r"^我大", "我", w) for w in found})
    if len(normalized) > 1:
        report.warn("领属词", f"检出多个领属词 {found} —— 全文应统一(以声音卡为准)")
    elif len(normalized) == 1:
        report.passed("领属词")
    else:
        report.warn("领属词", "未检出领属词(我X) —— 若非刻意省略, 请确认声音卡已落地")


def check_closing(text, report):
    """收束完整性: WARN 级。"""
    tail = text[-CLOSING_WINDOW:]
    hits = [w for w in CLOSING_SIGNALS if w in tail]
    if hits:
        report.passed("收束完整性")
    else:
        report.warn("收束完整性", f"结尾 {CLOSING_WINDOW} 字内未检出收束特征"
                    f"({'/'.join(CLOSING_SIGNALS[:6])}…) —— 收尾四件套至少命中两件")


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description="爆款历史旁白成稿质检硬闸门")
    ap.add_argument("file", help="成稿 txt 路径")
    ap.add_argument("--outline", help="大纲 txt 路径(启用段号覆盖交叉检查)")
    ap.add_argument("--no-fail", action="store_true", help="只看报告, 不因 FAIL 退出")
    args = ap.parse_args()

    try:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"无法读取成稿文件: {e}", file=sys.stderr)
        sys.exit(2)

    outline_text = None
    if args.outline:
        try:
            with open(args.outline, encoding="utf-8") as f:
                outline_text = f.read()
        except OSError as e:
            print(f"无法读取大纲文件: {e}", file=sys.stderr)
            sys.exit(2)

    segs = split_segments(text)
    report = Report()

    check_seg_tags(text, outline_text, report)      # FAIL
    check_ads(text, report)                          # FAIL
    check_ai_cliche(text, report)                    # FAIL
    check_elegy_segments(text, report)               # FAIL
    check_disclaimers(text, report)                  # WARN
    check_era_anchor(text, report)                   # WARN
    check_ammo_density(segs, report)                 # WARN
    check_ammo_repeat(text, report)                  # WARN
    check_hook_ledger(text, report)                  # WARN
    check_runon(segs, report)                        # WARN
    check_possessive(text, report)                   # WARN
    check_closing(text, report)                      # WARN

    # ---- 输出报告
    icons = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}
    width = max(len(c) for _, c, _ in report.items)
    print("=" * 64)
    print(f"成稿质检报告: {args.file}")
    chars = len(re.sub(r"\s", "", text))
    print(f"总字数(不计空白): {chars} | 段落数: {len(segs)}")
    print("=" * 64)
    for lv, check, msg in report.items:
        line = f"{icons[lv]} [{lv:<4}] {check.ljust(width)}"
        print(line + (f"  {msg}" if msg else ""))
    print("-" * 64)
    print(f"FAIL {report.fail_count} 项 | WARN {report.warn_count} 项 | "
          f"PASS {len(report.items) - report.fail_count - report.warn_count} 项")

    if report.fail_count:
        print("判定: ❌ 不过闸 —— 回炉重写对应段落后复检")
        if not args.no_fail:
            sys.exit(1)
    elif report.warn_count:
        print("判定: ⚠️ 过闸但有 WARN —— 交付说明中须列出未处理项及理由")
    else:
        print("判定: ✅ 全绿过闸, 可以交付")
    sys.exit(0)


if __name__ == "__main__":
    main()
