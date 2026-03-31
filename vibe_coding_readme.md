帮我用langgraph实现一个项目的代码，目前state已经设计完成，state部分为：
from typing import TypedDict, List, Dict, Any, Optional, Literal, NotRequired
# ----------------------------------------------------------------------
# 1. 策划层 · 故事架构师
# ----------------------------------------------------------------------

class ThreeLinesInfo(TypedDict):
    """ 三线构建  | 输出事件线、感情线、背景线的起承转合 | 每线≤200字 |"""
    event_line: str  # 主角成长轨迹（职场/生存/复仇等）
    emotion_line: str  # 感情阶段（试探→拉扯→破冰→危机→结局）
    background_line: str  # 幕后推手事件（家族/阴谋/时代）


class PlanState(TypedDict):
    """策划组输出状态"""

    # 故事摘要（800字）
    story_summary: str

    # 开篇爆点 开篇通过爆点吸引读者 通常是一句总结的、炸裂的话
    hook: str

    # 核心主题  明确小说想表达的情感内核（如双向奔赴、破镜重圆、暗恋成真、救赎、现实向爱情等）
    core_topic: str

    """
    故事背景
        时代背景：现代都市 / 民国 / 校园 / 古风（短篇选单一背景，不跨时空）
        场景背景：固定核心场景（如咖啡店、公司、校园、老街区），减少场景切换
        社会环境：轻量级现实规则（如职场压力、家庭反对、阶层差异，不写复杂社会矛盾）
    """
    story_backend: str

    #  **双线蓝图** | 明确感情线与副线（事业/生存/复仇等）的3个交汇点 | 每点≤30字
    dual_line_intersections: List[str]

    # ** 三线构建 ** | 输出事件线、感情线、背景线的起承转合 | 每线≤200字 |
    three_lines_info: ThreeLinesInfo

    # **核心矛盾** | 定义贯穿全文的1个主矛盾+2个副矛盾 | 矛盾必须可拆解为具体事件   [{main:xxx},{sub1:xxx},{sub2:xxx}]
    core_conflicts: List[Dict]


# ----------------------------------------------------------------------
# 2. 人物关系部 · 角色架构师
# ----------------------------------------------------------------------

class CharacterBasic(TypedDict):
    name: str
    age: int
    career_tag: str  # 身份职业：职场人 / 学生 / 自由职业者（贴合背景，决定行为逻辑）
    income_level: str  # 普通 / 优渥 / 清贫（影响爱情观、现实顾虑）
    habit: str  # 小癖好（喝咖啡加糖、戴旧手表、习惯性低头）

    """
        性格特质：主性格 + 反差感（如外冷内热、嘴硬心软、温柔敏感）
        原生家庭：影响爱情观的关键（缺爱→渴望安全感，强势→不懂表达）
        核心执念 / 软肋：情感痛点（怕被抛弃、不敢告白、放不下过去）
        爱情观：对感情的态度（慢热、勇敢、现实、被动）
        成长弧光：短篇需小弧光（从胆怯到勇敢，从冷漠到温柔）
        核心动机：行为驱动力（想被爱、想守护、想弥补遗憾）
    """


class CharacterDNA(TypedDict):
    surface_personality: List[str]  # 外在表现（3个关键词）
    inner_essence: str  # 内在本质（核心恐惧+核心渴望）
    character_flaw: str  # 性格缺陷（驱动冲突的关键，如：逃避型依恋） !! 重点性格描述
    characteristics: str  # 性格缺陷（驱动冲突的关键，如：逃避型依恋） !! 重点性格描述  性格特质：主性格 + 反差感（如外冷内热、嘴硬心软、温柔敏感）
    core_mechanism: str  # 核心动机：行为驱动力（想被爱、想守护、想弥补遗憾）


class RelationshipDynamics(TypedDict):
    initial_state: str  # 初始关系状态
    turning_points: List[str]  # 每章的发展状态
    final_state: str  # 最终关系状态


class CharacterProfile(TypedDict):
    character_id: str
    basic: CharacterBasic
    dna: CharacterDNA
    relationship_dynamics: RelationshipDynamics
    physical_markers: List[str]  # 身体特征状态


