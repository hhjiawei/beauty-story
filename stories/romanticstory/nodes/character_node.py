# romantic_story/nodes/character.py
import os

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from romanticstory.config.config import  llm
from romanticstory.prompts.romantic_story_prompt import CHARACTER_PROMPT
from romanticstory.states.romantic_story_state import MainState
import json
from langchain_core.messages import HumanMessage, SystemMessage

from utils.json_util import parse_json_response


# 策划节点，需要灵感和天马行空的设计，大模型也需要偏设计一些的 条理要清晰，要有逻辑   deepseek-reasoner

# 配置 API
OPENAI_API_KEY = "sk-0638b83c1e6a47eca1aeade34c493f6a"
OPENAI_API_BASE = "https://api.deepseek.com"
MODEL_NAME = "deepseek-reasoner"

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE

# 初始化 LLM
"""
temperature 参数默认为 1.0。

我们建议您根据如下表格，按使用场景设置 temperature。
场景	温度
代码生成/数学解题 	0.0
数据抽取/分析	1.0
通用对话	1.3
翻译	1.3
创意类写作/诗歌创作	1.5  当模型的「温度」较高时（如 0.8、1 或更高），模型会更倾向于从较多样且不同的词汇中选择，这使得生成的文本风险性更高、创意性更强，
"""
llm = ChatOpenAI(
    model=MODEL_NAME,
    temperature=1.5,
)



def character_node(state: MainState) -> dict:
    """
    人物关系部节点函数
    负责设计主角、配角等的完整档案和关系网
    """
    print("\n" + "=" * 60)
    print("[人物关系部] 开始工作")
    print("=" * 60)

    # # 构建消息
    # messages = [
    #     SystemMessage(content=CHARACTER_PROMPT),
    #     HumanMessage(content=f"""
    #     策划案设定：{json.dumps(state.get('plan_state', {}), ensure_ascii=False)}
    #     """)
    # ]
    #
    # # 调用 LLM
    # response = llm.invoke(messages)


    agent = create_deep_agent(
        model=llm,
        system_prompt=CHARACTER_PROMPT,
    )

    response = agent.invoke({"messages": [HumanMessage(content=f"""
        策划案设定：{json.dumps(state.get('plan_state', {}), ensure_ascii=False)}
        """)]})
    response = response["messages"][-1]

    # 解析 JSON 响应
    char_data = parse_json_response(response.content)

    # 构建人物关系状态对象
    character_state = {
        "characters": char_data.get("characters", []),
        "network": char_data.get("network", [])
    }

    # 打印工作日志
    print(f"[人物关系部] ✅ 完成：共设计 {len(character_state['characters'])} 个角色")
    if len(character_state['characters']) > 0:
        print(f"[人物关系部] 主角：{character_state['characters'][0]['basic']['name']}")

    # 返回状态更新
    return {"character_state": character_state}


