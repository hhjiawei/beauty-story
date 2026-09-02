"""
==========================================================================
 prompts.py —— 流水线全部节点 Prompt 集中管理文件
==========================================================================

设计契约（执行方案 §5.3 人格三层 + §4 各节点职责 + §3 deepagents 架构）：

- 每个 builder 返回 (system, user) 二元组，交给该节点的 deepagents 实例执行；
- system = 节点标记 + 人格 L1 常驻前缀（persona-writer 全文，100% 在场）
         + 已挂载技能清单（deepagents 渐进加载：清单引导 agent 用 read_file
           读取 /skills/<name>/SKILL.md 手册正文，不再全文塞进 prompt）
         + 人格 L2 系列记忆；
- user   = 节点输入契约（PipelineState 字段子集）+ 输出 Schema
         + 打回意见段（重跑时注入，「按条目修改，不重写全文」）；
- system 第一行固定为 <!-- NODE:节点id --> 标记：
  ① MockLLM 据此路由（测试/演示）② 节点日志可审计；
- 各节点默认挂载技能 = 执行方案 §5.1 挂载表（app/agents/node_registry.py），
  前端改挂载后由节点函数把实际清单传进来（mounted_skills 参数），
  prompt 清单与实际挂载永远一致。

节点索引（命名即含义）：
  N1 build_n1_event_card_mining      史料分析 · 事件卡选矿   → historical-event-cards
  N2 build_n2_style_robe_selection   风格选定 · 本期外衣     → duruhui-style
  N3 build_n3_outline_blueprinting   大纲生成 · 蓝图绘制     → history-outline-planner
  N4 build_n4_chapter_construction   旁白写作 · 逐章施工     → viral-history-narration
     build_n4_full_script_stitch     旁白写作 · 全稿缝合     → viral-history-narration
  N5 build_n5_three_gate_audit       成稿审核 · 三道门禁
  N6 build_n6_storyboard_translation 画本加工 · 声音翻译

技能接口链（各节点 user 提示词已对齐 skill 契约，2026-09 修订）：
  N1 产出六型资料卡包（C/P/R/B/D/E，validate_cards.py 过闸）
    → N2 消费卡摘要，产出《风格施工包》七件候选（人工拍板）
    → N3 消费资料卡包 + 风格施工包，产出《大纲包》＝篇级总卡＋段级施工卡
       （check_outline.py 过闸）
    → N4 消费大纲包 + 资料卡包 + 风格施工包，逐章施工后缝合
       （check_output.py 过闸）
==========================================================================
"""
from __future__ import annotations

import json

from . import memory_store
from .agents.node_registry import DEFAULT_SKILL_MOUNTS
from .skills_loader import load_skill, skill_description

# ---------------------------------------------------------------- 公共件

def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def persona_prefix() -> str:
    """人格 L1 常驻前缀：persona-writer 全文，每个内容节点 100% 在场。"""
    return load_skill("persona-writer")


def series_memory_section(node_uses: list[str]) -> tuple[str, list[str]]:
    """人格 L2 系列记忆：返回 (prompt段文本, 实际加载的记忆文件清单)。"""
    parts, loaded = [], []
    if "lessons" in node_uses:
        txt = memory_store.read_memory(memory_store.LESSONS)
        if txt.strip():
            parts.append(f"## 系列记忆 · 打回教训沉淀（历次人工打回的教训，务必避开）\n{txt}")
        loaded.append(memory_store.LESSONS)
    if "voice_samples" in node_uses:
        txt = memory_store.read_memory(memory_store.VOICE_SAMPLES)
        if txt.strip():
            parts.append(f"## 系列记忆 · 声口样句库（历期通过的语气示例，声口向它对齐）\n{txt}")
        loaded.append(memory_store.VOICE_SAMPLES)
    return ("\n\n".join(parts), loaded)


def rework_section(feedback: str | None, prev_artifact_brief: str | None) -> str:
    """打回意见注入段（执行方案 §6.3 上下文纪律）。"""
    if not feedback:
        return ""
    return (
        "\n\n## ⚠️ 打回重跑指令（最高优先级）\n"
        "上一版产物被人工闸门打回。纪律：**按打回条目逐条修改，不顺手重写全文"
        "——重写是偷懒，修改才是施工。**\n\n"
        f"【打回意见】\n{feedback}\n\n"
        f"【上一版产物（在此之上修改）】\n{prev_artifact_brief or '（见上方输入）'}\n"
    )