class NetworkNode(TypedDict):
    from_char: str
    to_char: str
    relationship: str  # 关系
    emotional_current: str  # 情感流向（如：A恨B但放不下）
    motivation: NotRequired[str]  # 仅配角需要
    independence: NotRequired[str]  # 仅助攻者需要


class CharacterState(TypedDict):
    """人物组输出状态"""
    characters: List[CharacterProfile]  # 主角配角等人物属性
    network: List[NetworkNode]  # 关系网络图


# ==========================================
# 3. 剧情策划部 · 大纲工程师 (Plot State)
# 对应章程：二 - 部门章程详解 - 【第三部门】
# ==========================================

class CharacterAction(TypedDict):
    character: str  # 具体角色
    behavior: str  # "具体行为"
    driven_by: str  # 驱动的性格缺陷
    defense_mechanism: str  # "使用的防御机制"


class ParagraphUnit(TypedDict):
    para_id: str  # 流水编号，非幕号
    character_action_list: List[CharacterAction]  # 角色行动
    climax_moment: str  # "本段高潮点（具体动作或对话）"
    resulting_state: str  # "新关系状态（输出给下一段）",
    residue_problem: str  # "遗留问题（下一段的触发器）",
    transition_design: str  # 过渡设计
    opening_hook: str  # 开篇设计
    ending_hook: str  # 结尾设计
    plot: str  # 本段大纲内容


class PlotState(TypedDict):
    beat_sheet: List[ParagraphUnit]  # 每段段情节大纲


# ==========================================
# 4. 分块写作部 · 主笔作家 (Writing State)
# 对应章程：二 - 部门章程详解 - 【第四部门】
# ==========================================

class SegmentState(TypedDict):
    para_id: str  # 段落编号
    # 段落内容
    content: str



# 主要State
class MainState(TypedDict):
    user_input: str

    plan_state: PlanState

    character_state: CharacterState

    plot_state: PlotState
    
    current_segment_index: int  # 当前段落索引 用于分段写作做计数和统计

    segments: List[SegmentState]
    


每部的相关作业完成后，将结果写入MainState对应部分，

node节点代码agent样例
import os

from deepagents import create_deep_agent
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from romanticstory.prompts.romantic_story_prompt import CHARACTER_PROMPT
from romanticstory.tools.web_search import internet_search



OPENAI_API_KEY = "sk-0638b83c1e6a47eca1aeade34c493f6a"
OPENAI_API_BASE = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"
# 设置环境变量
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE
TAVILY_API_KEY = "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"

llm = ChatOpenAI(
    model=MODEL_NAME,
)
agent = create_deep_agent(
    model=llm,
    system_prompt=CHARACTER_PROMPT
)
agent使用create_deep_agent 

思路：

每个智能体接受的信息包含 system_message以及use_message 
其中：
策划层，故事架构师 （Plan State）
    user_input
    PLAN_SUMMARY_PROMPT
人物关系部 · 角色架构师 （Character State）
    MainState.PlanState
    CHARACTER_PROMPT
剧情策划部 · 大纲工程师 (Plot State)
    MainState.PlanState
    MainState.CharacterState
    PLOT_PROMPT

分块写作部 · 主笔作家 (Writing State)
    MainState.PlotState
    WRITE_PROMPT

其中
_PROMPT为提示词
State为节点输出
所有提示词 都在目录为：romanticstory.prompts.romantic_story_prompt
例如from romanticstory.prompts.romantic_story_prompt import  PLOT_PROMPT


1 首先策划层，故事架构师做出策划内容根据用户输入和PLAN_SUMMARY_PROMPT，将结果保存到MainState.PlanState
2 然后根据策划部产生的内容（从MainState提取）和提示词CHARACTER_PROMPT 生成人物关系部 · 角色架构师的 
3 根据    MainState.PlanState MainState.CharacterState 生成PLOT_PROMPT大纲 结果保存到Plot State
4 大纲可能会划分多个段落，我需要你写一个条件node 根据大纲依次写每个段落的内容 将结果保存到MainState.segments
5 每个node都是单独的python文件


    
    
    
    
    
    
    
    
    
    
    
    
    