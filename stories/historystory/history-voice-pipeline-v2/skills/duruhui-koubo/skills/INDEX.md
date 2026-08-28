# INDEX — 杜茹慧历史口播风格 skill 包

> 本包由 cangjie-skill 流水线蒸馏自 93 篇杜茹慧历史口播语料（两晋 65 / 南北朝 23 / 晚清 5 / 隋 1）。
> 核心结论：**四把板斧跨朝代零漂移** → 任意朝代材料只换史实骨架与弹药词，不换手法引擎。

## 1. Skill 清单（8 个）

### 总控（1）
| Skill | 职责 |
|---|---|
| `duruhui-style` | 总改写引擎：定类→选手法→抽弹药→六模块写文→应用四手法→清洗 |

### 手法 skill（4）
| Skill | 手法 |
|---|---|
| `technique-empathy` | 心理代入（脑补古人内心OS） |
| `technique-decay` | 词汇降维（现代黑话嫁接古代） |
| `technique-scene` | 场景重构（细节脑补还原画面） |
| `technique-irony` | 反讽结构（预期违背/平反收束） |

### 框架 skill（3）
| Skill | 职责 |
|---|---|
| `outline-builder` | 六模块大纲 + 三大类变体 |
| `ammunition-lookup` | 弹药库检索（9 类/349 条） |
| `hook-factory` | 三类开篇钩子（设问/数字反差/迷因） |

## 2. 关系图

```
                        ┌─────────────────────┐
                        │   duruhui-style     │  (总控)
                        │   总改写引擎         │
                        └──────────┬──────────┘
              ┌────────────┬───────┼────────┬────────────┐
              ▼            ▼       ▼        ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────┐ ┌──────────┐ ┌──────────┐
       │outline-  │ │ammunition│ │hook- │ │technique-│ │technique-│
       │builder   │ │lookup    │ │factory│ │empathy   │ │decay    │
       └────┬─────┘ └────┬─────┘ └──┬───┘ └────┬─────┘ └────┬─────┘
            │           │          │          └─────┬──────┘
            │           │          │                ▼
            │           │          │         ┌──────────┐
            │           │          └────────▶│technique-│
            │           │                    │scene     │
            │           │                    └────┬─────┘
            │           │                         ▼
            │           │                 ┌──────────┐
            │           └────────────────▶│technique-│
            │                             │irony     │
            └─────────────────────────────┘
```

- `duruhui-style` **调度** 全部 7 个 skill（depends-on）。
- `outline-builder` 依赖 `ammunition-lookup` + `hook-factory`（大纲步骤3调用抽弹药、步骤1调用钩子）。
- 四手法 skill 被总控在"应用四把板斧"步骤分别调用，也可单独练习某手法。

## 3. 引用资源（安装时置于各 skill 包 `references/` 下）

| 资源 | 内容 | 被谁引用 |
|---|---|---|
| `AMMUNITION.md` | 弹药库 349 条 / 9 类 | duruhui-style, ammunition-lookup |
| `OUTLINE_TEMPLATE.md` | 六模块 + 三大类变体 + 弹药位 + 节奏曲线 | duruhui-style, outline-builder |
| `TAXONOMY.md` | 材料→手法查表（3 大类 / 16 中类） | duruhui-style, outline-builder |
| `STYLE_CORE.md` | 六手法总风格 + Boundary 清洗 | duruhui-style |
| `BOOK_OVERVIEW.md` | 整书理解（跨朝代验证） | 审计/背景 |

## 4. 典型用法

**场景 A：用户给历史素材，要改写成杜氏风格**
→ 直接调 `duruhui-style`，它自动调度 outline-builder（大纲）→ ammunition-lookup（抽弹药）→ hook-factory（钩子）→ 四手法（执行）→ 清洗。

**场景 B：用户只要某手法示例**
→ 直接调对应 `technique-*`，不触发总控。

**场景 C：用户要规划结构**
→ 调 `outline-builder`，输出六模块大纲供确认。

## 5. 验证状态
- 全部 8 个 skill 通过三重验证（V1✓/V2✓/V3✓），见 `../../verified.md`。
- 淘汰 9 项见 `../../rejected/README.md`（设问钩子/史料引用降级为组件，阴暗小故事/广告为 Boundary，反模式与术语降级）。
- 蒸馏时间：2026-08-24。
