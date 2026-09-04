# -*- coding: utf-8 -*-
"""
AMMUNITION 构建器 v2：
  1) 从 digest-01~05 解析四个弹药字段（net/rhetoric/intro/history）作为基础；
  2) 对每篇语料正文做「高频指纹词全文扫描」，补齐 称谓/动作/评价 等类别；
  3) 按场景/类型分类，生成 AMMUNITION.md（≥200 条，≥6 类，可追加）。
"""
import os, re, glob

NOTES = r"D:\ds-work\books\duruhui-koubo\notes"
CORPUS = r"D:\ds-work\finish"
OUT = r"D:\ds-work\books\duruhui-koubo\AMMUNITION.md"
DIGESTS = ["digest-01.md", "digest-02.md", "digest-03.md", "digest-04.md", "digest-05.md"]

# 字段小标题 -> 类别
FIELD_CAT = {
    "history": "史料考据引用",
    "rhetoric": "设问与反问",
    "intro": "心理代入标记",
    "net": "通用黑话/句式",  # net 再按关键词细分
}

# 高频指纹词 -> 细类（用于全文扫描补齐 + net 细分）
HIGH_FREQ = [
    ("称谓与身份替换", ["咱", "老同志", "老登", "基本盘", "牛马", "关系户", "大头兵", "老影帝", "影帝", "老六", "属于是"]),
    ("动作与能力描写", ["丝滑", "小连招", "连招", "梭哈", "金蝉脱壳", "逆天改命", "出道即巅峰", "carry", "开挂", "外挂", "满级", "满血", "复活", "上分", "下分", "封神", "整活", "神操作", "骚操作", "苟且发育", "苟且偷生", "立人设", "翻脸", "抱大腿", "带节奏", "打脸", "抽抽", "发疯", "发癫", "一拍即合", "接跟头", "花招", "一剂猛药", "猛药", "割席", "格局打开", "起飞", "锁死", "焊死", "套牢", "割肉", "止损", "抄底", "杠杆", "红利", "风口", "卷王", "卷死", "润了", "润去", "作妖"]),
    ("评价与定性词", ["狠人", "猛人", "神仙", "上头", "破防", "妖", "邪门", "裂开", "麻了", "最猛", "子弹飞", "大冤种", "冤种", "顶配", "低配", "高配", "顶流", "出圈", "破圈", "爆款", "流量", "塌房", "实锤", "绝杀", "血赚", "智商税", "版本答案", "剧本杀", "剧本", "凉凉", "寄", "拉胯", "躺赢", "躺平", "内卷", "摆烂", "佛系", "摸鱼", "划水", "社死", "社恐", "红温"]),
    ("现代制度与概念嫁接", ["供应链", "算法", "推流", "心态崩了", "精神内耗", "磁场", "玄学", "天命", "运势", "画大饼", "画饼", "潜规则", "站队", "割韭菜", "镰刀", "韭菜", "焦虑", "洗白", "立flag", "卖水", "表演", "S3赛季", "内耗"]),
    ("转折与衔接句式", ["殊不知", "说白了", "其实", "你可能会", "换作你", "你以为", "你猜", "你品", "品品", "换句话说", "也就是说", "但结果呢", "结果呢", "说到底"]),
    ("心理代入标记", ["脑补", "代入", "想象一下", "我们不妨", "如果换作", "站在", "假如", "假设", "试着", "不妨", "脑补一下", "代入一下"]),
]
KW2CAT = {}
for cat, kws in HIGH_FREQ:
    for kw in kws:
        KW2CAT.setdefault(kw, cat)

CATEGORY_ORDER = [
    "称谓与身份替换", "动作与能力描写", "评价与定性词",
    "现代制度与概念嫁接", "转折与衔接句式", "心理代入标记",
    "史料考据引用", "设问与反问", "通用黑话/句式",
]

