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

节点索引（命名即含义，2026-09-18 工序重排：弹药装配移至写作之后）：
  N1 build_n1_event_card_mining      史料分析 · 事件卡选矿   → historical-event-cards
  N3 build_n3_outline_blueprinting   大纲生成 · 蓝图绘制     → outline-architect
  N4 build_n4_chapter_construction   旁白写作 · 逐章施工     → narration-writer
     build_n4_full_script_stitch     旁白写作 · 全稿缝合     → narration-writer
  N2 build_n2_style_robe_selection   弹药装配 · 成稿装弹     → style-library
  N5 build_n5_three_gate_audit       成稿审核 · 三道门禁（含去AI味）
  N6 build_n6_storyboard_translation 画本加工 · 声音翻译

技能接口链（各节点 user 提示词已对齐 skill 契约，2026-09-18 重排）：
  N1 产出六型资料卡包（C/P/R/B/D/E，validate_cards.py 过闸）
    → N3 消费资料卡包，按「起承转合·关系驱动」大纲方法论产出《大纲包》
       ＝篇级总卡＋段落表（含情绪坐标列，相位即情绪基调）＋卡片消费闭环表
       （outline-architect，check_outline.py --cards 过闸）
    → N4 消费大纲包写**裸稿**——只管结构/事实/情绪/声口，弹药一律不碰
       （narration-writer，check_output.py 过闸）
    → N2 消费裸稿做**成稿弹药装配**——段级调度、句级作业，四步施工 SOP
       （筛句→选弹→安装→体检），三通道取弹不变，
       输出挂弹后成稿＋弹药装配报告（check_ammunition.py 过闸）
    → N5 消费挂弹后成稿过三道门禁，最后以 humanizer-zh-next 去AI味
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


# ---------------------------------------------------------------- N2 弹药装配（成稿装弹，2026-09-18 移至 N4 之后）

