# romantic_story/nodes/planner.py
import json
from romanticstory.config.config import get_agent
from romanticstory.prompts.romantic_story_prompt import PLAN_SUMMARY_PROMPT

from romanticstory.states.romantic_story_state import MainState


def planner_node(state: MainState) -> dict:
    """
    策划层：根据用户输入生成故事架构
    """
    user_input = state.get("user_input", "")

    # 创建 Agent
    agent = get_agent(PLAN_SUMMARY_PROMPT)

    # 构造消息 (假设 agent 接受 messages 列表)
    # 注意：根据 create_deep_agent 的具体实现，这里可能需要调整输入格式
    messages = [
        {"role": "user", "content": f"请根据以下灵感创作策划案：{user_input}"}
    ]

    response = agent.invoke(messages)

    # 解析输出 (假设 LLM 返回的是 JSON 字符串，实际需根据 Prompt 要求调整)
    # 这里需要确保解析后的字典符合 PlanState 结构
    try:
        # 如果 agent 返回的是 Message 对象，需提取 content
        content = response.content if hasattr(response, 'content') else str(response)
        plan_data = json.loads(content)
    except Exception:
        # 降级处理或抛出错误，此处为示例
        plan_data = {"story_summary": content, "hook": "", "core_topic": "", "story_backend": "",
                     "dual_line_intersections": [], "three_lines_info": {}, "core_conflicts": []}

    # 更新 State
    return {
        "plan_state": plan_data
    }


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