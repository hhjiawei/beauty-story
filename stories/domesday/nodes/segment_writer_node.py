"""
分块写作部节点
按大纲分 6 段撰写，严格遵循时间地点人物状态
整合前期所有部门信息，消除信息孤岛
"""
import json
from langchain_core.messages import HumanMessage, SystemMessage
from domesday.states.storyState import MainState
from domesday.prompts.storyPrompts import PROMPT_SEGMENT_WRITER
from domesday.config.config import llm_creative  # ✅ 使用创意 LLM，温度更高，更有文学性


def extract_text_and_summary(content: str) -> tuple:
    """
    从写作输出中提取正文和摘要

    Args:
        content: 写作输出内容

    Returns:
        (正文，摘要) 元组
    """
    if "===段落摘要===" in content:
        parts = content.split("===段落摘要===")
        text = parts[0].strip()
        summary = parts[1].strip() if len(parts) > 1 else ""
        return text, summary
    else:
        return content.strip(), ""


def build_world_building_context(state: MainState) -> dict:
    """
    从世界观设定部提取关键信息
    提取内容：
    - 末日名称和来源（写作时需要提及）
    - 爆发时间（判断当前段落是爆发前还是爆发后）
    - 传播规则（描写变异者行为时必须遵守）
    - 变异症状（描写感染者时必须一致）
    - 关键地点（场景转换时必须使用已定义的地点）
    - 特殊规则（任何特殊设定都不能违背）

    Args:
        state: 主状态对象

    Returns:
        世界观上下文字典
    """
    world = state.get("world_building", {})
    return {
        "apocalypse_name": world.get("apocalypse_name", "未知末日"),
        "apocalypse_source": world.get("apocalypse_source", ""),  # 限制长度
        "outbreak_date": world.get("outbreak_date", ""),
        "key_locations": [loc.get("name", "") for loc in world.get("key_locations", [])],
        "special_rules": world.get("special_rules", ""),
    }


def build_golden_finger_context(state: MainState) -> dict:
    """
    从金手指设计部提取关键信息
    提取内容：
    - 能力类型（重生/空间/系统/异能）
    - 激活条件（判断当前段落是否已激活）
    - 具体功能（写作时只能使用已定义的功能）
    - 使用限制（不能超出限制范围）
    - 复仇优势（提示可以在哪些场景使用）
    Args:
        state: 主状态对象

    Returns:
        金手指上下文字典
    """
    gf = state.get("golden_finger", {})
    return {
        "ability_type": gf.get("ability_type", ""),
        "activation_condition": gf.get("activation_condition", ""),
        "functions": gf.get("functions", []),
        "limitations": gf.get("limitations", ""),
        "revenge_advantages": gf.get("revenge_advantages", []),
    }


def build_character_context(state: MainState) -> dict:
    """
    从人物关系部提取关键信息
    提取内容：
    - 主角姓名、年龄、职业、性格
    - 前世死亡信息（用于回忆或心理描写）
    - 重生时间（判断当前时间点）
    - 仇人列表及弱点（复仇时必须利用弱点）
    - 盟友列表及价值（合作时必须符合设定）
    Args:
        state: 主状态对象

    Returns:
        人物上下文字典
    """
    char = state.get("character", {})
    protagonist = char.get("protagonist", {})
    villains = char.get("villains", [])
    allies = char.get("allies", [])

    # 格式化仇人信息
    villains_info = ""
    for i, v in enumerate(villains, 1):
        villains_info += f"  {i}. {v.get('name', '未知')}（{v.get('relationship', '未知')}）\n"
        villains_info += f"     弱点：{v.get('weakness', '无')}\n"
        villains_info += f"     前世背叛：{v.get('betrayal_info', {}).get('action', '未知')}...\n"
        villains_info += f"     今生结局：{v.get('fate', '未知')}\n\n"

    # 格式化盟友信息
    allies_info = ""
    for i, a in enumerate(allies, 1):
        allies_info += f"  {i}. {a.get('name', '未知')}（{a.get('relationship', '未知')}）\n"
        allies_info += f"     价值：{a.get('value', '无')}\n\n"

    return {
        "protagonist_name": protagonist.get("name", "未知"),
        "protagonist_age": protagonist.get("age", 0),
        "protagonist_profession": protagonist.get("profession", "未知"),
        "protagonist_personality": protagonist.get("personality", []),
        "death_info": protagonist.get("death_info", {}),
        "rebirth_time": protagonist.get("rebirth_info", {}).get("time", ""),
        "villains_info": villains_info,
        "allies_info": allies_info,
    }


