"""
==========================================================================
 prompts.py —— 流水线全部节点 Prompt 集中管理文件
==========================================================================

设计契约（执行方案 §5.3 人格三层 + §4 各节点职责）：

- 每个 builder 返回 (system, user) 二元组；
- system = 节点标记 + 人格 L1 常驻前缀（persona-writer 全文）
         + 节点主技能全文 + references 技能 + 人格 L2 系列记忆；
- user   = 节点输入契约（PipelineState 字段子集）+ 输出 Schema
         + 打回意见段（重跑时注入，「按条目修改，不重写全文」）；
- system 第一行固定为 <!-- NODE:节点id --> 标记：
  ① MockLLM 据此路由（测试/演示）② 节点日志可审计。

节点索引（命名即含义）：
  N1 build_n1_event_card_mining      史料分析 · 事件卡选矿
  N2 build_n2_style_robe_selection   风格选定 · 本期外衣
  N3 build_n3_outline_blueprinting   大纲生成 · 蓝图绘制
  N4 build_n4_chapter_construction   旁白写作 · 逐章施工
     build_n4_full_script_stitch     旁白写作 · 全稿缝合
  N5 build_n5_three_gate_audit       成稿审核 · 三道门禁
  N6 build_n6_storyboard_translation 画本加工 · 声音翻译
==========================================================================
"""
from __future__ import annotations

import json

from . import memory_store
from .skills_loader import load_skill

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


def _system(node_marker: str, main_skill: str, references: list[str],
            memory_uses: list[str]) -> tuple[str, list[str]]:
    parts = [
        f"<!-- NODE:{node_marker} -->",
        "# 人格层（L1 常驻，你的操作系统）\n" + persona_prefix(),
    ]
    if main_skill:
        parts.append("# 本节点主技能（你的工种手册）\n" + load_skill(main_skill))
    for ref in references:
        parts.append(f"# 参考技能：{ref}（按需查阅）\n" + load_skill(ref))
    mem_txt, loaded = series_memory_section(memory_uses)
    if mem_txt:
        parts.append(mem_txt)
    return "\n\n---\n\n".join(parts), loaded


# ---------------------------------------------------------------- N1 史料分析

def build_n1_event_card_mining(state, feedback=None, prev=None) -> tuple[str, str, list[str]]:
    system, loaded = _system(
        "n1_event_card_mining",
        main_skill="historical-event-cards",
        references=[],
        memory_uses=["lessons"],
    )
    user = f"""## 输入：任务信息
- 史料类型：{state["source_type"]}（dynasty 朝代 / person 人物 / event 事件）
- 目标时长：{state["target_minutes"]} 分钟
- 集次：第 {state["episode_no"]} 集
{f"- 上集衔接段：{state.get('prev_episode_bridge')}" if state.get("prev_episode_bridge") else ""}

## 输入：史料原文
{state["source_text"]}

## 任务
按主技能 schema 把史料拆成事件卡清单，并完成弹药的「选矿」工序：
每张卡标注弹药潜质（钩子/炸点/动情点/对照组/知识彩蛋/无）。
{"人物篇：额外标注人生阶段与最颠覆印象度评分。" if state["source_type"] == "person" else ""}
{"事件篇：额外标注因果链位置与主线变体预判。" if state["source_type"] == "event" else ""}

## 输出
只输出一个 JSON 数组（不要任何解释文字），元素为事件卡对象。
"""
    user += rework_section(feedback, prev)
    return system, user, loaded


# ---------------------------------------------------------------- N2 风格选定