def _mounted_skills_section(mounted_skills: list[str]) -> str:
    """已挂载技能清单：引导 deep agent 走渐进加载（read_file 读手册正文）。

    技能全文不再塞进 system——这是 deepagents skills 机制的核心收益：
    清单只占几行，正文由 agent 按需读取，且前端改挂载后此处自动同步。
    """
    lines = ["# 本节点挂载技能（手册在虚拟文件系统 /skills/ 下，渐进加载）"]
    for i, name in enumerate(mounted_skills):
        tag = "（本节点主技能）" if i == 0 else ""
        lines.append(f"- **{name}**{tag}：{skill_description(name)}")
    lines += [
        "",
        "⚠️ 开工纪律：动手前先用 read_file 通读主技能手册 /skills/<主技能名>/SKILL.md 全文"
        "（其余技能按任务需要阅读），严格遵循其中的 SOP、Schema 与禁忌清单。",
        "⚠️ 输出纪律：最终结果必须直接写进你的最终答复——流水线只从最终答复提取 JSON，"
        "不要只把结果写进文件。",
    ]
    return "\n".join(lines)


def _system(node_marker: str, mounted_skills: list[str],
            memory_uses: list[str]) -> tuple[str, list[str]]:
    parts = [
        f"<!-- NODE:{node_marker} -->",
        "# 人格层（L1 常驻，你的操作系统）\n" + persona_prefix(),
    ]
    if mounted_skills:
        parts.append(_mounted_skills_section(mounted_skills))
    mem_txt, loaded = series_memory_section(memory_uses)
    if mem_txt:
        parts.append(mem_txt)
    return "\n\n---\n\n".join(parts), loaded


# ---------------------------------------------------------------- N1 史料分析

def build_n1_event_card_mining(state, feedback=None, prev=None,
                               mounted_skills=None) -> tuple[str, str, list[str]]:
    system, loaded = _system(
        "n1_event_card_mining",
        mounted_skills or DEFAULT_SKILL_MOUNTS["n1_event_card_mining"],
        memory_uses=["lessons"],
    )
    user = f"""## 输入：任务信息
- 史料类型：{state["source_type"]}（dynasty 朝代 / person 人物 / event 事件）
- 目标时长：{state["target_minutes"]} 分钟
- 集次：第 {state["episode_no"]} 集
{f"- 上集衔接段：{state.get('prev_episode_bridge')}" if state.get("prev_episode_bridge") else ""}

## 输入：史料原文
{state["source_text"]}

## 任务：按主技能（historical-event-cards）「六步取证流程」执行
1. **读料判型**：通读史料，确认题材类型、覆盖时间段与出场人物；
2. **拆主干事件卡 C-**：一卡一事，装不下就拆（"鸿门宴"必须拆成赴宴/舞剑/闯帐/尿遁四张）；同一事件多个史料版本分别成卡、备注互标卡号，不抹平分歧；先标可信度初判。事件卡 ≥5 张；
3. **缺口诊断**：对照下游需求盘点——人物只有名字没有性格→补人物卡 P-；博弈关系说不清→补关系卡 R-；制度/地理门槛高→补背景卡 B-；宏大判断没数字托底→补数据卡 D-；有歇后语/相似事件/冷知识/名言→补彩蛋卡 E-（有就拆，没有不强凑）；
4. **定向搜索补料**：每个缺口按手册 references/research-playbook.md 的查询公式联网搜索（环境无搜索工具时凭已有史料拆卡，缺口在备注标"需补料"）；来源优先级：正史原文＞学术机构/博物馆/考古报告＞权威媒体＞百科（仅作线索不作依据）；搜不到标"存疑"，严禁脑补填充；
5. **多源互证与定级**：关键事实（时间/数字/死因/胜负）力争 ≥2 个独立来源，孤证标"存疑"；终审定级 正史/诸子/传说/出土文献 四级，传说级限位（仅钩子/彩蛋/氛围可用）；
6. **写卡校验**：按手册 references/schema.md 的字段规格填卡，然后过出口闸门。

## 字段要点（细则以 schema.md 为准）
- 卡号：卡型前缀 + 三位数字各自递增（C-001、P-001……），全库唯一；
- 每卡必有：对应卡型必填字段 + 史料出处（具体书名/篇目，多源用 `/` 分隔，网搜补料写明具体来源，不许只写"网络"）+ 可信度；
- 事件卡加标：叙事角色（钩子/锚定/主线节点/插件/高潮/收束/衔接，可复选）+ 本集用不用（用/备用/不用）——下游按这两个字段筛选与布点；
{f'- 人物篇加标：人生阶段、弧光位置、颠覆印象度（高/中/低）。' if state["source_type"] == "person" else ""}
{f'- 事件篇加标：因果位置（远因/近因/导火索/结果/余波）、事件阶段、多方视角。' if state["source_type"] == "event" else ""}
{f'- 朝代篇加标：因果位置、制度名称，并留意时代氛围判断所需的背景卡。' if state["source_type"] == "dynasty" else ""}
- **只记事实，不预判弹药**：禁止"弹药潜质/亮点类型"类风格字段（弹药由大纲节点从风格层弹药库统一选配，本层越权预判会污染下游）；有可逐字引用的原文照录进「古文原句」并标出处——原文是史料，怎么炸是下游的事；
- 可选字段有内容才写，没有整个省略，不写空字符串凑格式。

## 出口硬闸门（必过）
卡包写入文件后运行校验脚本，FAIL 项修完复检，全绿（或仅剩能说明理由的 WARN）才可交付：

python3 /skills/historical-event-cards/scripts/validate_cards.py <卡包.json>

## 输出
只输出一个 JSON 数组（不要任何解释文字），元素为六型资料卡对象（C/P/R/B/D/E 混排，卡号即身份）。
"""
    user += rework_section(feedback, prev)
    return system, user, loaded