"""

我将根据输入内容，自主设计完整的人物档案与关系网络。首先解析矛盾本质，然后推导人物设计。

Updated todo list to [
{'content': '解析矛盾本质：从输入推导main矛盾的核心机制', 'status': 'in_progress'}, 
{'content': '设计主角A（林小满）：从矛盾推导完整档案', 'status': 'pending'}, 
{'content': '设计主角B（陈阳）：从A推导形成关系互动', 'status': 'pending'},
{'content': '设计配角网络：从主线推导搅局者和助攻者', 'status': 'pending'}, 
{'content': '整合与验证：进行8项对齐检查', 'status': 'pending'}]

## 步骤1：解析矛盾本质

从输入文本分析：
- `story_summary`：反复出现的动词是"坚守"、"妥协"、"离开"、"背负"
- `core_topic`：最沉重的词是"生存"、"残酷抉择"、"现实"
- `hook`：张力来源是"收拾行李要离开" vs "摔碎第一个碗"（象征约定的破碎）
- `core_conflicts.main`：贫穷与爱情的对抗

**推导**：`conflict_essence` = "一方用承担证明爱，另一方用拒绝证明爱，形成'证明-拒绝'死锁"

具体机制：林小满通过承担一切（医药费、三份工）来证明自己的爱和责任，陈阳通过拒绝帮助（自暴自弃）来证明自己不愿拖累对方，两人都在用极端方式证明爱，却因此撕裂了关系。

Updated todo list to [
{'content': '解析矛盾本质：从输入推导main矛盾的核心机制', 'status': 'completed'}, 
{'content': '设计主角A（林小满）：从矛盾推导完整档案', 'status': 'in_progress'}, 
{'content': '设计主角B（陈阳）：从A推导形成关系互动', 'status': 'pending'}, 
{'content': '设计配角网络：从主线推导搅局者和助攻者', 'status': 'pending'}, 
{'content': '整合与验证：进行8项对齐检查', 'status': 'pending'}]

## 步骤2：设计主角A（林小满）

从`conflict_essence`中A的行为模式：用承担证明爱

**追问推导链**：
1. **恐惧**：失去什么会摧毁A？→ 失去"被需要"的价值感（如果陈阳不需要她，她的存在意义何在？）
2. **渴望**：什么能证明A的价值？→ 通过承担一切来证明自己"有用"、"不可或缺"
3. **动机**（`core_mechanism`）：为了证明自己有价值而过度承担，把责任等同于爱
4. **缺陷**（`character_flaw`）："责任成瘾"——通过不断承担更多来逃避面对关系的真实问题，用疲惫证明爱，用牺牲绑架爱
5. **特质**（`characteristics`）：主性格=坚韧务实，反差感=内心渴望被拯救却从不开口
6. **关键词**（`surface_personality`）："坚韧"、"务实"、"沉默的承担者"
7. **习惯**（`habit`）：咬下嘴唇内侧（压力时），把零钱按面额叠整齐（控制感）
8. **外貌**（`sample_character`）：右手虎口有长期端盘子留下的薄茧，眼下有熬夜打工的乌青

**必须回答**：
- 为什么是这个`flaw`？因为直接制造`conflict_essence`：她越承担，陈阳越觉得自己是负担，越要拒绝，形成死锁。
- 在`dual_line_intersections`的哪个交汇点爆发？→ 第二个交汇点"小满为医药费日夜兼三份工，感情在现实压力下磨损"：她的承担达到极限，疲惫让她无法再提供情感支持。

Updated todo list to [
{'content': '解析矛盾本质：从输入推导main矛盾的核心机制', 'status': 'completed'}, 
{'content': '设计主角A（林小满）：从矛盾推导完整档案', 'status': 'completed'}, 
{'content': '设计主角B（陈阳）：从A推导形成关系互动', 'status': 'in_progress'}, 
{'content': '设计配角网络：从主线推导搅局者和助攻者', 'status': 'pending'}, 
{'content': '整合与验证：进行8项对齐检查', 'status': 'pending'}]

## 步骤3：设计主角B（陈阳）

从A的缺陷推导B的回应方式：
- A的缺陷：责任成瘾（用承担证明爱）
- B的缺陷必须能**回应**：对抗性回应 → "尊严成瘾"（用拒绝证明爱）

**关系模式推导**：A制造"追问"（通过行动追问"我这样够不够爱你"），B制造"沉默"（通过拒绝回应"我不值得你这样爱"）→ **死锁模式**

**B的完整档案推导**：
1. **恐惧**：成为别人的负担，失去作为男人的尊严和价值
2. **渴望**：被需要但非被怜悯，被爱但非被拯救
3. **动机**：为了保护最后一点尊严而推开一切帮助
4. **缺陷**："尊严成瘾"——把接受帮助等同于失去尊严，把自暴自弃伪装成自我牺牲
5. **特质**：主性格=倔强自尊，反差感=内心渴望被拥抱却用刺猬姿态
6. **关键词**："倔强"、"自尊"、"沉默的拒绝者"
7. **习惯**：无意识地摩挲左手无名指（想戴婚戒的地方），拒绝眼神接触
8. **外貌**：事故后左腿膝盖上方有手术疤痕，右手食指有长期抽烟的焦黄

**Secret设计**：
- **内容**：陈阳在出事前三天，已经通过工友联系到一个去外地的高薪项目，准备攒够钱后正式向小满求婚。项目合同在事故中丢失，他从未告诉小满。
- **揭露节点**：对应`turning_points`节点3（小满动摇时）
- **关联**：与`background_line`的"工伤事故暴露劳动者保障缺失"同步——合同丢失象征底层劳动者权益的脆弱

**关系模式分析**：
- **pattern**："证明-拒绝死锁"
- **collision**：小满每多承担一份责任，陈阳就多一分"自己是负担"的耻辱感，于是更激烈地拒绝，让小满觉得自己的付出不被珍视
- **attraction**：两人都相信"爱需要证明"，只是证明方式相反：一个用承担，一个用拒绝
- **resolution**：死锁无法解开，最终小满选择生存，陈阳选择放手

Updated todo list to 
[{'content': '解析矛盾本质：从输入推导main矛盾的核心机制', 'status': 'completed'}, 
 {'content': '设计主角A（林小满）：从矛盾推导完整档案', 'status': 'completed'},
 {'content': '设计主角B（陈阳）：从A推导形成关系互动', 'status': 'completed'}, 
 {'content': '设计配角网络：从主线推导搅局者和助攻者', 'status': 'in_progress'},
 {'content': '整合与验证：进行8项对齐检查', 'status': 'pending'}]
 
 ## 步骤4：设计配角网络

从主线推导：

**1. 搅局者（从sub2推导）**：
- 外部压力来源：`sub2`"传统观念与现实选择的冲突——亲戚认为小满应选择稳定婚姻"
- 人物：**王姨**（小满的远房表姨）
- 动机：自身合理的恐惧/渴望 → 自己年轻时因爱情嫁错人，一生贫困，怕小满重蹈覆辙
- 功能：触发小满的缺陷爆发（"我这样承担真的值得吗？"），加剧main矛盾（提供"逃离"选项）

**2. 助攻者（从background_line推导）**：
- 信息/场景提供者：`background_line`"工伤事故暴露劳动者保障缺失医疗无着"
- 人物：**老张**（陈阳的工地工友，40多岁）
- 独立性：自己的故事线 → 同样是无保障的零工，妻子跟人跑了，独自抚养女儿
- 功能：创造A/B被迫相处的场景（帮忙送药、传话），但无法替他们解决main矛盾（他自己也无力）

**3. 压力源（从sub1推导）**：
- 外部压力来源：`sub1`"意外事故带来的生存危机——巨额医药费"
- 人物：**李医生**（医院骨科医生）
- 动机：职业责任与现实的冲突 → 同情但必须催缴医药费
- 功能：定期制造生存压力场景，让"钱"这个现实问题具象化

Updated todo list to 
[{'content': '解析矛盾本质：从输入推导main矛盾的核心机制', 'status': 'completed'}, 
 {'content': '设计主角A（林小满）：从矛盾推导完整档案', 'status': 'completed'},
 {'content': '设计主角B（陈阳）：从A推导形成关系互动', 'status': 'completed'}, 
 {'content': '设计配角网络：从主线推导搅局者和助攻者', 'status': 'completed'}, 
 {'content': '整合与验证：进行8项对齐检查', 'status': 'in_progress'}]
 
 ## 步骤5：整合与验证

**对齐验证表**：

| 验证项 | 检查方法 | 通过标准 |
|-------|---------|---------|
| 情感线对齐 | `turning_points` vs `emotion_line` | ✅ 每节点有具体触发事件：<br>1. 意外后小满不离不弃→温情渐冷<br>2. 小满兼三份工→疲惫动摇<br>3. 陈阳秘密揭露→绝望加深<br>4. 相亲出现→选择生存 |
| 事业线对齐 | `dual_line_intersections` vs 缺陷爆发场景 | ✅ 每个交汇点对应：<br>1. 意外致残→陈阳尊严成瘾爆发<br>2. 兼三份工→小满责任成瘾极限<br>3. 相亲出现→两人缺陷死锁 |
| 背景线对齐 | `secret.revealed_at` vs `background_line` | ✅ 揭露时机与"社会现实逼迫女性选择"同步 |
| 冲突对齐 | `character_flaw` vs `core_conflicts` | ✅ 缺陷直接制造`main`（责任成瘾vs尊严成瘾），回应`sub1`（医药费压力），`sub2`（传统观念） |
| 基础设定对齐 | `extra_plan` vs 人物档案 | ✅ `career_tags`直接使用，`initial_state`来自`meet_setting` |
| 职业标签化 | 全文搜索职业描写 | ✅ 无工作流程、专业技能展开 |
| 相识压缩 | 全文搜索相识描写 | ✅ 仅`meet_setting`作为背景 |
| 关系动态 | `turning_points`节点检查 | ✅ 每节点状态不同：升温→降温→质变→破碎 |

**关键问题回答**：
- 没有对方时，缺陷是否存在？→ 以不同形式存在：小满的"责任成瘾"会转向其他家人或工作，陈阳的"尊严成瘾"会表现为孤僻倔强，但无法被激活到撕裂关系的程度。

Updated todo list to [{'content': '解析矛盾本质：从输入推导main矛盾的核心机制', 'status': 'completed'}, {'content': '设计主角A（林小满）：从矛盾推导完整档案', 
'status': 'completed'}, {'content': '设计主角B（陈阳）：从A推导形成关系互动', 'status': 'completed'}, {'content': '设计配角网络：从主线推导搅局者和助攻者',
'status': 'completed'}, {'content': '整合与验证：进行8项对齐检查', 'status': 'completed'}]

## 输出：CharacterState


{
    "characters": [
        {
            "character_id": "A",
            "basic": {
                "name": "林小满",
                "age": "24",
                "sample_character": "右手虎口有长期端盘子留下的薄茧，眼下有熬夜打工的乌青",
                "career_tag": "餐馆服务员",
                "income_level": "月薪2800元",
                "habit": "压力时咬下嘴唇内侧，把零钱按面额叠整齐"
            },
            "dna": {
                "surface_personality": ["坚韧", "务实", "沉默的承担者"],
                "inner_essence": "恐惧失去被需要的价值感，渴望通过承担一切来证明自己不可或缺",
                "character_flaw": "责任成瘾——通过不断承担更多来逃避面对关系的真实问题，用疲惫证明爱，用牺牲绑架爱",
                "characteristics": "主性格=坚韧务实，反差感=内心渴望被拯救却从不开口",
                "core_mechanism": "为了证明自己有价值而过度承担，把责任等同于爱，最终在极限疲惫中选择生存"
            },
            "relationship_dynamics": {
                "initial_state": "城中村出租楼相邻单间，共用厨房卫生间相识，底层相濡以沫的温暖",
                "turning_points": [
                    "节点1：陈阳工地意外致残，小满不离不弃日夜照顾，但现实压力让温情渐冷",
                    "节点2：小满为医药费兼三份工，疲惫到在公交车上睡着坐过站，感情在磨损中动摇",
                    "节点3：陈阳秘密揭露（曾计划求婚的高薪项目合同丢失），小满意识到所有承担可能毫无意义，绝望加深",
                    "节点4：王姨介绍超市老板相亲，提供稳定工作，小满在生存与爱情间最终选择生存"
                ],
                "final_state": "离开陈阳，嫁给能提供安稳生活的男人，背负遗憾走向不同人生"
            },
            "physical_markers": [
                "右手虎口薄茧（端盘子三年）",
                "眼下乌青（熬夜兼三份工）"
            ],
            "secret": {
                "content": "小满在陈阳出事前一周，偷偷去做了婚检，一切正常。她计划等陈阳这个项目结束就提结婚，体检单一直藏在枕头下。",
                "revealed_at": "节点3",
                "connection_to_background": "与'社会现实逼迫女性在爱情与生存间做残酷选择'同步——健康证明在现实面前毫无意义"
            },
            "growth_arc": "从相信'爱就是承担一切'到明白'承担有时是逃避'，最终学会为自己生存负责，代价是永远失去爱情"
        },
        {
            "character_id": "B",
            "basic": {
                "name": "陈阳",
                "age": "26",
                "sample_character": "事故后左腿膝盖上方有手术疤痕，右手食指有长期抽烟的焦黄",
                "career_tag": "建筑工地零工",
                "income_level": "月薪3500元（事故前）",
                "habit": "无意识地摩挲左手无名指（想戴婚戒的地方），拒绝眼神接触"
            },
            "dna": {
                "surface_personality": ["倔强", "自尊", "沉默的拒绝者"],
                "inner_essence": "恐惧成为别人的负担失去尊严，渴望被需要但非被怜悯",
                "character_flaw": "尊严成瘾——把接受帮助等同于失去尊严，把自暴自弃伪装成自我牺牲，用推开证明爱",
                "characteristics": "主性格=倔强自尊，反差感=内心渴望被拥抱却用刺猬姿态",
                "core_mechanism": "为了保护最后一点尊严而推开一切帮助，最终用放手证明爱"
            },
            "relationship_dynamics": {
                "initial_state": "城中村出租楼相邻单间，因小满做饭总多带一份而走近，约定攒钱转正结婚",
                "turning_points": [
                    "节点1：工地意外双腿致残，从医院醒来第一句话是'分手吧'，开始自暴自弃",
                    "节点2：看到小满兼三份工累到睡着，故意摔碎东西制造争吵，想逼她离开",
                    "节点3：老张来探望时说出秘密（高薪项目合同丢失），被门外的小满听到",
                    "节点4：听到小满收拾行李，摔碎两人攒钱买的第一个碗，最后对视无言"
                ],
                "final_state": "独自留在城中村，背负'是我先推开她'的遗憾，在轮椅上度过余生"
            },
            "physical_markers": [
                "左腿膝盖上方手术疤痕（工伤致残）",
                "右手食指焦黄（事故后抽烟加剧）"
            ],
            "secret": {
                "content": "陈阳在出事前三天，已经通过工友联系到一个去外地的高薪项目，月薪能到8000，准备干半年就正式向小满求婚。项目合同在事故现场丢失，他从未告诉小满。",
                "revealed_at": "节点3",
                "connection_to_background": "与'工伤事故暴露劳动者保障缺失'同步——合同丢失象征底层劳动者权益的脆弱，计划永远赶不上现实"
            },
            "growth_arc": "从用'推开'保护尊严到明白'推开是最深的伤害'，最终学会真正的爱是接受自己的脆弱，但为时已晚",
            "relationship_to_a": {
                "pattern": "证明-拒绝死锁",
                "collision": "小满每多承担一份责任，陈阳就多一分'自己是负担'的耻辱感，于是更激烈地拒绝；陈阳每多一次拒绝，小满就多一分'付出不被珍视'的委屈，于是更拼命地承担",
                "attraction": "两人都深层相信'爱需要证明'，只是证明方式相反：一个用承担（'我这样够不够爱你'），一个用拒绝（'我不值得你这样爱'）",
                "resolution": "死锁无法解开，小满选择生存（离开），陈阳选择放手（沉默），爱情在现实前破碎"
            }
        }
    ],
    "network": [
        {
            "from_char": "A",
            "to_char": "B",
            "relationship": "从相濡以沫到被现实撕裂的情侣",
            "emotional_current": "想用承担靠近但先证明值得被爱，想用拒绝保护但先证明爱得深沉"
        },
        {
            "from_char": "王姨",
            "to_char": "A",
            "relationship": "远房表姨，婚姻'过来人'",
            "emotional_current": "同情但现实，'我是为你好'的压迫性关怀",
            "motivation": "自己年轻时因爱情嫁错人一生贫困，怕小满重蹈覆辙",
            "function_in_plot": "触发小满缺陷爆发（'我这样承担真的值得吗？'），提供'逃离'选项，加剧main矛盾"
        },
        {
            "from_char": "老张",
            "to_char": "B",
            "relationship": "工地工友，同样命运的底层劳动者",
            "emotional_current": "同病相怜的粗糙关怀，'男人要挺住'的无效鼓励",
            "independence": "40多岁零工，妻子跟人跑了，独自抚养读初中的女儿，自己的故事线是'下一个陈阳'"
        },
        {
            "from_char": "李医生",
            "to_char": "A",
            "relationship": "医院骨科主治医生",
            "emotional_current": "职业性同情与无奈，'我也要跟科室交代'的压力传递",
            "motivation": "职业责任与现实的冲突——同情病人但必须催缴医药费",
            "function_in_plot": "定期制造生存压力场景（催缴医药费），让'钱'这个现实问题具象化，创造A/B被迫讨论现实的场景"
        }
    ]
}
```

**推导痕迹说明**：
1. `conflict_essence`从`story_summary`的"坚守逐渐崩塌"和`hook`的"摔碎第一个碗"推导
2. 林小满的`character_flaw`从`dual_line_intersections`的"日夜兼三份工"推导
3. 陈阳的`character_flaw`从`emotion_line`的"自暴自弃"推导
4. 关系模式从两人缺陷的逻辑关系推导（承担vs拒绝）
5. 配角从`sub1`/`sub2`/`background_line`的具体压力来源推导
6. 所有`turning_points`与`emotion_line`阶段精确对应
7. `secret`揭露时机与`background_line`转折点同步
8. `career_tag`/`initial_state`直接来自输入，无添加
Process finished with exit code 0



"""
