def build_n2_style_robe_selection(state, feedback=None, prev=None,
                                  mounted_skills=None) -> tuple[str, str, list[str]]:
    system, loaded = _system(
        "n2_style_robe_selection",
        mounted_skills or DEFAULT_SKILL_MOUNTS["n2_style_robe_selection"],
        memory_uses=["lessons", "voice_samples"],
    )
    used_cards = [c for c in state.get("event_cards", []) if c.get("本集用不用") != "不用"]
    outline_rows = [{"段号": s.get("段号"), "相位": s.get("相位"),
                     "情绪坐标": s.get("情绪坐标"), "段意": s.get("段意")}
                    for s in state.get("outline", [])]
    user = f"""## 输入：旁白成稿（被装配对象——N4 已过闸的**裸稿**：结构/事实/情绪已定稿，弹药一律未装）
{state.get("script_md", "")}

## 输入：大纲段落表（段级调度基准：相位/情绪坐标定每段的装配策略——悲悯段整段禁装）
{_j(outline_rows)}

## 输入：资料卡包（史实锚点——「先支撑后弹药」：每发弹药先找史实逻辑支撑点，再选弹药词，支撑点挂卡号）
{_j(used_cards)}

## 输入：任务参数
- 类型：{state["source_type"]}（dynasty 朝代 / person 人物 / event 事件）
- 目标时长：{state["target_minutes"]} 分钟｜第 {state["episode_no"]} 集

## 任务：按主技能（style-library）对成稿做弹药装配——「给成稿装弹」
**作业颗粒度在句、调度颗粒度在段**：逐段进入（判轨道→悲悯跳过）→ 段内逐句筛（机会扫描）→ 句级安装（原地替换）→ 段级复检（连贯+密度）。

**五步装配流水线**（全程执行）：
0. **理解内容**：通读全稿——主线/核心爽点/各段情绪轨道（对照段落表「情绪坐标」）；建立全篇弹药预算（黑话≥6 建议 8–15、代入≥3、史料≥2、反讽≥2、同词≤2）；
1. **洞察爆炸点**：以敏锐编辑之眼扫六类爆炸点（数字反差/身份倒错/伦理冲击/时代错位/命运反转/留白脑补）——「观众会截图哪一句？」至少重装 1 个；一个都锁不住则提示「成稿可能缺爆点」；
2. **语义匹配**：逐段逐句扫描弹药机会——下论断→定性机会、预期违背→反讽机会、人物纠结→心理机会、权谋操作→动作机会、需权威托底→史料机会；无机会的句子明确跳过；
3. **选词/制弹**：三通道取弹——A **查库**（优先；按需读 /references/ 对应弹药类型，先明确要什么再定位）→ B **自造**（库存没有时按 generation-rules.md 现场生成，标【自造】＋史实锚点）→ C **联网热梗**（需当期热点时按 meme-scouting.md 检索→筛选→降维改造，标检索时效）；
4. **体检**：密度红线 + 悲悯禁区 + 结构一致性 + 朗读通顺。

**四步施工 SOP**（装配动作按此顺序）：
① **筛句**：逐段标出可挂句（定性/反差/托底/梗四类机会），产出候选句清单；无机会段显式标「不装」；
② **选弹**：逐句匹配弹药类型与等级——
   - **句子级弹药**（重装，限量）：反讽结构、场景重构、类比翻译——改造整句表达形态；
   - **词级弹药**（主力）：黑话/网络梗、绰号、成语、歇后语——句内原地插入/替换；
   - **落点分级**：截图句重装、普通句轻装、悲悯句**禁装**；
   每发标史实锚点（挂卡号）与来源（库取/自造/联网）；
③ **安装**：原地替换/插入——**前后语义焊接**（弹药词与上下文声口、史实、逻辑衔接连贯），每发过**抽走测验**（抽走弹药后句子须残废，残废说明是焊进去了；不残废就改安装形态或弃弹）；句内微调允许，改写整句仅限句子级弹药；
④ **复检**：逐段通读挂弹后文本——语义通顺、声口统一（与全稿既有声口一致，不另起炉灶）、段间咬合未被破坏。

## 结构铁律（违反即打回，机检 check_ammunition.py 逐条对照）
- **只做原地词级替换与句内微调**；禁止增删句、改段序、改段标【段N·相位】；
- 禁动（顿）【上屏】（地图留白 X 秒）等技术标注；禁动古文直引原文（梗只可落在引文的白话翻译层）；
- 禁动史料事实、数字、时间点；**悲悯段（情绪坐标标悲悯者）整段禁装**——弹药/绰号/设问全清零，只许 [史料引用]；
- 字数变化控制在 ±5% 以内。

## 边界纪律（违反即打回）
- **装配器不是编辑器**：结构/事实/声口问题退回写作节点，写进「装配异议」只标注不擅自处理；
- **弹药跟内容走，不跟位置走**：没有对应内容的句子不硬装，宁缺毋滥；
- **杜撰史料引文即违规**：修辞弹药可制可造，史料引文必须真实可考，库中没有就标注缺口；
- **验梗时效**：用过气梗或气质不合的梗，尬比缺梗更伤。

## 出口硬闸门（必过）
挂弹后成稿与装配报告分别写入文件后运行检查脚本，FAIL 项修完复检，全绿才可交付：

python3 /skills/style-library/scripts/check_ammunition.py --before <裸稿.txt> --after <挂弹稿.txt> --report <装配报告.json>

## 输出 Schema（只输出一个 JSON 对象）
{{
  "挂弹后成稿": "装配后的完整成稿 Markdown（段标/技术标注/古文原文原样保留，只弹药处变化）",
  "弹药装配报告": {{
    "装配点台账": [{{ "段号": 1, "原句摘录": "...", "弹药": "...", "类型": "黑话|网络梗|绰号|成语|歇后语|反讽|史料", "等级": "句子级|词级", "来源": "库取|自造|联网", "史实锚点": "C-001", "抽走测验": "抽走后句子残废点说明" }}],
    "弹药台账": ["每发弹药：来源｜挂载位置｜史实锚点｜挂载理由"],
    "未装配说明": ["识别出但放弃装配的句子及原因（撑不起/密度满/悲悯禁区/尬）"],
    "本期语气示例": "从挂弹后成稿中挑最能代表本期声口的一句（供声口样句库沉淀）"
  }},
  "装配异议": ["对成稿结构/事实/声口的疑问，只标注不擅自处理（无则空数组）"]
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
    user = f"""## 输入：素材卡包（唯一事实来源，N1 已过闸；六型卡 C/P/R/B/D/E，卡上没有的史实一个字不许进大纲）
{_j(used_cards)}