# ---------------------------------------------------------------- N2 风格选定

def build_n2_style_robe_selection(state, feedback=None, prev=None,
                                  mounted_skills=None) -> tuple[str, str, list[str]]:
    system, loaded = _system(
        "n2_style_robe_selection",
        mounted_skills or DEFAULT_SKILL_MOUNTS["n2_style_robe_selection"],
        memory_uses=["lessons", "voice_samples"],
    )
    # 注意：资料卡已废除「弹药潜质」字段（弹药归 N3 选配），摘要只取事实性字段；
    # 六卡型字段各异，内容栏按卡型回退取 冲突/特质/关系/要点/指标/内容
    def _brief(c):
        content = (c.get("冲突") or c.get("核心特质") or c.get("张力点")
                   or c.get("要点") or c.get("指标") or c.get("内容") or "")
        return {"卡号": c.get("卡号"), "卡型": c.get("卡型"), "内容": content,
                "叙事角色": c.get("叙事角色"), "情绪类型": c.get("情绪类型"),
                "颠覆印象度": c.get("颠覆印象度")}
    cards_brief = [_brief(c) for c in state.get("event_cards", [])
                   if c.get("本集用不用") != "不用"]
    user = f"""## 输入：任务信息
- 题材类型：{state["source_type"]}（dynasty 朝代 / person 人物 / event 事件）
- 目标时长：{state["target_minutes"]} 分钟｜第 {state["episode_no"]} 集

## 输入：本集素材摘要（N1 选矿结果，已过闸的事实卡）
{_j(cards_brief)}

## 任务：按主技能（duruhui-style）做风格策展——「给骨选型，给衣配料」，不写一句正文
0. **特质诊断**（手册步骤零）：一句话主线（收在人→命运类／收在事→进程类／收在理→结构类）+ 特质标签（悲剧/荒诞/权谋/逆袭/争议/惨烈……可多个）+ 时代氛围 + 悲悯段落预判（挂卡号）。
   注意：输入已是选矿后的事件卡摘要，直接诊断，不走"整理稿"两步交付分支；
1. **三维坐标**：知识密度 / 情感深度 / 娱乐强度各 1-5 分 + 评估理由；
2. **出 1-2 套候选**供人工拍板：每套 = 完整《风格施工包》七件草案 + 推荐理由 + 一句「本期语气示例」（写作层定声口的对齐基准，声口向系列记忆中的声口样句对齐）。

## 《风格施工包》七件（每件必填；下游大纲节点逐件清点，缺件会被记进「自补清单」降级处理）
1. **叙事路由**：人物传/事件录/制度论 选定 + 判定理由（想让观众记住这个人/这件事/这个规律）+ 骨架清单；
2. **大纲规划**：编年骨架方向 + 弹药布点方向 + 钩子/收尾位置建议（只给方向——明细大纲是下游 N3 的职责，不许越界写细纲）；
3. **签名声音系统**：领属词（我X，全篇唯一）+ 主要人物绰号—特征—事迹对照表（从最炸的事迹反推绰号，正面英雄给尊称不起贬损绰号）+ 称呼降格规则（史料原文引用内保留原称呼）；
4. **开场钩子术**：七种起手式选型 + 钩子方向（≤300 字、最后一句落在正题入口）+ 在场感称呼；悲悯重题材禁用香艳/搞笑钩子，降级为幕后开场；
5. **正文推进引擎**：设问策略 + 脑补留白方向（必挂声明牌）+ 弹药投放方向（类目 + 史实支撑点，挂素材摘要卡号）+ 搭靶/亮锤节点预判；
6. **史料双保险**：锚点规则（年号+公元双标 / 原文+白话翻译 / 宏大判断跟数字托底）+ 反常点推理链（按强度挂声明等级）；
7. **语气与收尾**：三轨配比（戏谑/悲悯/热血，按特质标签定主配方）+ 禁区清单（悲悯段锁定、轨道切换过渡句）+ 收尾四件套组合。

## 输出 Schema（只输出 JSON 对象）
{{
  "特质诊断": {{"主线一句话": "...", "特质标签": ["..."], "时代氛围": "...", "悲悯段落预判": ["C-00X"]}},
  "三维坐标": {{"知识密度": 4, "情感深度": 3, "娱乐强度": 4, "评估理由": "..."}},
  "候选风格": [
    {{
      "风格名": "...",
      "核心气质": "...",
      "推荐理由": "...",
      "本期语气示例": "...",
      "风格施工包": {{
        "叙事路由": {{"选定": "人物传|事件录|制度论", "判定理由": "...", "骨架清单": "..."}},
        "大纲规划": {{"编年骨架方向": "...", "弹药布点方向": "...", "钩子收尾位置建议": "..."}},
        "签名声音系统": {{"绰号对照表": [{{"人物": "...", "绰号": "...", "特征": "...", "事迹": "..."}}], "称呼降格规则": "..."}},
        "开场钩子术": {{"起手式": "...", "钩子方向": "...", "在场感称呼": "..."}},
        "正文推进引擎": {{"设问策略": "...", "脑补留白方向": "...", "弹药投放方向": "...", "搭靶亮锤节点": "..."}},
        "史料双保险": {{"锚点规则": "...", "反常点推理链": "..."}},
        "语气与收尾": {{"三轨配比": "...", "禁区清单": "...", "收尾四件套": "..."}}
      }}
    }}
  ]
}}
"""
    user += rework_section(feedback, prev)
    return system, user, loaded