def segment_writer_node(state: MainState) -> dict:
    """
    分块写作部节点函数 - 整合所有前期信息

    Args:
        state: 主状态对象，包含所有前期部门成果

    Returns:
        更新后的状态字典，包含新写的段落
    """
    # 1. 获取当前段落索引
    idx = state.get("current_segment_index", 0)
    beat_sheet = state["plot"]["beat_sheet"]

    # 检查是否已写完所有段落
    if idx >= len(beat_sheet):
        print(f"[分块写作部] ⚠️ 所有段落已完成：{len(beat_sheet)} 段")
        return {}

    print("\n" + "="*60)
    print(f"[分块写作部] 正在写第 {idx + 1}/{len(beat_sheet)} 段")
    print("="*60)

    # 2. 获取当前段落大纲
    beat = beat_sheet[idx]

    # 3. 获取前文摘要
    segments = state.get("segments", [])
    previous_summary = segments[-1].get("summary", "故事开头") if segments else "故事开头"

    # 4. 整合所有前期信息（消除信息孤岛）
    world_context = build_world_building_context(state)
    gf_context = build_golden_finger_context(state)
    char_context = build_character_context(state)

    # 5. 构建完整的提示词上下文
    prompt_context = f"""
    索引：{idx + 1}/{len(beat_sheet)}
    时间：{beat.get('time', '未指定')}
    地点：{beat.get('location', '未指定')}
    在场人物：{beat.get('characters', ['主角'])}
    人物状态：{json.dumps(beat.get('character_states', {}), ensure_ascii=False)}
    前文摘要：{previous_summary}
    当前段落大纲：{beat.get('plot_summary', '')}
    关键道具：{beat.get('key_props', [])}
    风格要求：短句密集、黑色幽默、强对比、不圣母、复仇狠辣
    """

    # 6. 构建 LLM 消息（包含所有上下文信息）
    messages = [
        SystemMessage(content=PROMPT_SEGMENT_WRITER),
        HumanMessage(content=f"""
        {prompt_context}
        
        【完整创作上下文】
        
        世界观设定：
        {json.dumps(world_context, ensure_ascii=False, indent=2)}
        
        金手指配置：
        {json.dumps(gf_context, ensure_ascii=False, indent=2)}
        
        人物关系：
        {json.dumps(char_context, ensure_ascii=False, indent=2)}
        """)
    ]

    # 7. 调用创意 LLM 进行写作
    print(f"[分块写作部] 正在调用 LLM 创作...")
    print(f"[分块写作部] 时间：{beat.get('time', '未知')}")
    print(f"[分块写作部] 地点：{beat.get('location', '未知')}")
    print(f"[分块写作部] 在场人物：{beat.get('characters', [])}")

    response = llm_creative.invoke(messages)

    # 8. 提取正文和摘要
    text, summary = extract_text_and_summary(response.content)

    # 9. 构建段落状态对象
    segment = {
        "segment_index": idx,
        "content": text,
        "summary": summary,
        "word_count": len(text),
        "time": beat.get('time', ''),
        "location": beat.get('location', ''),
        "characters": beat.get('characters', []),
        "character_states": beat.get('character_states', {}),
        "key_props": beat.get('key_props', []),
        "qa_status": "PENDING",
        "qa_feedback": ""
    }

    # 10. 添加到 segments 列表
    segments.append(segment)

    # 11. 打印工作日志
    print(f"[分块写作部] ✅ 完成第 {idx + 1} 段")
    print(f"[分块写作部] 生成字数：{segment['word_count']}")
    print(f"[分块写作部] 段落摘要：{summary[:100]}...")

    # 12. 返回状态更新
    return {
        "segments": segments,
        "current_segment_index": idx + 1
    }
