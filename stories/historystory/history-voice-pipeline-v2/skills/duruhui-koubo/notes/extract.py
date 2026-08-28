# -*- coding: utf-8 -*-
import os, re, glob

SRC = r"D:\ds-work\finish"
OUT = r"D:\ds-work\books\duruhui-koubo\notes\digest-03.md"

# (filename, short_name)
FILES = [
    ("41.两晋37：连日本人都推崇的五胡十六国猛人，是英雄，还是汉奸？【最能打的一集】_1460982540_zh.txt", "两晋37"),
    ("42.两晋38：五胡第三弹！鲜卑人两百年苟且发育，只为一次入关机会！_1475340207_zh.txt", "两晋38"),
    ("43.两晋39：为什么关外一旦整合，铁马入中原，就是历史的必然？（最邪门的一集）_1491366185_zh.txt", "两晋39"),
    ("44.两晋40：五胡S3赛季正式开打，由南北对峙急速裂变的三国格局（下手最快的一集）_1508719710_zh.txt", "两晋40"),
    ('45.两晋41："从来就没有什么救世主，朝廷里全是关系户"（谁是门阀？）_1520825525_zh.txt', "两晋41"),
    ("46.两晋42：两千里奔袭，从南方灭蜀，桓温应该走那条线？_1547786471_zh.txt", "两晋42"),
    ("47.两晋43：北伐是假，夺权是真！深度剖析，为什么大多数北伐，必不能成功？_1578383701_zh.txt", "两晋43"),
    ("49.两晋45：剥面皮、凿头顶、剖腹挖心，五胡最变态君主上线！_1597574375_zh.txt", "两晋45"),
    ('50.两晋46：改革就要杀人？"王道+霸道"，千古君臣给十六国开出一剂猛药_1610314547_zh.txt', "两晋46"),
    ("53.两晋49：大元帅为何深夜出逃？千古第一阴谋 有办法破解吗？_1646568359_zh.txt", "两晋49"),
    ("54.五胡一统北方的关键战争中，太傅忙着卖水，皇帝忙着表演，总指挥忙着当小媳妇儿【两晋50】_1658201009_zh.txt", "两晋50"),
    ("56.英雄气短、百年遗恨，王猛死前为何阻止苻坚灭晋？【两晋52】_25720850687_zh.txt", "两晋52"),
    ("57.时来天地皆同力，有些仗，必须在一代人全打完【两晋53】_25842223091_zh.txt", "两晋53"),
    ("58.铁血军团、威震五胡，一期看懂出道即巅峰的北府军【两晋54】_25980700798_zh.txt", "两晋54"),
    ("59.8万打哭97万！扭转历史的淝水之战前，到底发生了什么隐情？【两晋55】_26047745018_zh.txt", "两晋55"),
    ("60.既能逍遥快活、又能肤白貌美，风靡魏晋三百年的五石散，到底猛在什么地方？_26131300526_zh.txt", "两晋56"),
    ("61.间谍反水，百万军破！淝水之战的真相，比史书记载的更残酷！【两晋56】_26231178579_zh.txt", "两晋57"),
    ("62.淝水之战唯一赢家，教科书级别的金蝉脱壳，看我一人如何逆天改命？！【两晋57】_26431196596_zh.txt", "两晋58"),
]

AD_KW = ["小豆", "妙界", "U型枕", "眼罩", "领券", "护颈", "颈椎", "热敷", "按摩", "性价比", "包邮", "下单", "加赠", "运费险", "贺卡", "专属", "促销", "大促", "保价", "焕新", "券"]

NET_KW = ["骚操作","基本盘","内耗","关系户","躺平","拉胯","杀胡令","S3赛季","小媳妇儿","卖水","表演","金蝉脱壳","逆天改命","出道即巅峰","苟且发育","苟且偷生","乖宝宝","火急火燎","花招","一拍即合","接跟头","立人设","翻脸","抱大腿","带节奏","打脸","反转","神操作","狠人","猛人","神仙","上头","破防","整活","封神","血赚","智商税","套路","潜规则","站队","割韭菜","内卷","供应链","心态崩了","躺赢","剧本","顶流","出圈","流量","洗白","立flag","画大饼","画饼","猛药","一剂猛药","割席","邪门","裂开","麻了","妖","最猛","子弹飞","剧本杀","大冤种","冤种","格局打开","摸鱼","划水","摆烂","佛系","社死","社恐","破圈","顶配","低配","高配","满级","满血","复活","开挂","外挂","版本答案","节奏","吃瓜","镰刀","韭菜","焦虑","精神内耗","磁场","玄学","天命","运势","算法","推流","爆款","翻车","塌房","实锤","绝杀","锁死","焊死","套牢","割肉","止损","抄底","梭哈","杠杆","红利","风口","起飞","凉凉","寄","卷王","卷死","润了","润去","加戏","戏多","戏精","发疯","发癫","抽抽","掉线","上分","下分","carry","摸鱼","摆烂"]

INTRO_KW = ["你以为","想象一下","我们不妨","代入","脑补","如果","殊不知","说白了","其实","咱们","咱","换个角度","站在","假如","假设","你可能会","你以为","你猜","你品","品品","脑补一下","代入一下","想象","不妨","试着","假如说","如果换作","换作你"]