# ---------------------------------------------------------------- N3 大纲生成

def build_n3_outline_blueprinting(state, feedback=None, prev=None,
                                  mounted_skills=None) -> tuple[str, str, list[str]]:
    system, loaded = _system(
        "n3_outline_blueprinting",
        mounted_skills or DEFAULT_SKILL_MOUNTS["n3_outline_blueprinting"],
        memory_uses=["lessons"],
    )
    used_cards = [c for c in state.get("event_cards", []) if c.get("本集用不用") != "不用"]
    user = f"""## 输入：资料卡包（唯一事实来源，N1 已过闸；卡上没有的史实一个字不许进大纲）
{_j(used_cards)}

## 输入：本期风格施工包（N2 产出、人工拍板；若传入的是候选对象，取其中「风格施工包」七件 + 本期语气示例）
{_j(state.get("style_card", {}))}

## 输入：任务参数
- 类型：{state["source_type"]}｜目标时长：{state["target_minutes"]} 分钟｜第 {state["episode_no"]} 集
{f"- 上集衔接段（本集开头要接住）：{state.get('prev_episode_bridge')}" if state.get("prev_episode_bridge") else ""}

## 任务：按主技能（history-outline-planner）「六步订纲流程」执行
- **第0步 接收清点**：风格施工包七件逐件标"到齐/缺失"；事件卡计数 N（<5 张在自补清单说明）；存疑纪年/人名/官职先联网核实——取证发生在订纲时，不留给写作节点；缺失件与存疑项记入篇级「自补清单」；
- **第1步 因果主干**：时间线初排→标因果铰链（谁导致谁，禁止只按时间罗列）→节点分级（强化 3-5 个／关键／过渡 ≤1/3）→强化节点标动作链骨架「谁→什么动作→对方什么反应→下一招」；
- **第2步 结构决策**：开头前置（选矛盾最激烈的一帧——自问"全片只留 30 秒留哪段"）→按 起承转合尾 节奏曲线落入六模块（①钩子②铺陈③展开④高潮⑤收束⑥尾声）→结尾呼应（前置片段归位 + 开头设问回收），登记为伏笔；
- **第3步 段落切分**：事件卡→S 段映射（一卡可拆多段、多卡可并一段）；每段定功能类型/时间码（累计字数 ÷ 270 字/分钟）/情绪坐标/预计字数；总字数预算 = {state["target_minutes"]} × 270，超预算先砍过渡段、再合并关键段，强化段不砍；
- **第4步 技法弹药布点**：逐段写段意（写不出段意的段合并或删）→打技法标（[心理代入][词汇降维][场景重构][反讽][设问][史料引用]，悲悯段只许[史料引用]）→弹药按「选配五问」预选（功能定位→题材适配→史料锚点→密度轮换→兑现能力；先查手册本地弹药库 references/opening-hooks.md、explosion-points.md、dialect-ammunition.md、ammunition.md，查不到再联网搜，没有就空着不硬凑）→填四张清单（弹药/史料/歇后语/相似事件，生产指南见 references/list-building.md）→登记伏笔（F-01 起，埋设必配回收、回收段号 > 埋设段号）与炸点（语言/结构/情绪三层，相邻不同型）；
- **第5步 全局校验**：过出口闸门，全绿才交付。

## 卡面纪律（字段细则以 references/card-spec.md 为准）
- 每段一张段级施工卡：段号 + 施工卡号 + 模块归属 + 段意 + 功能类型 + 时间码 + 使用史料卡 + 节点分级 + 指定技法 + 因果接口 + 弹药清单 + 史料清单 + 歇后语清单 + 相似事件 + 炸点 + 伏笔 + 情绪坐标 + 预计字数 + 备注；
- **因果接口**必填「本段之因 ← S-___ ｜ 本段之果 → S-___」——填不出因的段当场修掉（补过渡段或并入有因的段）；①钩子段之因填 —、⑥尾声段之果填 —（下集）；
- 备注只写施工指令（怎么写、避什么坑、呼应哪里），**禁写正文句子**；
- 每个弹药/歇后语/相似事件必须挂史料锚点（卡号）；悲悯段弹药清零、方言禁入、技法只留[史料引用]；传说级（D 级）材料仅可进钩子/彩蛋/氛围位并标"须挂声明牌"；方言全篇 ≤3 处；主钩子每集 1 发只在①模块。

## 出口硬闸门（必过）
大纲与事件卡分别写入文件后运行检查脚本，FAIL 项修完复检，全绿才可交付：

python3 /skills/history-outline-planner/scripts/check_outline.py <大纲.md> --events <事件卡.txt> --minutes {state["target_minutes"]}

## 输出 Schema（只输出一个 JSON 对象）
{{
  "篇级总卡": {{
    "题目集名": "...",
    "叙事路由": "人物传|事件录|制度论 ＋ 一句话判定理由",
    "目标时长": "{state["target_minutes"]}分钟",
    "总字数预算": 0,
    "主线因果链": "因为……所以……最终……（一句话讲完全篇逻辑）",
    "开头前置": "前置片段 ＋ 选帧理由",
    "结尾呼应": "前置片段归位方式 ＋ 开头设问回收方式",
    "声音素材": "领属词 ＋ 主要人物绰号—特征—事迹候选",
    "伏笔总台账": [{{"伏笔编号": "F-01", "内容": "...", "埋设段": "S-001", "回收段": "S-005"}}],
    "炸点总表": [{{"段": "S-003", "层型": "结构·..."}}],
    "情绪地图": "各段轨道一览（戏谑/悲悯/热血+强度），悲悯段显式标出",
    "弹药总表": "全篇弹药汇总查重：同词 ≤2 次、同类不连续两段",
    "字数预算表": "各段预计字数合计 = 预算 ±10%",
    "自补清单": "缺失施工件 / 存疑史实及处理方式"
  }},
  "段级施工卡": [
    {{"段号": 1, "施工卡号": "S-001", "模块归属": "①钩子", "段意": "...",
      "功能类型": "钩子|锚定|主线节点|插件|高潮|收束|衔接",
      "时间码": "00:00–01:18", "使用史料卡": ["C-001"], "节点分级": "强化|关键|过渡|—",
      "指定技法": ["..."],
      "因果接口": "本段之因 ← — ｜ 本段之果 → S-002（喂给它的态势/问题/情绪）",
      "弹药清单": "弹药名（类型）｜作用｜推荐度｜原因；无则 空",
      "史料清单": [{{"典籍": "...", "原文摘录": "...", "对应事件卡": "C-001", "来源等级": "A|B|C|D", "用途": "..."}}],
      "歇后语清单": "歇后语＋挂接事件＋建议入点＋（传统/自创）；无则 空",
      "相似事件": "案例＋相似点＋引申方式（铺垫/对照/判词）；无则 空",
      "炸点": "语言|结构|情绪 类型＋位置 或 无",
      "伏笔": "埋设 F-__ ｜ 回收 F-__ ｜ 无",
      "情绪坐标": "戏谑|悲悯|热血（强度 _/5）",
      "预计字数": 350,
      "备注": "只写施工指令，禁写正文句子"}}
  ]
}}
"""
    user += rework_section(feedback, prev)
    return system, user, loaded