## 输入：任务参数
- 类型：{state["source_type"]}（dynasty 朝代 / person 人物 / event 事件）｜目标时长：{state["target_minutes"]} 分钟｜第 {state["episode_no"]} 集
{f"- 上集衔接段（本篇开头要接住）：{state.get('prev_episode_bridge')}" if state.get("prev_episode_bridge") else ""}

## 任务：按主技能（outline-architect）「起承转合·关系驱动」方法论执行——本技能只产大纲，不写正文
三条铁律：**关系先于段落**（先构建四要素关系层，段落是关系的容器，大纲禁止出现无关系的素材）；**相位固定，段数弹性**（起承转合必须各出现，每相位内部段数由关系类型与意图单元推出，禁止写死段数）；**每张卡有去向**（用卡 100% 落到段落，封存卡 100% 有理由）。
- **S0 卡片清点与初筛**：按六卡型归类计数；孤证/存疑卡打标；两级判据初筛封存（①挂不上主线 ②好看但不推进论点，标去向）；缺卡预警——C 卡 <3 报「需补事件卡」、B 卡 <2 转只能选叙事转折型、D 卡 =0 宏大判断降调或标「需补数据卡」；
- **S1 关系层构建**（核心步骤，细则见 references/relationships.md）：定根（归属关系：本篇以谁为根，换主角/换朝代仍成立＝根定错）→ 列主体对（人-人/人-事/事-事/事-背景/人-物/人-背景）→ 挂关系类型（五族十一型：因果/条件潜在/递进/并列/反差/演化/镜像伏应/归属/咬合/缺口/象征，每型有操作性判定法）→ 排主线关系链；每处标「因果」的必须写得出一句机制句；主线重大因果过跨度检查（中间变量＋强度）；
- **S2 主线命题与转形态选型**：核心矛盾＝表层关系（观众以为的解释）vs 深层关系（本篇要立起的解释），两句话缺一不可；压缩成一句话主线（可证伪）——翻案型「不是【表层】，而是【深层】」／历程型「他凭什么___」；**转形态选型**：≥2 张 B 卡指向同一机制→结构归因型，B 卡不足→叙事转折型，判据写进总卡、选定不得中途换；
- **S3 四相位任务分配**（细则见 references/phase-paragraphing.md）：起承转合各写一句任务书；选起形态（**现象蒙太奇式**＝现象单元链 3–8 个递进排列→拔高定性→暗钩，顺序由递进锁死／**报幕定调式**＝反差概括→吐槽→时代一笔→预告片→报幕，预告短语须与后续分段诚实对应）与合形态（阴冷/幽默回扣/盖棺判词/远期伏笔）；**起的任务锁定为：核心矛盾的现象描述**——只呈现现象，不解释、不铺年代背景；
- **S4 分段推导与段落表填写**：逐相位按意图单元与关系类型推导段落数（一段＝一次完整的修辞动作；关系类型切换/视角切换/修辞模式切换处必须分；写不出引出方式的段＝不该存在的段）；每段必填引出方式（问答/因果/递进/镜头/时间五种，相位交界优先镜头式或问答式）与段尾欠条（本段留给下段兑现之物，全篇结束＝主线欠条还清＋开一张跨篇欠条）；思考顺序建议：先推转的骨架→再定承的峰值→再回头定制起→最后写合，输出仍按起→合排列；
- **S5 卡片消费闭环**：逐卡登记去向（段号＋用途：关系例证/数字托底/古文直引/氛围调味）；封存卡登记理由与去向；「待定」卡必须二选一，不许带出大纲阶段；
- **S6 质检**：过模板质检清单；孤证/存疑卡在备注标「存疑须声明」；D 卡全部托底具体关系；字数合计＝预算 ±10%；通读段意列自成一篇缩略论证。