SCENE_NOTE = {
    "称谓与身份替换": "把古人/古群体用现代身份词重新命名，制造亲近感与反差（如「老登」「基本盘」）。",
    "动作与能力描写": "用游戏/网络动作词描写古人的谋略与战局，节奏快、画面感强。",
    "评价与定性词": "一句话给人物/事件贴现代情绪标签，承担「价值判定」功能。",
    "现代制度与概念嫁接": "把当代社会结构/经济/心理概念嫁接到古代场景，制造荒诞反差。",
    "转折与衔接句式": "承上启下的逻辑铰链，决定叙述节奏与「预期违背」的落点。",
    "心理代入标记": "引导读者「脑补古人想法」的触发词，配合【心理代入】手法。",
    "史料考据引用": "引《晋书》《资治通鉴》等原文或数据，建立权威感（配合【史料引用】手法）。",
    "设问与反问": "开头/段间设问、反问、自问自答，制造悬置与好奇（配合【设问钩子】手法）。",
    "通用黑话/句式": "未命中上述专属类别的高频黑话/句式，统一归此，便于后续细分。",
}
TYPE_OF = {"net": "现代黑话", "rhetoric": "设问/反问", "intro": "心理代入", "history": "史料引文"}

# 语料文件名 -> short（用于全文扫描追溯出处文件）
def short_of(filename):
    m = re.match(r"(\d+\..+?)_(\d+)_zh", filename)
    if m:
        return m.group(1)
    return filename

def parse_fields(path):
    """解析四个弹药字段 -> [(short, field, text, tags, srcfile)]"""
    out = []
    src = os.path.basename(path)
    cur_short = None
    cur_field = None
    for ln in open(path, encoding="utf-8", errors="ignore"):
        s = ln.rstrip("\n")
        m = re.match(r"^###\s*\[(.+?)\]", s)
        if m:
            cur_short = m.group(1).strip(); cur_field = None; continue
        if cur_short is None:
            continue
        fm = re.match(r"^-\s*\*\*(.+?)\*\*", s)
        if fm:
            lab = fm.group(1)
            if lab.strip() == "注意":
                cur_field = None
            elif "网络梗" in lab or "现代黑话" in lab or "黑话" in lab:
                cur_field = "net"
            elif "设问" in lab:
                cur_field = "rhetoric"
            elif "代入" in lab:
                cur_field = "intro"
            elif "史料" in lab:
                cur_field = "history"
            else:
                cur_field = None
            continue
        bm = re.match(r"^-\s*(.+)$", s)
        if bm and cur_field:
            txt = bm.group(1).strip()
            if txt in ("无", ""):
                continue
            tags = []
            tm = re.search(r"【黑话[:：](.+?)】", txt)
            if tm:
                tags = [t.strip() for t in re.split(r"[、,，]", tm.group(1)) if t.strip()]
                txt = re.sub(r"\s*【黑话[:：].*?】", "", txt).strip()
            out.append((cur_short, cur_field, txt, tags, src))
    return out