# ---------------------------------------------------------------- N4 旁白写作

def build_n4_chapter_construction(state, chapter_segments: list[dict],
                                  prev_chapter_tail: str | None,
                                  feedback=None, prev=None,
                                  mounted_skills=None) -> tuple[str, str, list[str]]:
    """逐章施工 prompt。每章携带：前一章末段 + 全篇大纲包 + 声口基准（长文连贯三件套）。"""
    system, loaded = _system(
        "n4_narration_construction",
        mounted_skills or DEFAULT_SKILL_MOUNTS["n4_narration_construction"],
        memory_uses=["lessons", "voice_samples"],
    )
    used_cards = [c for c in state.get("event_cards", []) if c.get("本集用不用") != "不用"]
    user = f"""## 输入：全篇大纲包（N3 已过闸：篇级总卡 + 全部段级施工卡——把握全局用，写作范围以本章施工卡为准）
{_j(state.get("outline", []))}

## 输入：本章施工卡（本次只写这几段，逐卡施工）
{_j(chapter_segments)}

## 输入：资料卡包（段内事实唯一来源——施工卡引了哪张卡，本段就只能用哪张卡里的事实）
{_j(used_cards)}

## 输入：本期风格施工包（声口基准：领属词 / 绰号对照表 / 称呼降格 / 三轨配比 / 本期语气示例）
{_j(state.get("style_card", {}))}

## 输入：前一章末段（保持连贯，接口要焊住）
{prev_chapter_tail or "（本章是全篇开头，无前一章）"}

## 任务：按主技能（viral-history-narration）逐段施工
- **本章含第 1 段时**：先过阶段零（读料取证——不确定的年份/人名/官职先联网核实，取证在动笔前；按施工包「叙事路由」定调；对施工卡弹药清单逐条斟酌，不准确的宁可弃用）与阶段一（声音卡以施工包「签名声音系统」定稿：领属词全篇唯一、绰号—特征—事迹对照、称呼降格规则；钩子卡按「开场钩子术」施工，≤300 字、最后一句落在正题入口）；
- **后续章节**：沿用既有声音卡，与前一章末段声口对齐，不另起炉灶、不换领属词；
- **每段过四道引擎**：①心理OS与场景脑补（只填史书留白，不改史实骨架，必挂声明牌"或许/可以想象/估计"）→ ②弹药投放（按选配五问复核施工卡弹药：功能定位→题材适配→史料锚点→密度轮换→兑现能力，答不上就撤弹）→ ③反讽结构（材料有真实"自信→翻车"弧线才用，亮锤 ≤ 搭靶段 1/5）→ ④因果链校验三问（因从哪来／果落在哪／与下段怎么咬合——照施工卡「因果接口」焊死）；
- **写的是听的**：一句一个信息、强调词在句尾、大数字先换算；（顿）标停顿位、【上屏】标引文、（地图留白 X 秒）标地图节点；每段正文开头标【段N·功能类型】；
- **悲悯段**（情绪坐标标悲悯者）：零梗零绰号零方言，白描 + 原文直引；进出悲悯轨必补显式过渡句；动情点前后 30 秒不玩梗；
- **史料双保险随写随做**：新时间点年号+公元双标；原文引用配白话翻译（梗只落翻译层、不动原文）；宏大判断后跟数字或原文托底；
- **零广告**：剥离一切广告植入痕迹。

## 大纲约束纪律
- **硬约束（无权改）**：史实骨架、段序、功能类型、伏笔埋收位置、悲悯段禁区、因果接口——有异议写进「施工异议」，只标注不擅自处理；
- **软约束（可撤换须声明）**：弹药与技法——大纲是推荐不是命令，写作节点保留撤弹权；按选配五问复核后可撤弹/换弹，逐条写进「技法弹药调整声明」并给出理由；
- 每处埋钩/兑现登记进「本章钩子台账」（埋钩位置 → 计划兑现位置），供缝合节点核销。

## 输出 Schema（只输出 JSON 对象）
{{
  "本章正文": "按成稿格式写的本章 Markdown（【段N·功能类型】标注、（顿）/【上屏】/（地图留白 X 秒）齐全）",
  "技法弹药调整声明": ["段N：撤/换某弹药或技法 ＋ 理由（无则空数组）"],
  "本章钩子台账": [{{"类型": "埋钩|兑现", "内容": "...", "位置": "段N", "计划兑现位置": "段M"}}],
  "施工异议": ["对大纲的疑问，只标注不擅自处理（无则空数组）"]
}}
"""
    user += rework_section(feedback, prev)
    return system, user, loaded


