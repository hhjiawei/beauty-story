"""
剧情策划部节点
规划 6000 字情绪曲线、爽点分布、时间地点流程
整合前期所有部门信息，消除信息孤岛
支持根据连贯性检测的返修意见重新设计大纲
"""
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_PLOT_PLANNER
from config.config import llm_default



def parse_json_response(content: str) -> dict:
    """
    解析 LLM 的 JSON 响应

    Args:
        content: LLM 返回的内容

    Returns:
        解析后的字典
    """
    try:
        # 清理 Markdown 代码块标记
        content = content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        content = content.strip()

        # 解析 JSON
        return json.loads(content)
    except Exception as e:
        print(f"[JSON 解析错误] {e}")
        return {}


def build_world_building_context(state: MainState) -> dict:
    """从世界观设定部提取关键信息"""
    world = state.get("world_building", {})
    return {
        "apocalypse_name": world.get("apocalypse_name", "未知末日"),
        "apocalypse_source": world.get("apocalypse_source", "")[:300],
        "outbreak_date": world.get("outbreak_date", "未指定"),
        "key_locations": [loc.get("name", "") for loc in world.get("key_locations", [])],
        "special_rules": world.get("special_rules", "")[:200],
    }


def build_golden_finger_context(state: MainState) -> dict:
    """从金手指设计部提取关键信息"""
    gf = state.get("golden_finger", {})
    return {
        "ability_type": gf.get("ability_type", "未知"),
        "activation_condition": gf.get("activation_condition", "")[:100],
        "functions": gf.get("functions", []),
        "limitations": gf.get("limitations", "")[:200],
        "revenge_advantages": gf.get("revenge_advantages", []),
    }


def build_character_context(state: MainState) -> dict:
    """从人物关系部提取关键信息"""
    char = state.get("character", {})
    protagonist = char.get("protagonist", {})
    villains = char.get("villains", [])
    allies = char.get("allies", [])

    # 格式化仇人信息
    villains_info = ""
    villains_names = []
    villains_weaknesses = []
    for i, v in enumerate(villains, 1):
        name = v.get('name', '未知')
        villains_names.append(name)
        villains_weaknesses.append(v.get('weakness', '无'))
        villains_info += f"  {i}. {name}（{v.get('relationship', '未知')}）\n"
        villains_info += f"     弱点：{v.get('weakness', '无')}\n"
        villains_info += f"     前世背叛：{v.get('betrayal_info', {}).get('action', '未知')[:50]}...\n"
        villains_info += f"     今生结局：{v.get('fate', '未知')}\n\n"

    # 格式化盟友信息
    allies_info = ""
    for i, a in enumerate(allies, 1):
        allies_info += f"  {i}. {a.get('name', '未知')}（{a.get('relationship', '未知')}）\n"
        allies_info += f"     价值：{a.get('value', '无')}\n\n"

    # 获取关键地点用于高潮场景
    key_locations = state.get("world_building", {}).get("key_locations", [])
    key_location_climax = key_locations[2].get("name", "未指定") if len(key_locations) > 2 else "未指定"

    return {
        "protagonist_name": protagonist.get("name", "未知"),
        "protagonist_age": protagonist.get("age", 0),
        "protagonist_profession": protagonist.get("profession", "未知"),
        "protagonist_personality": protagonist.get("personality", []),
        "death_info": protagonist.get("death_info", {}),
        "rebirth_time": protagonist.get("rebirth_info", {}).get("time", "未指定"),
        "villains_info": villains_info,
        "villains_names": villains_names,
        "villains_weaknesses": villains_weaknesses,
        "allies_info": allies_info,
        "key_location_climax": key_location_climax,
    }


