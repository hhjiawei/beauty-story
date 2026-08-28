# verified.md — 三重验证通过清单（阶段 1.5）

> 输入：candidates/（5 视角，共 20 条候选）。
> 验证口径：V1 跨域（≥2 独立语境佐证）/ V2 预测力（外推到书未明说场景）/ V3 独特性（非任何聪明人都能说的常识）。
> 判定符号：✓ 明确通过（独特）｜△ 边界但通过（框架类，组合独特）｜✗ 不通过（常识，降级）。
> 通过率：11/20 = 55%（符合 cangjie 30–50% 经验区间上沿，因语料风格高度密集）。

---

## f01 — 四把板斧总引擎（framework）
```yaml
id: f01
title: 四把板斧总引擎（心理代入+词汇降维+场景重构+反讽结构）
type: framework
V1_cross_domain:
  passed: true
  evidence:
    - 两晋65篇：四手法全程高频（batch-01~07）
    - 南北朝23篇：手法一致、黑话更密（batch-09/10, agent-C）
    - 晚清5篇+隋1篇：完全同构（batch-08, agent-D）
V2_predictive_power:
  passed: true
  novel_question: "用这套引擎仿写'安史之乱'会什么样？"
  derived_answer: "必现内心OS(唐玄宗后悔)+黑话嫁接(安禄山开挂)+场景重构(马嵬坡)+反讽收束(盛世崩塌)，与史实骨架无关"
V3_exclusivity:
  passed: true
  why_not_common: "单手法皆常见，但'口播史评+现代黑话嫁接+强代入+画面脑补+反转'的固定组合密度是杜氏独有指纹"
→ 进入阶段 2（核心 master skill）
```

## f02 — 六模块栏目骨架（framework）
```yaml
id: f02
title: 六模块栏目骨架（钩子→铺陈→展开→反转→收束→尾声）
type: framework
V1_cross_domain:
  passed: true
  evidence:
    - 93篇全库均呈六模块（BOOK_OVERVIEW 栏目化结论）
    - 两晋/南北朝/晚清/隋四套材料模块顺序一致（batch-08）
V2_predictive_power:
  passed: true
  novel_question: "拿到一篇'科技史'材料如何套？"
  derived_answer: "钩子立反差→史料铺陈→核心展开(多段)→反转→收束升华→下期预告，框架直接复用"
V3_exclusivity:
  passed: true  # △
  why_not_common: "结构化模板本身常识，但'固定六栏目+尾声只留预告(禁阴暗小故事)'的杜氏特定组合独特"
→ 进入阶段 2
```

## f03 — 三大类叙事变体（framework）
```yaml
id: f03
title: 三大类叙事变体（人物/事件/朝代弧光）
type: framework
V1_cross_domain:
  passed: true
  evidence:
    - 人物类：帝王/权臣/将领/后妃/门阀/士人 各有标准弧（TAXONOMY §1）
    - 事件类：战争/政变/制度/内斗/外交/风气 各规则卡（TAXONOMY §3.2）
    - 朝代类：开国/鼎盛/亡国/转折（TAXONOMY §3.3）
V2_predictive_power:
  passed: true
  novel_question: "写一篇'某科学家传记'用哪类？"
  derived_answer: "归人物类→人设钩子→名场面→命运转折→盖棺，手法组合查表即得"
V3_exclusivity:
  passed: true  # △
  why_not_common: "'按对象分类'常识，但杜氏'大类→中类→手法组合'的可查表映射 + 跨朝代稳定是独特工程化产物"
→ 进入阶段 2
```

## f04 — 弹药检索与布置位（framework）
```yaml
id: f04
title: 弹药检索与布置位（按类别抽黑话+7位置布置）
type: framework
V1_cross_domain:
  passed: true
  evidence:
    - AMMUNITION.md 349条/9类，覆盖四套材料
    - OUTLINE_TEMPLATE §4 全篇7位置布置规则（钩子/转承/心理/动作/史料/高潮/收束）
V2_predictive_power:
  passed: true
  novel_question: "写'以少胜多战争'该抽哪些弹药？"
  derived_answer: "抽'数字反差+电竞解说(丝滑连招)+史料《资治通鉴》+反讽(赢家未必赢)'，直接命中"
V3_exclusivity:
  passed: true
  why_not_common: "词库本身非独有，但'从独特弹药库按位置检索布置'的机制依赖杜氏指纹词，不可泛化"
→ 进入阶段 2
```

## f05 — 钩子工厂（framework）
```yaml
id: f05
title: 钩子工厂（设问悬念/数字反差/网络迷因破题）
type: framework
V1_cross_domain:
  passed: true
  evidence:
    - 设问钩子：多中类"开头钩子偏向"列（TAXONOMY §3）
    - 数字反差：淝水(8万vs97万)/胡马(5600万→1900万)
    - 迷因破题：魏晋风度("荒唐且美好?")/风气类
V2_predictive_power:
  passed: true
  novel_question: "写'某冷门制度'如何开篇？"
  derived_answer: "用设问('这制度为什么害死人?')或数字反差或迷因，三选一即可立住"
V3_exclusivity:
  passed: true  # △
  why_not_common: "单种钩子常识，但'三型钩子工厂+与后段手法强绑定'是杜氏开场范式"
→ 进入阶段 2（吸纳被淘汰的 CS-5 设问钩子为组件）
```