def build_n4_full_script_stitch(state, chapter_drafts: list[str],
                                mounted_skills=None) -> tuple[str, str, list[str]]:
    """全稿缝合 prompt：焊缝隙 + 双保险 + 逻辑核销 + 情绪质检 + 成稿组装 + 硬闸门。"""
    system, loaded = _system(
        "n4_full_script_stitch",
        mounted_skills or DEFAULT_SKILL_MOUNTS["n4_narration_construction"],
        memory_uses=[],
    )
    user = f"""## 输入：各章初稿（按顺序，含各章钩子台账）
{chr(10).join(f"--- 第{i+1}章 ---{chr(10)}{d}" for i, d in enumerate(chapter_drafts))}

## 输入：全篇大纲包（核对伏笔埋收、呼应归位、悲悯段禁区、因果接口）
{_j(state.get("outline", []))}

## 任务：按主技能（viral-history-narration）阶段三收尾
1. **缝合**：逐接口检查——主线按篇型缝合（{"命运感缝合" if state["source_type"] == "person" else "因果缝合"}，用上一段的余震引出下一段的地震），插件进出用挂接句，禁用过渡套话；领属词、绰号全篇统一（以声音卡为准）；
2. **朗读测试**：拆读不顺的句子、断一口气读不完的句子；每 60 秒查信息/情绪增量；
3. **史料双保险复核**：每个新时间点年号+公元双标无遗漏；每处原文引用配白话翻译；每个宏大判断有数字/原文托底；反常处证据链 ≥2 条、声明等级到位、孤证只写"存疑"；
4. **逻辑核销**：各章钩子台账逐条核销——埋钩必兑现，兑现不了的删钩改平实表述，不许留坑；设问必已回答；意外类转折已补"能接住意外靠的是……"；决策现场未混入后见之明；收尾回扣开头（开头立的问题/误判，结尾给出答案或推翻，单集逻辑闭环）；
5. **情绪质检**：对照禁区清单扫悲悯轨（零梗零绰号，改白描+原文直引）、轨道切换过渡句、动情点隔离区；收尾四件套按需组合（总结排比→金句收束→栏目收尾→下期预告钩连）；
6. **成稿组装**：段号标注/【上屏】/（顿）/（地图留白 X 秒）按成稿格式收齐，广告植入痕迹全部剥离。

## 出口硬闸门（必过）
成稿与大纲分别写入文件后运行检查脚本，FAIL 项回到对应段落重写后复检，全绿才可交付：

python3 /skills/viral-history-narration/scripts/check_output.py <成稿.txt> --outline <大纲.txt>

## 输出 Schema（只输出 JSON 对象）
{{
  "成稿": "# 《...》旁白成稿\\n\\n> 目标时长...\\n\\n## 第一章 ...\\n（完整 Markdown）",
  "自查清单": [{{"item": "...", "verdict": "过|不过", "location": "..."}}]
}}
"""
    return system, user, loaded