def get_revision_feedback(state: MainState) -> dict:
    """
    获取连贯性检测的返修意见（如果有）

    Args:
        state: 主状态对象

    Returns:
        返修意见字典
    """
    plot_continuity_report = state.get("plot_continuity_report", {})

    # 检查是否有返修意见
    if not plot_continuity_report:
        return {
            "has_feedback": False,
            "feedback": "",
            "must_fix_issues": [],
            "total_score": 0
        }

    overall_status = plot_continuity_report.get("overall_status", "FAIL")
    total_score = plot_continuity_report.get("total_score", 0)
    must_fix_issues = plot_continuity_report.get("must_fix_issues", [])
    feedback = plot_continuity_report.get("feedback", "")

    # 只有当状态为 FAIL 或有必须修复的问题时，才视为有返修意见
    has_feedback = (overall_status == "FAIL" or len(must_fix_issues) > 0)

    return {
        "has_feedback": has_feedback,
        "feedback": feedback,
        "must_fix_issues": must_fix_issues,
        "total_score": total_score,
        "time_issues": plot_continuity_report.get("time_continuity", {}).get("issues", []),
        "location_issues": plot_continuity_report.get("location_continuity", {}).get("issues", []),
        "character_issues": plot_continuity_report.get("character_continuity", {}).get("issues", []),
        "plot_logic_issues": plot_continuity_report.get("plot_logic", {}).get("issues", []),
    }