## c01 — 心理代入手法（case）
```yaml
id: c01
title: 心理代入（脑补古人内心OS）
type: case
V1_cross_domain:
  passed: true
  evidence:
    - 两晋01/06/37 高频标注（agent-A）
    - 南北朝南北01/12/19（agent-C）
    - 晚清/隋（agent-D）
V2_predictive_power:
  passed: true
  novel_question: "写'崇祯自缢'如何代入？"
  derived_answer: "脑补'他最后看一眼紫禁城，想的是祖宗还是煤山的风'——可外推"
V3_exclusivity:
  passed: true
  why_not_common: "'共情历史人物'非独有，但'口播化高强度内心OS+现代语气(他肯定想…)'的密度与口吻是杜氏标志"
→ 进入阶段 2（独立手法 skill）
```

## c02 — 词汇降维手法（case）
```yaml
id: c02
title: 词汇降维（现代黑话嫁接古代场景）
type: case
V1_cross_domain:
  passed: true
  evidence:
    - 两晋：我晋/属于是/丝滑小连招
    - 南北朝：基本盘/牛马/老影帝
    - 晚清/隋：老登/基本盘
V2_predictive_power:
  passed: true
  novel_question: "写'商鞅变法'用什么降维？"
  derived_answer: "职场/系统重装类比(系统升级BUG多)——可外推任意改革"
V3_exclusivity:
  passed: true
  why_not_common: "戏仿/混搭非新，但'史评口播+特定指纹黑话(我晋/老登/牛马)+跨朝代插槽变量'组合是杜氏最强识别符"
→ 进入阶段 2（独立手法 skill）
```

## c03 — 场景重构手法（case）
```yaml
id: c03
title: 场景重构（细节脑补还原历史画面）
type: case
V1_cross_domain:
  passed: true
  evidence:
    - 淝水前奏：战场决策链画面（agent-B）
    - 南北朝：宫廷/改革名场面（agent-C）
    - 两晋：误敲鼓/堆土山（batch）
V2_predictive_power:
  passed: true
  novel_question: "写'赤壁'如何重构？"
  derived_answer: "脑补'东南风起时黄盖船头的火把、曹操舰队的铁链声'——可外推"
V3_exclusivity:
  passed: true
  why_not_common: "'show don't tell'常识，但'口播史评中高密度具象脑补+动作细节(误敲鼓)'是杜氏画面感来源"
→ 进入阶段 2（独立手法 skill）
```

## c04 — 反讽结构手法（case）
```yaml
id: c04
title: 反讽结构（预期违背/平反式收束）
type: case
V1_cross_domain:
  passed: true
  evidence:
    - 两晋：清君侧只是清君侧/赢家未必真赢
    - 南北朝：平反式收束
    - 晚清/隋：衰世反讽
V2_predictive_power:
  passed: true
  novel_question: "写'王安石变法失败'如何反讽？"
  derived_answer: "收束'他想要的强国，恰恰被自己最狠的法条推向反面'——可外推"
V3_exclusivity:
  passed: true
  why_not_common: "反讽修辞常识，但'史评口播中作为固定收束机制+与史料托底绑定'是杜氏标志"
→ 进入阶段 2（独立手法 skill）
```

## p01 — 史料托底原则（principle）
```yaml
id: p01
title: 史料托底原则（黑话需史料权威托底，≥2条）
type: principle
V1_cross_domain:
  passed: true
  evidence:
    - STYLE_CORE Boundary
    - TAXONOMY §4"黑话需史料权威托底"
    - techniques 各篇史料引用标注
V2_predictive_power:
  passed: true
  novel_question: "通篇用黑话无史料会怎样？"
  derived_answer: "降为段子/脱口秀，失'杜味'权威感——可预测"
V3_exclusivity:
  passed: true  # △
  why_not_common: "'要引证据'常识，但'杜氏特定强度配比(黑话表层+史料地基，每篇≥2)'是工程化约束非泛泛建议"
→ 进入阶段 2（吸纳被淘汰的 CS-6 史料引用为组件）
```

## p03 — 反转必需原则（principle）
```yaml
id: p03
title: 反转必需原则（高潮处必有反讽结构）
type: principle
V1_cross_domain:
  passed: true
  evidence:
    - STYLE_CORE 反讽结构手法
    - BOOK_OVERVIEW 反转/反讽收束结论
    - 93篇高潮处普遍反讽
V2_predictive_power:
  passed: true
  novel_question: "一篇无反转会如何判定？"
  derived_answer: "判定为'特征缺失/不像杜氏'——可预测质检"
V3_exclusivity:
  passed: true  # △
  why_not_common: "'要有转折'常识，但'作为硬性质检红线(无反转=不像)'是杜氏风格工程化要求"
→ 进入阶段 2
```

---

## 阶段 2 将构造的 skill 映射
| verified id | 阶段2 skill 文件 | 类型 |
|---|---|---|
| f01 | SKILL.md（master 总控，含四把板斧+六模块+清洗） | 总控 |
| f02 | outline-builder/SKILL.md（六模块骨架） | 框架 |
| f03 | outline-builder/SKILL.md（三大类变体，合并入大纲） | 框架 |
| f04 | ammunition-lookup/SKILL.md（弹药检索布置） | 框架 |
| f05 | hook-factory/SKILL.md（钩子工厂，含设问） | 框架 |
| c01 | technique-empathy/SKILL.md | 手法 |
| c02 | technique-decay/SKILL.md（词汇降维） | 手法 |
| c03 | technique-scene/SKILL.md（场景重构） | 手法 |
| c04 | technique-irony/SKILL.md（反讽结构） | 手法 |
| p01 | 并入 master 总控（考据托底约束，含史料引用） | 原则 |
| p03 | 并入 master 总控（反转红线质检） | 原则 |

> 注：CS-5 设问钩子、CS-6 史料引用 因 V3 不通过（常识）未独立成 skill，分别降级为 f05 / p01 的内部组件。
