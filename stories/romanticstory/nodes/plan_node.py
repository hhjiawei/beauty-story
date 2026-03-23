import os

from deepagents import create_deep_agent
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from romanticstory.prompts.romantic_story_prompt import PLAN_SUMMARY_PROMPT
from romanticstory.tools.web_search import internet_search

"""
故事架构师的deep agent

"""

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
    tools=[internet_search],
    system_prompt=PLAN_SUMMARY_PROMPT
)

#流式输出方法（实时更新）
inputs = {"messages": [("user", """
林小满与陈阳是在城中村相依为命的临时工，她在餐馆端盘，他在工地打零工。两人挤在出租屋里，靠着微薄的薪水互相取暖，是彼此灰暗生活里唯一的光，约定攒钱转正、安稳度日。
朝夕相处中，底层的陪伴滋生出真挚的爱意，加班后的一碗热汤、发薪日的小礼物，让感情迅速升温。然而一场工地意外，陈阳双腿致残，失去劳动能力，家里的顶梁柱轰然倒塌。
医药费的重压、生活的困顿接踵而至，小满独自扛起两人的生计，日夜操劳却看不到希望。在现实的碾压下，她的坚守逐渐崩塌。面对亲戚介绍的、能给她安稳生活的男人，看着瘫痪在床、日渐消沉的陈阳，小满最终选择了妥协。她收拾行李离开出租屋，这段始于烟火、终于现实的临时工爱情，以最残酷的方式落幕，只剩两人各自背负遗憾，走向截然不同的人生。
""")]}

for msg, metadata in agent.stream(inputs, stream_mode="messages"):
    if msg.content and not isinstance(msg.content, list):
        print(msg.content, end="", flush=True)



"""
{
    "story_summary": "林小满与陈阳是蜗居城中村的临时工情侣，相依为命约定未来。陈阳工地意外双腿致残，无保险的巨额医药费压垮两人。小满日夜兼三份工仍入不敷出，在现实碾压下坚守逐渐崩塌。面对亲戚介绍的能提供安稳生活的超市老板，看着瘫痪消沉的陈阳，小满最终选择妥协离开。这段始于烟火、终于现实的爱情残酷落幕，两人各自背负遗憾走向不同人生。故事以BE结局收尾，展现底层爱情在生存压力下的脆弱与无奈。",
    "hook": "林小满收拾行李时，陈阳在隔壁房间摔碎了他们攒钱买的第一个碗。三年前他们约定要攒够钱转正结婚，现在她却要嫁给能给她安稳生活的陌生男人。",
    "core_topic": "现实向爱情/生存与爱情的残酷抉择",
    "story_backend": "现代都市背景，固定核心场景为二线城市老城区城中村'向阳村'，轻现实规则聚焦底层打工者生存现状，无复杂社会矛盾。",
    "dual_line_intersections": [
        "陈阳工地意外致残，感情危机与生计危机同时爆发",
        "小满为医药费日夜兼三份工，感情在现实压力下磨损",
        "亲戚介绍相亲对象提供稳定工作，感情与生存必须二选一"
    ],
    "three_lines_info": {
        "event_line": "起：城中村临时工情侣相依为命约定未来。承：陈阳工地意外致残，医药费压垮小满。转：小满日夜兼三份工仍入不敷出，亲戚介绍相亲对象。合：小满选择离开陈阳，嫁给能提供安稳生活的男人。",
        "emotion_line": "起：底层相濡以沫的温暖让爱升温。承：意外后小满不离不弃但现实压力让温情渐冷。转：陈阳自暴自弃，小满在疲惫绝望中动摇。合：小满选择生存而非爱情，两人最后对视爱情破碎。",
        "background_line": "起：城中村底层打工者无保障的临时工生活。承：工伤事故暴露劳动者保障缺失医疗无着。转：社会现实逼迫女性在爱情与生存间做残酷选择。合：不同阶层生活轨迹对比，底层爱情在现实前脆弱。"
    },
    "core_conflicts": [
        {"main": "贫穷与爱情的对抗——底层临时工情侣在生存压力下爱情逐渐被现实碾碎"},
        {"sub1": "意外事故带来的生存危机——陈阳工伤致残无保险，巨额医药费压垮两人"},
        {"sub2": "传统观念与现实选择的冲突——亲戚认为小满应选择稳定婚姻而非守着残疾男友"}
    ],
    "extra_plan": {
        "meet_setting": "两人在城中村同一栋出租楼租住相邻单间，因共用厨房和卫生间而相识。",
        "career_tags": "林小满：餐馆服务员月薪2800元；陈阳：建筑工地零工月薪3500元（事故前）",
        "time_place": "时间跨度2个月（从陈阳出事到小满离开），主场景：某二线城市老城区城中村'向阳村'"
    }

"""