def clean_text(text):
    lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        # drop filename artifact lines
        if "_zh.txt" in s and len(s) < 80:
            continue
        if s.startswith("百年苟且发育") or s.startswith("两晋") and len(s) < 60 and "_" in s:
            continue
        lines.append(s)
    return " ".join(lines)

def split_sentences(text):
    # split keeping the ending punctuation
    parts = re.split(r'(?<=[。！？!?])', text)
    out = []
    for p in parts:
        p = p.strip()
        if p:
            out.append(p)
    return out

def is_ad(s):
    return any(k in s for k in AD_KW)

def extract(path, short):
    with open(path, encoding="utf-8", errors="ignore") as f:
        raw = f.read()
    text = clean_text(raw)
    sents = split_sentences(text)
    # remove ad sentences globally
    sents = [s for s in sents if not is_ad(s)]
    n = len(sents)
    used = set()

    # opening: first 3
    opening = sents[:3]
    # ending: last 3
    ending = sents[-3:] if n >= 3 else sents[:]

    result = {
        "opening": opening,
        "ending": ending,
        "history": [],
        "intro": [],
        "rhetoric": [],
        "net": [],
    }

    # 史料引文: sentences with 《 book 》 or quoted citation markers
    for i, s in enumerate(sents):
        if i in used:
            continue
        if "《" in s and "》" in s:
            result["history"].append((i, s))
            used.add(i)
        elif ("“" in s or "”" in s or "「" in s or "」" in s) and any(k in s for k in ["曰","云","记载","史","书","诏","敕","令曰","上书","表曰","叹曰","笑曰","谓"]):
            result["history"].append((i, s))
            used.add(i)
        if len(result["history"]) >= 3:
            break

    # 设问句: sentences ending with ？/？
    for i, s in enumerate(sents):
        if i in used:
            continue
        if s.endswith("？") or s.endswith("?"):
            result["rhetoric"].append((i, s))
            used.add(i)
        if len(result["rhetoric"]) >= 3:
            break

    # 代入式: introspective / reader-immersive
    for i, s in enumerate(sents):
        if i in used:
            continue
        if any(k in s for k in INTRO_KW):
            result["intro"].append((i, s))
            used.add(i)
        if len(result["intro"]) >= 3:
            break

    # 网络梗: modern slang mapped onto ancient scene
    for i, s in enumerate(sents):
        if i in used:
            continue
        hit = [k for k in NET_KW if k in s]
        if hit:
            result["net"].append((i, s, hit))
            used.add(i)
        if len(result["net"]) >= 4:
            break

    return result

def fmt_list(items, prefix="- "):
    if not items:
        return prefix + "无"
    return "\n".join(prefix + x for x in items)

def main():
    blocks = []
    stats = {"history_cover": 0, "net_terms": set(), "total": len(FILES)}
    for fname, short in FILES:
        path = os.path.join(SRC, fname)
        if not os.path.exists(path):
            blocks.append(f"### [{short}]\n- **注意**：文件缺失 {fname}\n")
            continue
        r = extract(path, short)
        if r["history"]:
            stats["history_cover"] += 1
        for it in r["net"]:
            stats["net_terms"].update(it[2])

        b = []
        b.append(f"### [{short}]")
        b.append("- **开头钩子**（原文前 2-3 句，照抄）：")
        b.append(fmt_list(r["opening"]))
        b.append("- **结尾收束**（原文末 2-3 句，照抄）：")
        b.append(fmt_list(r["ending"]))
        b.append("- **史料引文**（文中引用的史书/史料原文，2-3 条，注明出处；无则写\"无\"）：")
        if r["history"]:
            hl = []
            for i, s in r["history"]:
                # try to find book title
                m = re.search(r"《([^》]{1,20})》", s)
                src = ("（出处：" + m.group(1) + "）") if m else "（文中引文）"
                hl.append(s + " " + src)
            b.append(fmt_list(hl))
        else:
            b.append("- 无")
        b.append("- **代入式**（内心OS/心理代入/脑补古人想法片段，摘录 2-3 条）：")
        b.append(fmt_list([s for i, s in r["intro"]]) if r["intro"] else "- 无")
        b.append("- **设问句**（文中设问/反问/自问自答，摘录 2-3 条）：")
        b.append(fmt_list([s for i, s in r["rhetoric"]]) if r["rhetoric"] else "- 无")
        b.append("- **网络梗/现代黑话**（现代词汇嫁接到古代场景的词句，摘录 2-4 条，带原文）：")
        if r["net"]:
            nl = []
            for i, s, hit in r["net"]:
                nl.append(s + " 【黑话：" + "、".join(hit) + "】")
            b.append(fmt_list(nl))
        else:
            b.append("- 无")
        blocks.append("\n".join(b))

    header = "# 杜茹慧历史口播风格蒸馏 · 机械提取 digest-03\n\n"
    header += "> 切片：两晋37~两晋58（18篇）。本文件为 6 维机械提取，原文照抄，不解读。\n\n"
    header += "---\n\n"
    content = header + "\n\n".join(blocks) + "\n"

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(content)

    print("WROTE", OUT)
    print("total files:", stats["total"])
    print("history covered:", stats["history_cover"])
    print("net terms found:", "、".join(sorted(stats["net_terms"])))

if __name__ == "__main__":
    main()
