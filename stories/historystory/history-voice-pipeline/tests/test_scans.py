"""确定性扫描单测（执行方案 §4.6：程序化部分不进 LLM）。"""
from app.services import scans


def test_banned_words_hit():
    script = "众所周知，桀是暴君。这段历史引人深思。"
    hits = scans.scan_banned_words(script)
    words = {h["word"] for h in hits}
    assert "众所周知" in words and "引人深思" in words


def test_banned_words_clean():
    assert scans.scan_banned_words("桀放走了汤。三年后，王朝没了。") == []


def test_transition_cliches():
    assert scans.scan_transition_cliches("话说回来，鸣条之战不简单。")
    assert scans.scan_transition_cliches("鸣条的土是黏的。") == []


def test_zero_info():
    assert scans.scan_zero_info("这真是历史的尘埃啊。")
    assert scans.scan_zero_info("他放走了那个灭夏的人。") == []


def test_split_segments_and_tolerance():
    script = """【段1·钩子】
南巢的冬天湿冷。一个老人缩在墙角，数着流放路上的第三个年头。三年前，他还是拥有天下的王。
【段2·锚定】
这个人叫桀。夏朝最后一个王。故事要从都城安邑说起。"""
    segs = scans.split_segments(script)
    assert set(segs) == {1, 2}
    outline = [
        {"段号": 1, "预计字数": "60（容差 ±40%）", "功能类型": "钩子"},
        {"段号": 2, "预计字数": "70（容差 ±20%）", "功能类型": "锚定"},
        {"段号": 3, "预计字数": "100", "功能类型": "主线节点"},
    ]
    findings = scans.check_word_count_tolerance(script, outline)
    # 段3 缺段必报；段1/段2 字数在容差内不报
    assert any(f["段号"] == 3 and f["issue"] == "成稿缺段" for f in findings)
    assert not any(f["段号"] == 1 for f in findings)


def test_tolerance_over_limit():
    script = "【段1·钩子】\n" + "字" * 200
    outline = [{"段号": 1, "预计字数": "60（容差 ±40%）", "功能类型": "钩子"}]
    findings = scans.check_word_count_tolerance(script, outline)
    assert findings and findings[0]["issue"] == "字数超出容差"


def test_hard_violations_gate():
    assert scans.has_hard_violations({"AI腔禁词": [{"word": "众所周知"}],
                                      "过渡套话": [], "零信息量感慨": []})
    assert not scans.has_hard_violations({"AI腔禁词": [], "过渡套话": [],
                                          "零信息量感慨": [], "字数容差": [{}]})