## 篇幅指导（{state["target_minutes"]} 分钟 × 270 字/分钟；细则见 references/phase-paragraphing.md）
起 10%–25%（现象蒙太奇取上限，报幕定调取下限）｜承 10%–20%｜转 45%–65%｜合 5%–10%。超预算收缩顺序：先并呼吸性分段→再并同关系类型相邻段→永不并欠条关系不同的段。

## 输出纪律（字段规格以 assets/outline-template.md 为准）
- 段落表每行：段号从 1 连续递增｜相位（起/承/转/合，各相位连续成块不交错）｜段意一句话（说不清＝装了多个意图，拆段）｜关系类型（从 S1 关系链直接抄，不另发明；标「因果」处备注写机制句）｜挂卡（精确到卡号；D 卡标「托底{{哪条关系}}」，E 卡标「氛围」）｜情绪坐标（戏谑/悲悯/热血＋强度_/5，逐段必填；相位定基调，苦难/殉国/冤死段标【悲悯】——下游写作照此兑现、装配层照此设禁区）｜引出方式（首段填「—（全篇起点）」）｜段尾欠条｜预计字数｜备注（只写施工指令，禁写正文句子；古文原句照录/存疑须声明写在这里）；
- 篇级总卡：字段见输出 Schema，四相位任务连读＝全篇逻辑；封存素材两级判据（①挂不上主线 ②好看但不推进论点）标去向；
- 卡片消费闭环表：用卡 100% 入表且用途精确；段落表无凭空卡号；封存卡 100% 有理由与去向。

## 出口硬闸门（必过）
大纲与素材卡分别写入文件后运行检查脚本，FAIL 项修完复检，全绿才可交付：

python3 /skills/outline-architect/scripts/check_outline.py <大纲.md> --cards <素材卡.json> --minutes {state["target_minutes"]}

