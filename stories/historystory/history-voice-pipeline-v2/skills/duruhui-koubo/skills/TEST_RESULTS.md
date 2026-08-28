# TEST_RESULTS — 压力测试（阶段 4）

> 测试对象：8 个 skill（duruhui-style + 4 手法 + 3 框架）。
> 测试格式：darwin 兼容 `test-prompts.json`（should_trigger / should_not_trigger 诱饵 / edge_case，诱饵含跨 skill 混淆）。
> **测试模式：主流程自测 fallback** —— 本环境 sub-agent 触发频率限制（429），按 methodology/06 第 24 行允许的 fallback 执行：基于各 skill `description`(A2 trigger) 与 test_cases `expected_behavior` 逐条比对判定 `would_trigger`。
> ⚠️ 可信度说明：独立 sub-agent 盲测可信度高于主流程自测；本结果用于"trigger 描述自洽性"检查，正式部署前建议补一轮独立盲测。

## 判卷规则
- `should_trigger`：prompt 含风格化/仿写/加手法/列大纲/抽弹药/设钩子信号 → `would_trigger=true` → pass。
- `should_not_trigger`（普通诱饵）：纯信息查询 → `would_trigger=false` → pass。
- `should_not_trigger`（跨 skill 混淆）：应触发**兄弟 skill**（如整篇改写归 `duruhui-style` 总控）→ 对本 skill `would_trigger=false` → pass。
- `edge_case`：边界场景，判定须符合 `expected_behavior` 的边界理由 → pass。

## 逐 skill 结果

### duruhui-style（总控）
| case | type | would_trigger | pass |
|---|---|---|---|
| should-01 安史之乱口播 | should | true | ✅ |
| should-02 王莽篡汉改写 | should | true | ✅ |
| should-03 靖难之役仿写 | should | true | ✅ |
| not-01 查《资治通鉴》年份 | not | false | ✅ |
| not-02 产品发布会幽默开场 | not(跨) | false（应触发通用幽默skill） | ✅ |
| edge-01 学术魏晋论文 | edge | false | ✅ |
**通过率 6/6**

### technique-empathy
| case | type | would_trigger | pass |
|---|---|---|---|
| should-01 崇祯心理描写 | should | true | ✅ |
| should-02 加心理代入 | should | true | ✅ |
| should-03 苻坚兵败所想 | should | true | ✅ |
| not-01 文言文翻译 | not | false | ✅ |
| not-02 写整篇安史之乱 | not(跨) | false（归总控） | ✅ |
| edge-01 学术传记心理 | edge | false（克制） | ✅ |
**通过率 6/6**

### technique-decay
| case | type | would_trigger | pass |
|---|---|---|---|
| should-01 商鞅变法现代梗 | should | true | ✅ |
| should-02 玄武门加黑话 | should | true | ✅ |
| should-03 三国网络语 | should | true | ✅ |
| not-01 解释商鞅变法 | not | false | ✅ |
| not-02 写整篇商鞅变法 | not(跨) | false（归总控） | ✅ |
| edge-01 青少年普及读物 | edge | false（少量可） | ✅ |
**通过率 6/6**

### technique-scene
| case | type | would_trigger | pass |
|---|---|---|---|
| should-01 赤壁火攻分镜 | should | true | ✅ |
| should-02 土木堡还原 | should | true | ✅ |
| should-03 淝水动作链 | should | true | ✅ |
| not-01 赤壁哪年 | not | false | ✅ |
| not-02 写整篇赤壁 | not(跨) | false（归总控） | ✅ |
| edge-01 教科书战役描述 | edge | false | ✅ |
**通过率 6/6**

### technique-irony
| case | type | would_trigger | pass |
|---|---|---|---|
| should-01 项羽反转收尾 | should | true | ✅ |
| should-02 秦桧平反 | should | true | ✅ |
| should-03 归因反转 | should | true | ✅ |
| not-01 项羽介绍 | not | false | ✅ |
| not-02 写整篇项羽 | not(跨) | false（归总控） | ✅ |
| edge-01 客观不评价 | edge | false | ✅ |
**通过率 6/6**

### outline-builder
| case | type | would_trigger | pass |
|---|---|---|---|
| should-01 安史之乱列大纲 | should | true | ✅ |
| should-02 商鞅变法归事件类 | should | true | ✅ |
| should-03 刘裕人物类大纲 | should | true | ✅ |
| not-01 安史之乱讲啥 | not | false | ✅ |
| not-02 写整篇安史之乱 | not(跨) | false（归总控写文） | ✅ |
| edge-01 已有初稿润色 | edge | false（直接总控） | ✅ |
**通过率 6/6**

### ammunition-lookup
| case | type | would_trigger | pass |
|---|---|---|---|
| should-01 以少胜多抽弹药 | should | true | ✅ |
| should-02 隋朝老登替换 | should | true | ✅ |
| should-03 暴君类弹药 | should | true | ✅ |
| not-01 基本盘啥意思 | not | false | ✅ |
| not-02 写整篇暴君 | not(跨) | false（归总控） | ✅ |
| edge-01 学术论文引黑话 | edge | false | ✅ |
**通过率 6/6**

### hook-factory
| case | type | would_trigger | pass |
|---|---|---|---|
| should-01 赤壁钩子 | should | true | ✅ |
| should-02 迷因破题 | should | true | ✅ |
| should-03 崇祯设问钩子 | should | true | ✅ |
| not-01 赤壁导火索 | not | false | ✅ |
| not-02 写整篇赤壁 | not(跨) | false（归总控） | ✅ |
| edge-01 学术引言钩子 | edge | false | ✅ |
**通过率 6/6**

## 汇总
- **总通过率：48/48 = 100%**（主流程自测 fallback）。
- **跨 skill 混淆诱饵**：8 条全部正确"不抢调用"，整篇改写类 prompt 稳定归 `duruhui-style` 总控，单手法/框架 skill 不越界——符合 methodology/06 第 68 行硬性要求。
- **诱饵容错**：0 误触发。
- **结论**：所有 skill trigger 描述自洽，接受进入阶段 5（交付）。建议正式部署前补独立 sub-agent 盲测一轮以达最高可信度。

## 回炉记录
- 无回炉：未出现 <80% 通过项，无需重做阶段 2。