def main():
    # 1) 字段解析基础库
    base = []
    for d in DIGESTS:
        p = os.path.join(NOTES, d)
        if os.path.exists(p):
            base.extend(parse_fields(p))

    buckets = {c: [] for c in CATEGORY_ORDER}
    seen = set()
    for short, field, txt, tags, src in base:
        if field == "net":
            # net 先按关键词细分，否则归通用
            cat = None
            for kw in tags + [txt]:
                for k, c in KW2CAT.items():
                    if k in kw:
                        cat = c; break
                if cat:
                    break
            cat = cat or "通用黑话/句式"
        else:
            cat = FIELD_CAT[field]
        key = (cat, short, txt)
        if key in seen:
            continue
        seen.add(key)
        buckets[cat].append((short, TYPE_OF[field], txt, src, "、".join(tags)))

    # 2) 全文指纹词扫描补齐（尤其 称谓/动作/评价）
    ad_kw = ["小豆","妙界","U型枕","眼罩","领券","护颈","颈椎","热敷","按摩","性价比","包邮","下单","加赠","运费险","贺卡","专属","促销","大促","保价","焕新","券","麦冬","广告","购买","链接","小黄车"]
    for fn in glob.glob(os.path.join(CORPUS, "*.txt")):
        short = short_of(os.path.basename(fn))
        raw = open(fn, encoding="utf-8", errors="ignore").read()
        # 按句切分
        for seg in re.split(r"(?<=[。！？!?])", raw):
            seg = seg.strip()
            if not seg:
                continue
            if any(k in seg for k in ad_kw):
                continue
            for kw, cat in KW2CAT.items():
                if kw in seg:
                    # 取含 kw 的短句窗口
                    i = seg.find(kw)
                    window = seg[max(0, i-20): i+len(kw)+20].strip()
                    if len(window) > 80:
                        window = window[:80] + "…"
                    key = (cat, short, kw, window)
                    if key in seen:
                        continue
                    seen.add(key)
                    buckets[cat].append((short, "现代黑话", window, os.path.basename(fn), kw))
                    break  # 一句只取一个指纹词，避免重复

    total = sum(len(v) for v in buckets.values())

    out = []
    out.append("# AMMUNITION — 杜茹慧历史口播风格弹药库\n")
    out.append(f"> 由 5 份 digest（digest-01~05，覆盖 93 篇语料）字段解析 + 全文指纹词扫描聚合而成，共 **{total}** 条弹药，分 {len([c for c in CATEGORY_ORDER if buckets[c]])} 类。\n")
    out.append("> 用途：被 skill 引用，作为仿写时的「词汇指纹」。每条格式：弹药本体 ｜ 类型 ｜ 适用场景 ｜ 原文例句 ｜ 出处文件 ｜ 篇。\n")
    out.append("> 新增弹药时，在对应类别下追加一行即可，结构不变。\n")
    out.append("\n---\n")

    CAP = 40
    for cat in CATEGORY_ORDER:
        lst = buckets[cat]
        if not lst:
            continue
        shown = lst[:CAP]
        total_cat = len(lst)
        suffix = "" if total_cat <= CAP else f"（展示前 {CAP} / 共 {total_cat} 条，其余按同规则可从语料补齐）"
        out.append(f"\n## {cat}（{total_cat} 条{suffix}）\n")
        out.append(f"> {SCENE_NOTE.get(cat, '')}\n")
        out.append("\n| 弹药本体 | 类型 | 适用场景 | 原文例句 | 出处文件 | 篇 |\n|---|---|---|---|---|---|")
        for short, typ, txt, src, ben_ti in shown:
            本体 = ben_ti if ben_ti else (txt[:12] + ("…" if len(txt) > 12 else ""))
            scene = {"现代黑话": "任意场景的词汇降维", "设问/反问": "钩子/段间悬念", "心理代入": "脑补古人心理", "史料引文": "增强权威/考据"}.get(typ, "风格指纹")
            ex = txt if len(txt) <= 46 else txt[:46] + "…"
            out.append(f"| {本体} | {typ} | {scene} | {ex} | {src} | {short} |")
        out.append("")

    out.append("\n---\n\n## 运用规则（被 skill 引用）\n")
    out.append("""
1. **密度控制**：单篇口播 3000–6000 字，黑话密度建议 8–15 处，集中在「价值判定」与「动作描写」节点；中段可密，开头钩子与结尾收束各留 1 处强标签即可，避免全程堆砌导致审美疲劳。
2. **搭配方式**：
   - 称谓替换（老登/基本盘）一般放在**段落主语位置**，奠定「现代视角看古人」的基调；
   - 动作能力词（丝滑小连招/金蝉脱壳/梭哈）放在**战局/权谋转折处**，制造爽感；
   - 评价定性词（狠人/妖/邪门/破防）放在**人物出场或结局判定处**，一锤定音；
   - 转折衔接词（殊不知/说白了/其实）放在**预期违背的落点前**，制造反转；
   - 史料考据与设问放在**权威建构与悬念制造处**，不抢戏。
3. **红线（避免堆砌）**：
   - 同一黑话词在单篇内重复 ≤2 次，跨篇复用是风格指纹、允许；
   - 不在同一句话里叠 2 个以上评价定性词（如「这个狠人妖操作」即过载）；
   - 阴暗小故事、广告口播、第一人称自我介绍（「我是杜茹慧」）**不进入仿写**，由总控清洗；
   - 史料引文必须真实可考，不得为贴合黑话编造史书原文。
4. **跨朝代一致性**：上述弹药不绑定两晋/南北朝，晚清/隋材料（见 digest-04）同样适用，仅个别词有朝代偏好（如「老登」偏用于昏暴帝王，「基本盘」偏用于权力结构分析）。仿写任意朝代时按需调用，不必改写弹药本身。
""")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("WROTE", OUT)
    print("total items:", total)
    for c in CATEGORY_ORDER:
        if buckets[c]:
            print(f"  {c}: {len(buckets[c])}")

if __name__ == "__main__":
    main()