## 输出 Schema（只输出一个 JSON 对象——字段与模板一一对应，流水线只从最终答复提取 JSON）
{{
  "篇级总卡": {{
    "标题": "主推《…》；备选①《…》②《…》",
    "一句话主线": "可证伪判断；翻案型用「不是【表层】，而是【深层】」，历程型用「凭什么___」",
    "核心矛盾": "表层关系{{观众以为的解释}} vs 深层关系{{本篇要立起的解释}}",
    "叙事根": "人物名/事件名/风气名（归属判定依据）",
    "转形态": "结构归因型/叙事转折型＋判据{{B卡情况}}",
    "起形态": "现象蒙太奇式/报幕定调式",
    "合形态": "阴冷/幽默回扣/盖棺判词/远期伏笔",
    "四相位任务": "起{{一句}}｜承{{一句}}｜转{{一句}}｜合{{一句}}",
    "主线因果链": "因为…所以…最终…（重大因果逐条附：中间变量{{…}}｜强度 强/中/弱）",
    "时长与字数": "{state["target_minutes"]}分钟→{state["target_minutes"] * 270}字",
    "篇幅配比": "起__%｜承__%｜转__%｜合__%",
    "封存素材": "卡号→理由（①挂不上主线/②好看不推进）→去向；无则填「无」"
  }},
  "段落表": [
    {{ "段号": 1,
      "相位": "起",
      "段意": "一句话说清该段干什么",
      "关系类型": "递进",
      "挂卡": "C-001,C-003",
      "情绪坐标": "戏谑|悲悯|热血（强度 _/5）；苦难/殉国/冤死段标【悲悯】——相位定基调，N4 照此兑现、装配层照此设禁区",
      "引出方式": "问答/因果/递进/镜头/时间＋一句话；首段填「—（全篇起点）」",
      "段尾欠条": "本段留给下段兑现之物；末段填「跨篇欠条：{{钩}}」",
      "预计字数": 350,
      "备注": "只写施工指令（古文原句照录/存疑须声明/机制句/避坑）；禁写正文句子" }}
  ],
  "卡片消费闭环表": [
    {{ "卡号": "C-001", "卡型": "事件", "去向": "段03", "用途": "递进链第2环（例证）" }},
    {{ "卡号": "E-001", "卡型": "彩蛋", "去向": "封存", "用途": "挂不上主线，留未来篇目" }}
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
    """逐章施工 prompt（2026-09-18 工序重排：写作只产裸稿，弹药一律不碰）。
写作层职责收敛为：结构（段间咬合/欠条链）+ 事实（史料双保险）+ 情绪（照大纲情绪坐标）
+ 声口（绰号/称呼策略自建并保持全篇统一）；弹药由下游 N2 在成稿上装配，
写作时任何「弹药清单」字段都不存在，也不得为了日后好挂弹而预留生硬位置。"""
    system, loaded = _system(
        "n4_narration_construction",
        mounted_skills or DEFAULT_SKILL_MOUNTS["n4_narration_construction"],
        memory_uses=["lessons", "voice_samples"],
    )
    used_cards = [c for c in state.get("event_cards", []) if c.get("本集用不用") != "不用"]
    # N3 产出：state["outline"]＝段落表（list，含情绪坐标列，N3 直接产出）；篇级总卡在 state["theme_card"]
    outline_pack = state.get("outline", [])
    if isinstance(outline_pack, dict):  # 兼容旧 dict 包裹格式
        master_card = outline_pack.get("篇级总卡", {}) or state.get("theme_card", {})
        segment_cards = outline_pack.get("段落表", outline_pack.get("段级施工卡", []))
    else:
        master_card = state.get("theme_card", {})
        segment_cards = outline_pack
    voice_benchmark = {k: master_card.get(k, "") for k in
                       ("标题", "一句话主线", "核心矛盾", "四相位任务", "主线因果链",
                        "起形态", "合形态")}
    user = f"""## 输入：全篇大纲包（N3 已过闸直接交付：篇级总卡＋段落表——把握全局用，写作范围以本章段落为准）
{_j({"篇级总卡": master_card, "段落表": segment_cards})}

## 输入：本章段落表（本次只写这几段，逐段施工）
{_j(chapter_segments)}

## 输入：资料卡包（段内事实唯一来源——段落表引了哪张卡（挂卡列），本段就只能用哪张卡里的事实）
{_j(used_cards)}

## 输入：篇级基准（取自篇级总卡：一句话主线/核心矛盾/四相位任务/主线因果链/起形态/合形态）
{_j(voice_benchmark)}

## 输入：前一章末段（保持连贯，接口要焊住）
{prev_chapter_tail or "（本章是全篇开头，无前一章）"}

## 任务：按主技能（narration-writer）第七章「阶段零→阶段一→阶段二」逐段施工——**写裸稿，弹药一律不碰**
- **本章含第 1 段时**：先过**阶段零**（读料取证——不确定的年份/人名/官职先联网核实，取证在动笔前；按篇级总卡「一句话主线＋核心矛盾」定调）与**阶段一**（声音卡自建定稿：绰号—特征—事迹对照由本节点依史实自定、后续章节不换；签名句式只服务节奏不承担事实；朝代称呼随语境自然换用——禁用全篇统一的"我X"领属词自称；**起段按篇级总卡「起形态」施工**——现象蒙太奇式＝只呈现现象不解释、末段拔高定性＋暗钩一句带过；报幕定调式＝概括含反差、预告短语与后续段落一一对应、最后落在报幕入口）；
- **后续章节**：沿用既有声音卡，与前一章末段声口对齐，不另起炉灶、不中途改称呼策略；
- **每段过三道引擎**（顺序执行）：①心理OS与场景脑补（只填史书留白，不改史实骨架，必挂声明牌"或许/可以想象/估计"）→ ②反讽结构（材料有真实"自信→翻车"弧线才用：搭靶用当事人信息集铺到最足，亮锤最短、不加评论，锤长≤靶长1/5；搭靶段保持克制不泄压）→ ③段间咬合三问（本段凭「引出方式」承接上段什么／本段「段尾欠条」留了什么给下段／与下段怎么咬合——照段落表焊死，三问答不出回炉）；
- **每段完稿后过灵气自检**（对应主技能第五、二章）：黑名单逐句扫描命中即改；准确律——这段的灵魂钉死了吗？删掉这个比喻信息会缺损吗？情绪目标（照段落表「情绪坐标」，N3 大纲产出）兑现了吗、用哪个细节兑现的？答不出＝本段白写，回炉；
- **写的是听的**：一句一个信息、强调词在句尾、大数字先换算；（顿）标停顿位、【上屏】标引文、（地图留白 X 秒）标地图节点；每段正文开头标【段N·相位】；
- **悲悯段**（情绪坐标标悲悯者）：零梗零绰号零方言，白描 + 原文直引；进出悲悯轨必补显式过渡句；动情点前后 30 秒不玩梗；
- **史料双保险随写随做**：新时间点年号+公元双标；原文引用配白话翻译；宏大判断后跟数字或原文托底（D 卡托底优先）；**可信度纪律**：段落表备注标「存疑须声明」的卡，心理动机类内容按声明牌纪律外显（"或许/可以想象/估计"），不把推断写成事实断言；
- **零广告**：剥离一切广告植入痕迹。

## 大纲约束纪律
- **硬约束（无权改）**：史实骨架、段序与相位、挂卡范围、引出方式、段尾欠条链、悲悯段禁区、情绪坐标——有异议写进「施工异议」，只标注不擅自处理；
- 每处埋钩/兑现登记进「本章钩子台账」（埋钩位置 → 计划兑现位置，对准段落表「段尾欠条」列），供缝合节点核销。

## 输出 Schema（只输出 JSON 对象）
{{
  "本章正文": "按成稿格式写的本章 Markdown（【段N·相位】标注、（顿）/【上屏】/（地图留白 X 秒）齐全）",
  "本章钩子台账": [{{"类型": "埋钩|兑现", "内容": "...", "位置": "段N", "计划兑现位置": "段M"}}],
  "施工异议": ["对大纲的疑问，只标注不擅自处理（无则空数组）"]
}}
"""
    user += rework_section(feedback, prev)
    return system, user, loaded


def build_n4_full_script_stitch(state, chapter_drafts: list[str],
                                mounted_skills=None) -> tuple[str, str, list[str]]:
    """全稿缝合 prompt（v2 对齐 SKILL 第七章阶段三）：七任务＝缝合/朗读/双保险/逻辑核销/情绪质检/灵气质检/组装。v2 新增第6任务「灵气质检」（黑名单全文扫描/语频≤3/陌生化≤2/删无感句），自查清单 schema 补对应条目。"""
    system, loaded = _system(
        "n4_full_script_stitch",
        mounted_skills or DEFAULT_SKILL_MOUNTS["n4_narration_construction"],
        memory_uses=[],
    )
    user = f"""## 输入：各章初稿（按顺序，含各章钩子台账）
{chr(10).join(f"--- 第{i+1}章 ---{chr(10)}{d}" for i, d in enumerate(chapter_drafts))}

## 输入：全篇大纲包（N3 产出：篇级总卡＋段落表＋卡片消费闭环表；核对欠条链闭合、呼应归位、悲悯段禁区、段间咬合、存疑声明）
{_j(state.get("outline", []))}

## 任务：按主技能（narration-writer）第七章「阶段三」收尾，七任务依次执行
1. **缝合**：逐接口检查——段与段的衔接照段落表「引出方式＋段尾欠条」焊死（上段欠条＝本段首务，兑现同时开新欠条；主线按篇型缝合——{"命运感缝合" if state["source_type"] == "person" else "因果缝合"}，用上一段的余震引出下一段的地震），禁用过渡套话；绰号全篇统一（以阶段一自建声音卡为准），朝代称呼随语境自然换用、全篇多样（禁统一"我X"自称）；
2. **朗读测试**：拆读不顺的句子、断一口气读不完的句子；每 60 秒查信息/情绪增量；
3. **史料双保险复核**：每个新时间点年号+公元双标无遗漏；每处原文引用配白话翻译；每个宏大判断有数字/原文托底（对卡片消费闭环表，D 卡用途为数字托底者优先）；反常处证据链 ≥2 条、声明等级到位、备注标「存疑须声明」的卡只写"存疑"；
4. **逻辑核销**：各章钩子台账逐条核销——埋钩必兑现，兑现不了的删钩改平实表述，不许留坑；段落表「段尾欠条」链主线全部还清、跨篇欠条（钩）只此一张；设问必已回答；决策现场未混入后见之明；收尾回扣起段（起铺的现象/暗钩，合段给出定性或更深的开口，单集逻辑闭环）；
5. **情绪质检**：对照段落表「情绪坐标」（N3 大纲产出）逐段扫悲悯轨（零梗零绰号，改白描+原文直引）、轨道切换过渡句、动情点隔离区；收尾按篇级总卡「合形态」施工（定格最小单位＋甩钩过三禁），末句保留给下篇的钩；
6. **灵气质检**：黑名单全文逐句扫描零命中（不禁让人感叹/可想而知/可歌可泣/历史总是惊人的相似/震惊等）；同一连接词与"就这样"每篇≤3次；陌生化手法全篇≤2处且每处成立；**删无感句**——凡"当时觉得很好、现在无感"的比喻，按准确律重审，不准就删（本层无弹药，弹药装配由下游 N2 负责，修辞克制即美德）；
7. **成稿组装**：段号标注/【上屏】/（顿）/（地图留白 X 秒）按成稿格式收齐，广告植入痕迹全部剥离。

## 出口硬闸门（必过）
成稿与大纲分别写入文件后运行检查脚本，FAIL 项回到对应段落重写后复检，全绿才可交付：

python3 /skills/narration-writer/scripts/check_output.py <成稿.txt> --outline <大纲.txt>

## 输出 Schema（只输出 JSON 对象）
{{
  "成稿": "# 《...》旁白成稿\\n\\n> 目标时长...\\n\\n## 第一章 ...\\n（完整 Markdown）",
  "自查清单": [
    {{"item": "缝合：接口无过渡套话、绰号统一、称呼多样", "verdict": "过|不过", "location": "..."}},
    {{"item": "朗读：无拗口长句、无一口气读不完的句子", "verdict": "过|不过", "location": "..."}},
    {{"item": "双保险：年号+公元双标无遗漏/原文配译/宏大判断有托底", "verdict": "过|不过", "location": "..."}},
    {{"item": "逻辑：钩子台账全核销、设问全回答、收尾回扣开头", "verdict": "过|不过", "location": "..."}},
    {{"item": "情绪：悲悯轨零梗零绰号、切换有过渡句、隔离区干净", "verdict": "过|不过", "location": "..."}},
    {{"item": "灵气：黑名单零命中/语频≤3/陌生化≤2/抽走测验过/无感句已删", "verdict": "过|不过", "location": "..."}},
    {{"item": "组装：段标/（顿）/【上屏】/地图留白齐全、零广告", "verdict": "过|不过", "location": "..."}}
  ]
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
最后使用humanizer-zh-next技能把文章润色一遍，去掉AI味。
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

## 输入：大纲段落表（情感标注的图纸——照抄翻译；情绪坐标由 N2 挂载，相位为段落功能）
{_j([{"段号": s.get("段号"), "相位": s.get("相位"), "情绪坐标": s.get("情绪坐标")} for s in state.get("outline", [])])}

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