# ---------------------------------------------------------------- N5 成稿审核

def build_n5_three_gate_audit(state, scan_findings: dict,
                              mounted_skills=None) -> tuple[str, str, list[str]]:
    system, loaded = _system(
        "n5_three_gate_audit",
        mounted_skills or DEFAULT_SKILL_MOUNTS["n5_draft_three_gate_audit"],
        memory_uses=[],
    )
    user = f"""## 输入：旁白成稿（被审对象）
{state.get("script_md", "")}

## 输入：单集大纲文件（结构门禁对照基准）
{_j(state.get("outline", []))}

## 输入：事件卡（史实门禁对照基准）
{_j(state.get("event_cards", []))}

## 输入：确定性扫描结果（代码已扫，你复核并补漏；扫描管「词」，你管「句式模式」与判断）
{_j(scan_findings)}

## 任务
过三道门禁，逐项举证（过/不过+具体位置+判罚依据），输出按主技能 Output Schema 的 JSON 对象。
确定性扫描有硬伤的项直接判不过；你发现的扫描漏网问题追加进对应门禁。
"""
    return system, user, loaded


# ---------------------------------------------------------------- N6 画本加工

def build_n6_storyboard_translation(state, pronunciation_dict: dict,
                                    feedback=None, prev=None,
                                    mounted_skills=None) -> tuple[str, str, list[str]]:
    system, loaded = _system(
        "n6_storyboard_translation",
        mounted_skills or DEFAULT_SKILL_MOUNTS["n6_storyboard_translation"],
        memory_uses=["lessons"],
    )
    user = f"""## 输入：旁白成稿（审核通过版）
{state.get("script_md", "")}

## 输入：大纲情绪坐标（情感标注的图纸——照抄翻译）
{_j([{"段号": s.get("段号"), "情绪坐标": s.get("情绪坐标"), "功能类型": s.get("功能类型")} for s in state.get("outline", [])])}

## 输入：系列读音词典（累积资产，直接复用；发现新专名请补充）
{_j(pronunciation_dict)}

## 任务：画本加工（弹药的「击发」工序）
1. 拆分单元：按语义拆 1-3 句的合成单元，每单元 ≤80 字；
2. 停顿翻译：（顿）→ 前/后停顿毫秒（炸点后 400-600ms、动情点后 600-800ms、章间 800-1000ms）；
3. 情感标注：抄大纲情绪坐标翻译（高位起跳→明亮有力；回落蓄力→平稳放缓；峰顶→按炸点类型；谷底→低沉克制）；
4. 情感强度克制在 0.6-0.8；情感切换粒度为「段」不为「句」；
5. 读音表：扫多音字/生僻字/专名；数字年代转口语读法；
6. 古文引文单独拆单元，标「换声线感」；（地图留白 X 秒）单元设时长目标。
铁律：只加声音指令，不改事实与措辞——读不顺的句子是写作层放水，写进「打回写作层条目」。

## 输出 Schema（只输出 JSON 对象）
{{
  "画本": [{{"段号": 1, "对应成稿段": "【段1·钩子】", "文本": "...", "拆分": ["...", "..."],
    "情感": "...", "情感强度": 0.7, "语速": 1.0, "前停顿_ms": 0, "后停顿_ms": 500,
    "读音表": {{"妺喜": "mò xǐ"}}, "时长目标_s": null, "备注": "..."}}],
  "新增读音": {{"专名": "拼音"}},
  "打回写作层条目": []
}}
"""
    user += rework_section(feedback, prev)
    return system, user, loaded