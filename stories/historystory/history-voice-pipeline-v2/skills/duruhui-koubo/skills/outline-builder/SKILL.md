---
name: outline-builder
description: |
  当用户要规划一篇"杜茹慧式历史口播文案"的结构/大纲时调用。
  产出固定六模块栏目骨架（钩子→铺陈→展开→反转→收束→尾声），并按人物/事件/朝代三大类套用对应变体弧光。
  适用 trigger（中英）："列大纲"/"规划结构"/"六模块怎么排"/"怎么开头结尾"/"build outline for history video"。
  不适用：已有完整初稿只需润色、或纯学术大纲。
source_book: 杜茹慧历史口播语料（93篇）
source_chapter: OUTLINE_TEMPLATE.md 综合
tags: [framework, outline, structure, planning]
related_skills: [duruhui-style, ammunition-lookup, hook-factory, technique-empathy, technique-decay, technique-scene, technique-irony]
---

# 框架 · 大纲生成（Outline Builder）

## R — 原文 (Reading)

> 已知明年就要发动灭国大战，如果你是皇帝，那么今年你要做些什么呢？……在五胡十六国时代，前秦和东晋之间，就曾经爆发了一场南北终极大战——淝水之战。……甚至我们可以粗暴地将整个前秦中央的工作高度概括为两件事……

> — 杜茹慧《两晋55·淝水之战前奏》

全篇依次：设问钩子 → 史料铺陈+降维 → 战术链展开 → 归因反转 → "自己一手酿成"收束 → 下期预告。即六模块骨架实例。

---

## I — 方法论骨架 (Interpretation)

大纲生成 = 把任意历史素材落进固定六模块 + 选对三大类变体：
- **六模块**（全篇不变）：①钩子 ②史料铺陈+降维 ③核心展开 ④高潮反转 ⑤收束升华 ⑥尾声预告（禁阴暗小故事）。
- **三大类变体**：人物（人设钩子→名场面→命运转折→盖棺）、事件（反差钩子→过程多线→反转收束）、朝代（总账钩子→枚举拆解→崩塌/转折）。

用法：先定类（人物/事件/朝代），再抄 `references/TAXONOMY.md` §3 规则卡的钩子偏向+手法组合+节奏，最后按 `references/OUTLINE_TEMPLATE.md` §5 工作表填内容。

---

## A1 — 语料中的应用 (Past Application)

### 案例：淝水之战（事件·以少胜多）大纲
- **问题**：如何规划一篇以少胜多战争的结构？
- **方法论的使用**：钩子=数字反差(8万vs97万)；铺陈=双方战前态势+史料；展开=彭城/三阿战术链；反转=前秦内乱自毁；收束=赢家未必真赢；尾声=下期预告。
- **结论**：六模块+事件类变体可直接复用。
- **结果**：该大纲跨"以少胜多战争"篇目稳定生效。

---

## A2 — 触发场景 (Future Trigger) ★

### 用户会在什么情境下需要这个 skill?
1. 拿到历史素材，不知从哪下笔、如何排结构。
2. 写好了但开头/结尾散，想对齐杜氏骨架。
3. 批量产出系列文案，需要统一结构模板。

### 语言信号
- "给我列个大纲" "怎么排结构" "六模块怎么填" "开头结尾怎么搭"

### 与相邻 skill 的区分
- 与 `duruhui-style`：本 skill 只出大纲（步骤4前置），总控负责按纲写文。
- 与 `hook-factory`：本 skill 调用 hook-factory 产①钩子，不独占钩子逻辑。

---

## E — 可执行步骤 (Execution)

1. **定类**
   - 读 `references/TAXONOMY.md` §1，选人物/事件/朝代及中类。
   - 完成标准：确定中类（如"事件·战争·以少胜多"）。
2. **抄规则卡**
   - 读 `references/TAXONOMY.md` §3，记下钩子偏向+手法组合+节奏收束。
   - 完成标准：得到该类手法组合清单。
3. **填工作表**
   - 按 `references/OUTLINE_TEMPLATE.md` §5 填：钩子句/背景/事件链(5-8点)/高潮/收束/预告 + 史料≥2 + 弹药≥6。
   - 完成标准：六模块字段齐全，弹药来自 `ammunition-lookup`。
4. **排弹药位**
   - 据 OUTLINE_TEMPLATE §4 的7位置表，把弹药标到对应模块。
   - 完成标准：每模块有标注的弹药/手法。

---

## B — 边界 (Boundary) ★

### 不要在以下情况使用
- 已有完整初稿只需润色：直接调 `duruhui-style`。
- 纯学术大纲：不需六模块栏目化与黑话布置。

### 作者暴露的失败模式
- **模块⑥写成阴暗小故事**：须只留预告，见 `duruhui-style` 清洗约束。
- **事件链平铺无高潮反转**：缺④模块反讽结构，不像杜氏。

### 容易混淆
- 普通"写作大纲"工具：缺三大类变体映射 + 弹药位置表。

---

## 相关 skills
- depends-on: [duruhui-style, ammunition-lookup, hook-factory]
- composes-with: [technique-empathy, technique-decay, technique-scene, technique-irony]

## 审计信息
- **验证通过**: V1 ✓ / V2 ✓ / V3 ✓（△ 框架类组合独特）
- **蒸馏时间**: 2026-08-24
