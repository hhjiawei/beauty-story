"""确定性扫描（执行方案 §4.6：程序化部分不进 LLM）。

一句话总结： 这就是个防AI废话、防生硬转场、并精确卡字数的自动巡检机器人，专门用来保证你的口播稿既“像人话”，又符合时长要求。
如果你的稿子被它扫出很多红叉，说明你写得太“机器人”了，得赶紧改成口语化表达。

- AI 腔禁词全文扫描（人格层禁忌清单词汇表）
- 过渡套话扫描（写作层 Step 4 禁用清单）
- 零信息量感慨扫描（人格层·嘴禁区）
- 字数容差检查（对照大纲预计字数，分级容差）
"""
from __future__ import annotations

import re

# 人格层禁忌清单 §4 + 写作层 §7.3
AI_FLAVOR_BANNED_WORDS = [
    "众所周知", "不得不说", "引人深思", "历史的洪流",
    "值得我们学习", "人性的复杂", "让我们把时间拨回",
]

# 写作层 Step 4 禁用过渡套话
TRANSITION_CLICHES = ["话说回来", "言归正传", "与此同时", "镜头来到"]

# 人格层·嘴：零信息量点评
ZERO_INFO_PHRASES = ["令人深思", "历史的尘埃", "人性的复杂", "不禁让人", "感慨万千"]


def _find_positions(text: str, needle: str) -> list[int]:
    return [m.start() for m in re.finditer(re.escape(needle), text)]


def scan_banned_words(script: str) -> list[dict]:
    """AI 腔禁词扫描，一个不留。"""
    hits = []
    for w in AI_FLAVOR_BANNED_WORDS:
        for pos in _find_positions(script, w):
            hits.append({"word": w, "position": pos, "context": script[max(0, pos - 15): pos + len(w) + 15]})
    return hits


def scan_transition_cliches(script: str) -> list[dict]:
    hits = []
    for w in TRANSITION_CLICHES:
        for pos in _find_positions(script, w):
            hits.append({"word": w, "position": pos, "context": script[max(0, pos - 15): pos + len(w) + 15]})
    return hits


def scan_zero_info(script: str) -> list[dict]:
    hits = []
    for w in ZERO_INFO_PHRASES:
        for pos in _find_positions(script, w):
            hits.append({"word": w, "position": pos, "context": script[max(0, pos - 15): pos + len(w) + 15]})
    return hits


def split_segments(script: str) -> dict[int, str]:
    """按成稿格式【段N·...】切分段落，返回 {段号: 段正文}。"""
    segs: dict[int, list[str]] = {}
    current = None
    for line in script.splitlines():
        m = re.match(r"^【段(\d+)", line.strip())
        if m:
            current = int(m.group(1))
            segs.setdefault(current, [])
        elif current is not None:
            segs[current].append(line)
    return {k: "\n".join(v).strip() for k, v in segs.items()}


def _tolerance_of(func_type: str) -> tuple[float | None, float | None]:
    """按功能类型返回 (下浮容差, 上浮容差)。过渡段不设下限只设上限。"""
    ft = func_type or ""
    if any(k in ft for k in ("钩子", "收尾")):
        return 0.4, 0.4
    if any(k in ft for k in ("主线", "插件", "高潮", "锚定")):
        return 0.2, 0.2
    return None, 0.4  # 过渡/衔接：不设下限，上限 40%


def _count_chars(text: str) -> int:
    """口播字数：剔除标记与空白后的汉字+字母数字计数。"""
    t = re.sub(r"【[^】]*】", "", text)
    t = re.sub(r"（[^）]*）", "", t)
    t = re.sub(r"\s", "", t)
    return len(t)


def check_word_count_tolerance(script: str, outline: list[dict]) -> list[dict]:
    """逐段核对字数容差（写作层 Step 3 字数查的代码层落实）。"""
    segs = split_segments(script)
    findings = []
    for seg in outline:
        no = seg.get("段号")
        if no not in segs:
            findings.append({"段号": no, "issue": "成稿缺段", "expected": seg.get("预计字数"), "actual": 0})
            continue
        planned_raw = str(seg.get("预计字数", ""))
        m = re.match(r"^(\d+)", planned_raw)
        if not m:
            continue
        planned = int(m.group(1))
        actual = _count_chars(segs[no])
        down, up = _tolerance_of(seg.get("功能类型", ""))
        lo = planned * (1 - down) if down is not None else 0
        hi = planned * (1 + (up if up is not None else 0.4))
        if actual < lo or actual > hi:
            findings.append({
                "段号": no, "issue": "字数超出容差",
                "expected": f"{planned}（{int(lo)}-{int(hi)}）", "actual": actual,
            })
    return findings


def run_all_scans(script: str, outline: list[dict]) -> dict:
    """汇总三门确定性扫描 + 字数容差，供 N5 输入与前端展示。"""
    return {
        "AI腔禁词": scan_banned_words(script),
        "过渡套话": scan_transition_cliches(script),
        "零信息量感慨": scan_zero_info(script),
        "字数容差": check_word_count_tolerance(script, outline),
    }


def has_hard_violations(scan_findings: dict) -> bool:
    """前三类扫描任一命中即硬伤（字数容差交给审核综合判罚）。"""
    return any(scan_findings.get(k) for k in ("AI腔禁词", "过渡套话", "零信息量感慨"))
