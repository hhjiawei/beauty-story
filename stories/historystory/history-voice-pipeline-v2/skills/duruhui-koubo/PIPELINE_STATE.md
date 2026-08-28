# PIPELINE_STATE — duruhui-koubo

## 当前阶段：✅ 全部完成（2026-08-24）

## 语料
- 路径：`D:/ds-work/finish/`（93 篇，清单见 `corpus-manifest.txt`）
- 系列分布：两晋 65 / 衣冠南北(南北朝) 23 / 千年变局(晚清) 5 / 大隋 1

## 进度 checklist（全绿）
- [x] 任务 001：全语料通读 + BOOK_OVERVIEW（确认点 1 ✅）
- [x] 任务 002：digest 机械提取 → `notes/digest-01~05.md`（93 篇 6 维全覆盖）
- [x] 任务 003：TAXONOMY.md（3 大类 / 16 中类 / 93 篇归类 + §3 规则）✅ 确认点 2
- [x] 任务 004：techniques/agent-A~D.md（10 篇精读 + 理论溯源）
- [x] 任务 005：AMMUNITION.md（349 条 / 9 类）
- [x] 任务 006：STYLE_CORE.md（六手法总风格）
- [x] 任务 007：OUTLINE_TEMPLATE.md（六模块 + 三大类变体 + 弹药位 + 节奏曲线）
- [x] 任务 008：candidates/(5 视角) + verified.md(11 通过) + rejected/(9 淘汰) ✅ 确认点 3
- [x] 任务 009：8 个 skill（RIA++ 六段）+ test-prompts(darwin) + INDEX.md + GLOSSARY.md
- [x] 任务 010：压力测试(TEST_RESULTS 48/48) + DIGEST.md + 安装 + 盲测终验(blind-test.md)

## 交付物位置
- **已安装 skill**（用户级，全局可用）：`C:\Users\胡佳伟01\.workbuddy\skills\`
  - `duruhui-style`（总控）/ `technique-empathy` / `technique-decay` / `technique-scene` / `technique-irony` / `outline-builder` / `ammunition-lookup` / `hook-factory`
  - 每个含 SKILL.md + test-prompts.json + references/(AMMUNITION/OUTLINE/TAXONOMY/STYLE_CORE/BOOK_OVERVIEW)
- **构建产物**（books/duruhui-koubo/）：BOOK_OVERVIEW / TAXONOMY / AMMUNITION / STYLE_CORE / OUTLINE_TEMPLATE / verified / rejected / candidates / DIGEST.md / blind-test.md / skills/INDEX.md / skills/GLOSSARY.md

## 关键结论
- **四把板斧跨朝代零漂移**：心理代入/词汇降维/场景重构/反讽结构 + 设问 + 史料，在两晋/南北朝/晚清/隋四套材料完全同构 → 支撑"仿写任意朝代"。
- **盲测终验通过**：唐·安史之乱仿写稿（blind-test.md）有"杜味"、清洗生效（无阴暗小故事/广告/自我介绍）。
- **压力测试**：48/48 通过（主流程自测 fallback，建议部署前补独立 sub-agent 盲测）。

## 下一步
用户可直接调用 `duruhui-style`（给历史素材→改写成杜氏风格），或单调用某 `technique-*` 练手法。如需持续进化，用 `darwin evolve books/duruhui-koubo/` 基于 test-prompts.json 做 ratcheting。