def plot_planner_node(state: MainState) -> dict:
    """
    剧情策划部节点函数 - 整合所有前期信息，支持返修意见

    Args:
        state: 主状态对象，包含世界观、金手指、人物关系

    Returns:
        更新后的状态字典，包含剧情大纲
    """
    print("\n" + "="*60)
    print("[剧情策划部] 开始工作")
    print("="*60)

    # 1. 整合所有前期信息（消除信息孤岛）
    world_context = build_world_building_context(state)
    gf_context = build_golden_finger_context(state)
    char_context = build_character_context(state)

    # 2. 获取连贯性检测的返修意见（如果有）
    revision_feedback = get_revision_feedback(state)

    # 3. 打印整合信息
    print(f"[剧情策划部] 末日名称：{world_context['apocalypse_name']}")
    print(f"[剧情策划部] 爆发时间：{world_context['outbreak_date']}")
    print(f"[剧情策划部] 金手指类型：{gf_context['ability_type']}")
    print(f"[剧情策划部] 主角姓名：{char_context['protagonist_name']}")
    print(f"[剧情策划部] 仇人数量：{len(char_context['villains_names'])}")
    print(f"[剧情策划部] 关键地点：{world_context['key_locations']}")

    # 4. 打印返修意见（如果有）
    if revision_feedback["has_feedback"]:
        print(f"\n[剧情策划部] ⚠️ 检测到返修意见")
        print(f"[剧情策划部] 上次评分：{revision_feedback['total_score']}/100")
        print(f"[剧情策划部] 必须修复问题：{len(revision_feedback['must_fix_issues'])}个")
        for i, issue in enumerate(revision_feedback['must_fix_issues'][:5], 1):
            print(f"  {i}. {issue}")
        print(f"[剧情策划部] 修改建议：{revision_feedback['feedback'][:200]}...")
    else:
        print(f"\n[剧情策划部] ✅ 无返修意见（首次生成）")

    # 5. 构建完整的提示词上下文
    prompt_context = f"""
    世界观设定：
    {json.dumps(world_context, ensure_ascii=False, indent=2)}
    
    金手指配置：
    {json.dumps(gf_context, ensure_ascii=False, indent=2)}
    
    人物关系：
    {json.dumps(char_context, ensure_ascii=False, indent=2)}
    """

    # 6. 如果有返修意见，添加到提示词中
    if revision_feedback["has_feedback"]:
        revision_context = f"""
        
═══════════════════════════════════════════════════════════════════════════
                        【返修意见】⚠️ 必须修复
═══════════════════════════════════════════════════════════════════════════

上次大纲连贯性检测评分：{revision_feedback['total_score']}/100

必须修复的问题：
{json.dumps(revision_feedback['must_fix_issues'], ensure_ascii=False, indent=2)}

时间连贯问题：
{json.dumps(revision_feedback['time_issues'], ensure_ascii=False, indent=2)}

地点连贯问题：
{json.dumps(revision_feedback['location_issues'], ensure_ascii=False, indent=2)}

人物连贯问题：
{json.dumps(revision_feedback['character_issues'], ensure_ascii=False, indent=2)}

剧情逻辑问题：
{json.dumps(revision_feedback['plot_logic_issues'], ensure_ascii=False, indent=2)}

修改建议：
{revision_feedback['feedback']}

⚠️ 重要：请根据以上返修意见重新设计大纲，确保所有问题都已修复。
修复后的大纲必须满足：
1. 时间线连贯，无倒流或跳跃无交代
2. 地点转换合理，使用已定义的关键地点
3. 人物状态连续，仇人在适当段落出现
4. 每段有爽点，段与段之间有过渡设计
5. 金手指使用符合设定，不超出功能范围
"""
        prompt_context += revision_context

    # 7. 构建 LLM 消息（包含所有上下文信息）
    messages = [
        SystemMessage(content=PROMPT_PLOT_PLANNER),
        HumanMessage(content=prompt_context)
    ]

    # 8. 调用 LLM 进行剧情策划
    print(f"\n[剧情策划部] 正在调用 LLM 规划剧情...")
    response = llm_default.invoke(messages)

    # 9. 解析 JSON 响应
    try:
        content = response.content.strip()
        # 清理 Markdown 代码块标记
        plot_data = parse_json_response(content)
        print(f"[剧情策划部] ✅ JSON 解析成功")
    except Exception as e:
        print(f"[剧情策划部][JSON 解析错误] {e}")
        # 降级处理：生成默认 6 段
        plot_data = {
            "beat_sheet": [
                {
                    "segment": i + 1,
                    "word_range": f"{i*1000}-{(i+1)*1000}",
                    "time": f"第{i+1}阶段",
                    "location": char_context.get('key_location_climax', '未指定'),
                    "characters": ["主角"],
                    "character_states": {"主角": "正常"},
                    "plot_summary": f"第{i+1}段：根据前期设定继续发展",
                    "hook_points": ["爽点"],
                    "key_props": [],
                    "golden_finger_usage": gf_context.get('ability_type', '无'),
                    "apocalypse_rules": world_context.get('apocalypse_name', '无'),
                    "transition_to_next": "自然过渡"
                }
                for i in range(6)
            ],
            "opening_hook": "她睁开眼睛，发现自己回到了末世前一天",
            "ending_hook": "她启动车辆，驶向远方",
            "timeline_summary": "重生→囤货→爆发→复仇→收尾",
        }

    # 10. 确保至少 6 段
    beat_sheet = plot_data.get("beat_sheet", [])
    if len(beat_sheet) < 6:
        print(f"[剧情策划部] ⚠️ 段落不足 6 段，补充至 6 段")
        for i in range(len(beat_sheet), 6):
            beat_sheet.append({
                "segment": i + 1,
                "word_range": f"{i*1000}-{(i+1)*1000}",
                "time": f"第{i+1}阶段",
                "location": char_context.get('key_location_climax', '未指定'),
                "characters": ["主角"],
                "character_states": {"主角": "正常"},
                "plot_summary": f"第{i+1}段：根据前期设定继续发展",
                "hook_points": ["爽点"],
                "key_props": [],
                "golden_finger_usage": gf_context.get('ability_type', '无'),
                "apocalypse_rules": world_context.get('apocalypse_name', '无'),
                "transition_to_next": "自然过渡"
            })

    # 11. 构建剧情状态对象
    plot = {
        "beat_sheet": beat_sheet,
        "hook_points": plot_data.get("hook_points", []),
        "transition_design": "",
        "opening_hook": plot_data.get("opening_hook", ""),
        "ending_hook": plot_data.get("ending_hook", ""),
        "timeline_summary": plot_data.get("timeline_summary", ""),
        "revision_count": state.get("plot_revision_count", 0) + (1 if revision_feedback["has_feedback"] else 0),
        "qa_status": "PENDING",
        "qa_feedback": "",
        "revision_notes": plot_data.get("plot_data",""),
    }

    # 12. 打印工作日志
    print(f"\n[剧情策划部] ✅ 完成：{len(plot['beat_sheet'])} 个段落")
    print(f"[剧情策划部] 开篇钩子：{plot['opening_hook'][:50]}...")
    print(f"[剧情策划部] 时间线摘要：{plot['timeline_summary'][:50]}...")
    print(f"[剧情策划部] 返修次数：{plot['revision_count']}")

    # 13. 返回状态更新
    return {"plot": plot}