def build_n2_style_robe_selection(state, feedback=None, prev=None) -> tuple[str, str, list[str]]:
    system, loaded = _system(
        "n2_style_robe_selection",
        main_skill="style-library",
        references=["persona-writer"],
        memory_uses=["lessons", "voice_samples"],
    )
    cards_brief = [
        {"卡号": c.get("卡号"), "冲突": c.get("冲突"), "弹药潜质": c.get("弹药潜质")}
        for c in state.get("event_cards", []) if c.get("本集用不用") != "不用"
    ]
    user = f"""## 输入：本集素材摘要（事件卡·选矿结果）
{_j(cards_brief)}

## 任务：选衣（一件衣穿一整期）
1. 评估三维坐标：知识密度 / 情感深度 / 娱乐强度（各 1-5 分）；
2. 查「人物类型 × 推荐风格」决策矩阵；
3. 推荐 1-2 种主风格，给出推荐理由 + 该风格 3-5 个核心技巧；
4. 每种候选给出一句「本期语气示例」（将作为写作层定声口的对齐基准）。

## 输出 Schema（只输出 JSON 对象）
{{
  "三维坐标": {{"知识密度": 4, "情感深度": 3, "娱乐强度": 4, "评估理由": "..."}},
  "候选风格": [
    {{
      "风格名": "...",
      "核心气质": "...",
      "推荐理由": "...",
      "核心技巧": ["...", "..."],
      "本期语气示例": "..."
    }}
  ]
}}
"""
    user += rework_section(feedback, prev)
    return system, user, loaded


# ---------------------------------------------------------------- N3 大纲生成

def build_n3_outline_blueprinting(state, feedback=None, prev=None) -> tuple[str, str, list[str]]:
    system, loaded = _system(
        "n3_outline_blueprinting",
        main_skill="outline-architect",
        references=["ammo-depot"],
        memory_uses=["lessons"],
    )
    used_cards = [c for c in state.get("event_cards", []) if c.get("本集用不用") != "不用"]
    user = f"""## 输入：事件卡（唯一事实来源）
{_j(used_cards)}

## 输入：本期外衣（人工拍板）
{_j(state.get("style_card", {}))}

## 输入：任务参数
- 类型：{state["source_type"]}｜目标时长：{state["target_minutes"]} 分钟｜第 {state["episode_no"]} 集
{f"- 上集衔接段（本集开头要接住）：{state.get('prev_episode_bridge')}" if state.get("prev_episode_bridge") else ""}

## 任务：九步 SOP
Step 0 认知入口（无反差不强行）→ Step 1 已在 N1 完成（直接用上方事件卡）
→ Step 2 一句话主题 + 主题自检三问 + 钩子选型 → Step 3 节点分级
→ Step 4 三个非线性动作 → Step 5 技法主/备选型 → Step 6 炸点+情绪波形+动情点
→ Step 7 伏笔登记 → Step 8 举证式签发清单。

## 输出 Schema（只输出一个 JSON 对象）
{{
  "主题卡": {{
    "一句话主题": "...",
    "钩子选型": "反常切片|反差量化|名场面前置|颠覆细节|...",
    "钩子那一帧": "开场具体画面/事实",
    "主题自检三问": {{"哦一声了吗": "...", "只有你能讲吗": "...", "换主语还成立吗": "..."}}
  }},
  "单集大纲文件": [{{"段号": 1, "时间码": "...", "功能类型": "...", "章节标题": "...",
    "使用史料卡": ["C-001"], "指定技法": "主：...；备选：...", "炸点": "类型+位置+史料卡出处 或 null",
    "动情点": "有/无+位置 或 null", "伏笔": "埋设/回收/无", "情绪坐标": "...",
    "预计字数": "60（容差 ±40%）", "备注": "..."}}],
  "伏笔登记表": [{{"伏笔": "...", "埋设段": 1, "回收段": 8, "状态": "待收"}}],
  "签发清单": [{{"item": "检查项", "verdict": "过|不过", "location": "大纲中的具体位置"}}]
}}

## 弹药纪律（本节点是「配弹」工序）
- 每个炸点必须挂史料卡出处，无卡炸点一票退回；
- 炸点数量按 {state["target_minutes"]} 分钟换算区间执行，区间是上限不是 KPI；
- 动情点全片至少一处，找不到 → 大纲退回；
- 插件数量在纪律内（引文 3-5 处、历史对照组 ≤1、对勘 ≤1、盖牌 ≤1）。
"""
    user += rework_section(feedback, prev)
    return system, user, loaded


# ---------------------------------------------------------------- N4 旁白写作

