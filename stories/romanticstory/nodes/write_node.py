# romanticstory/nodes/writer_node.py
import json
from langchain_core.messages import SystemMessage, HumanMessage
from romanticstory.config.config import llm
from romanticstory.prompts.romantic_story_prompt import WRITE_PROMPT
from romanticstory.states.romantic_story_state import MainState, SegmentState
from utils.json_util import parse_json_response


def writer_node(state: MainState) -> dict:
    """
    分块写作部：根据大纲当前段落进行写作
    每次只处理一段，不考虑前后文连贯
    """
    print("\n" + "=" * 60)
    print(f"[分块写作部] 开始工作 - 段落索引：{state.get('current_segment_index', 0)}")
    print("=" * 60)

    # ===================================================================
    # 步骤 1: 从 MainState 提取必要信息
    # ===================================================================
    current_index = state.get("current_segment_index", 0)
    plot_state = state.get("plot_state", {})
    beat_sheet = plot_state.get("beat_sheet", [])

    # 安全检查：索引超出范围则直接返回
    if current_index >= len(beat_sheet):
        print(f"[分块写作部] ⚠️ 索引 {current_index} 超出大纲范围 {len(beat_sheet)}，结束写作")
        return {"current_segment_index": current_index}

    # 提取当前段落大纲
    current_paragraph = beat_sheet[current_index]

    # 提取基础状态信息（用于保持人设和主题一致）
    plan_state = state.get("plan_state", {})
    character_state = state.get("character_state", {})
    structure_notes = plot_state.get("structure_notes", {})

    # ===================================================================
    # 步骤 2: 整合当前段落信息到字典
    # ===================================================================

    # 2.1 提取三线对齐信息
    lines_alignment = current_paragraph.get("lines_alignment", {})

    # 2.2 提取角色行动列表
    character_action_list = current_paragraph.get("character_action_list", [])

    # 2.3 提取人物设定摘要（用于保持人设一致）
    characters_map = {}
    for char in character_state.get("characters", []):
        char_id = char.get("character_id", "")
        char_name = char.get("basic", {}).get("name", "")
        characters_map[char_name] = {
            "character_id": char_id,
            "character_flaw": char.get("dna", {}).get("character_flaw", ""),
            "core_mechanism": char.get("dna", {}).get("core_mechanism", ""),
            "physical_markers": char.get("physical_markers", []),
            "habit": char.get("basic", {}).get("habit", ""),
            "secret": char.get("secret", {})
        }

    # 2.4 整合写作上下文信息
    writing_context = {
        # 核心故事信息
        "story_info": {
            "core_topic": plan_state.get("core_topic", ""),
            "story_backend": plan_state.get("story_backend", ""),
            "hook": plan_state.get("hook", "")
        },

        # 当前段落大纲（核心）
        "current_paragraph": {
            "para_id": current_paragraph.get("para_id", ""),
            "lines_alignment": {
                "event_line_stage": lines_alignment.get("event_line_stage", ""),
                "emotion_line_stage": lines_alignment.get("emotion_line_stage", ""),
                "background_line_stage": lines_alignment.get("background_line_stage", ""),
                "dual_line_intersection": lines_alignment.get("dual_line_intersection", "")
            },
            "character_action_list": character_action_list,
            "climax_moment": current_paragraph.get("climax_moment", ""),
            "resulting_state": current_paragraph.get("resulting_state", ""),
            "residue_problem": current_paragraph.get("residue_problem", ""),
            "transition_design": current_paragraph.get("transition_design", ""),
            "opening_hook": current_paragraph.get("opening_hook", ""),
            "ending_hook": current_paragraph.get("ending_hook", ""),
            "plot": current_paragraph.get("plot", "")
        },

        # 主要人物设定（保持人设）
        "characters": characters_map,

        # 整体结构说明
        "structure_notes": {
            "total_paragraphs": structure_notes.get("total_paragraphs", ""),
            "rhythm_pattern": structure_notes.get("rhythm_pattern", ""),
            "secret_reveal_schedule": structure_notes.get("secret_reveal_schedule", ""),
            "core_conflict_resolution": structure_notes.get("core_conflict_resolution", "")
        },

        # 写作要求
        "writing_requirements": {
            "word_count": "1000-1500 字",
            "style": "细腻情感描写 + 具体动作呈现",
            "focus": "严格遵循 character_action_list 中的行为驱动和防御机制"
        }
    }

    # 打印日志
    print(f"[分块写作部] 📋 当前段落：{current_paragraph.get('para_id', 'N/A')}")
    print(f"[分块写作部] 📋 事件线阶段：{lines_alignment.get('event_line_stage', 'N/A')}")
    print(f"[分块写作部] 📋 情感线阶段：{lines_alignment.get('emotion_line_stage', 'N/A')}")
    print(f"[分块写作部] 📋 高潮点：{current_paragraph.get('climax_moment', '')[:50]}...")
    print(f"[分块写作部] 📋 角色行动数：{len(character_action_list)}")

    # ===================================================================
    # 步骤 3: 构建消息并调用 LLM
    # ===================================================================
    messages = [
        SystemMessage(content=WRITE_PROMPT),
        HumanMessage(content=f"""
        请根据以下信息撰写正文内容：

        【故事核心信息】
        {json.dumps(writing_context["story_info"], ensure_ascii=False, indent=2)}

        【当前段落大纲】
        {json.dumps(writing_context["current_paragraph"], ensure_ascii=False, indent=2)}

        【主要人物设定】
        {json.dumps(writing_context["characters"], ensure_ascii=False, indent=2)}

        【整体结构说明】
        {json.dumps(writing_context["structure_notes"], ensure_ascii=False, indent=2)}

        【写作要求】
        {json.dumps(writing_context["writing_requirements"], ensure_ascii=False, indent=2)}

        请输出 JSON 格式：{{"content": "正文内容"}}
        """)
    ]

    # 调用 LLM
    response = llm.invoke(messages)

    # ===================================================================
    # 步骤 4: 解析响应并构建 SegmentState
    # ===================================================================
    response_data = parse_json_response(response.content)

    # 获取 content 字段（必须是字符串）
    content = response_data.get("content", "")

    # 如果解析失败，使用原始响应内容
    if not content:
        content = response.content if hasattr(response, 'content') else str(response)

    # 构建 SegmentState 对象
    new_segment: SegmentState = {
        "para_id": current_paragraph.get("para_id", f"para_{current_index}"),
        "content": content  # ✅ 确保是字符串，不是字典
    }

    # 更新 segments 列表
    existing_segments = state.get("segments", [])
    updated_segments = existing_segments + [new_segment]

    # 打印日志
    print(f"[分块写作部] ✅ 完成：段落 {new_segment['para_id']}")
    print(f"[分块写作部] ✅ 字数：{len(content)} 字符")
    print(f"[分块写作部] ✅ 本段内容：{content} ")

    # ===================================================================
    # 步骤 5: 返回状态更新（必须是字典）
    # ===================================================================
    return {
        "segments": updated_segments,
        "current_segment_index": current_index + 1
    }