def build_n4_chapter_construction(state, chapter_segments: list[dict],
                                  prev_chapter_tail: str | None,
                                  feedback=None, prev=None) -> tuple[str, str, list[str]]:
    """逐章施工 prompt。每章携带：前一章末段 + 全篇大纲 + 声口样句（长文连贯三件套）。"""
    system, loaded = _system(
        "n4_narration_construction",
        main_skill="narration-writer",
        references=["style-library", "ammo-depot"],
        memory_uses=["lessons", "voice_samples"],
    )
    used_cards = [c for c in state.get("event_cards", []) if c.get("本集用不用") != "不用"]
    user = f"""## 输入：全篇大纲（硬约束无权改，软约束可调须声明）
{_j(state.get("outline", []))}

## 输入：本章施工段落（本次只写这几段）
{_j(chapter_segments)}

## 输入：事件卡（段内事实唯一来源——大纲引了哪张卡，本段就只能用哪张卡里的事实）
{_j(used_cards)}

## 输入：本期外衣与声口
{_j(state.get("style_card", {}))}

## 输入：前一章末段（保持连贯，接口要焊住）
{prev_chapter_tail or "（本章是全篇开头，无前一章）"}

## 任务
按写作层 SOP 逐段施工：功能查 → 字数查（分级容差）→ 技法查（第六节对照表）
→ 炸点/伏笔查。写的是听的：一句一个信息、强调词在句尾、大数字先换算、
（顿）标停顿位、【上屏】标引文、（地图留白 X 秒）标地图节点。

## 输出 Schema（只输出 JSON 对象）
{{
  "本章正文": "按成稿格式写的本章 Markdown（【段N·功能类型】标注齐全）",
  "技法切换声明": ["段N 技法：主→备（如有，无则空数组）"],
  "施工异议": ["对大纲的疑问，只标注不擅自处理（无则空数组）"]
}}
"""
    user += rework_section(feedback, prev)
    return system, user, loaded


def build_n4_full_script_stitch(state, chapter_drafts: list[str]) -> tuple[str, str, list[str]]:
    """全稿缝合 prompt：焊缝隙 + 朗读测试修订 + 成稿组装 + 自查签发。"""
    system, loaded = _system(
        "n4_full_script_stitch",
        main_skill="narration-writer",
        references=[],
        memory_uses=[],
    )
    user = f"""## 输入：各章初稿（按顺序）
{chr(10).join(f"--- 第{i+1}章 ---{chr(10)}{d}" for i, d in enumerate(chapter_drafts))}

## 输入：全篇大纲（缝合时核对伏笔埋收、呼应归位）
{_j(state.get("outline", []))}

## 任务：Step 4-7
1. 缝合：逐接口检查——主线按篇型缝合（{"命运感缝合" if state["source_type"] == "person" else "因果缝合"}），
   插件进出用挂接句，禁用过渡套话；
2. 朗读测试：拆读不顺的句子、断一口气读不完的句子、每 60 秒查信息/情绪增量；
3. 成稿组装：按写作层第八节 schema（段号标注/【上屏】/（顿）/（地图留白 X 秒））；
4. 自查签发：过第九节自查清单，逐项举证。

## 输出 Schema（只输出 JSON 对象）
{{
  "成稿": "# 《...》旁白成稿\n\n> 目标时长...\n\n## 第一章 ...\n（完整 Markdown）",
  "自查清单": [{{"item": "...", "verdict": "过|不过", "location": "..."}}]
}}
"""
    return system, user, loaded


# ---------------------------------------------------------------- N5 成稿审核

def build_n5_three_gate_audit(state, scan_findings: dict) -> tuple[str, str, list[str]]:
    system, loaded = _system(
        "n5_three_gate_audit",
        main_skill="narration-auditor",
        references=["persona-writer", "narration-writer"],
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
                                    feedback=None, prev=None) -> tuple[str, str, list[str]]:
    system, loaded = _system(
        "n6_storyboard_translation",
        main_skill="tts-script-doctor",
        references=[],
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
