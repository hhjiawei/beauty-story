"""
连贯性整合部节点
大纲阶段已进行连贯性检测，此节点仅负责段落整合
"""
from states.storyState import MainState


def continuity_node(state: MainState) -> dict:
    """
    连贯性整合部节点函数 - 简化版（仅段落整合）

    Args:
        state: 主状态对象

    Returns:
        更新后的状态字典，包含连贯初稿
    """
    print("\n" + "="*60)
    print("[连贯性整合部] 开始工作")
    print("="*60)

    # 1. 获取所有段落
    segments = state.get("segments", [])
    print(f"[连贯性整合部] 段落数量：{len(segments)}")

    # 2. 组合所有段落正文
    full_draft = "\n\n".join([seg.get("content", "") for seg in segments])

    # 3. 获取大纲阶段的连贯性报告
    plot_continuity_report = state.get("plot_continuity_report", {})

    # 4. 构建连贯性状态
    continuity = {
        "full_draft": full_draft,
        "continuity_report": {
            "overall_status": plot_continuity_report.get("overall_status", "PASS"),
            "logic_continuity_score": plot_continuity_report.get("total_score", 80),
        },
        "transition_records": [],
        "logic_continuity": plot_continuity_report.get("total_score", 80),
        "qa_status": "PENDING",
        "qa_feedback": ""
    }

    print(f"[连贯性整合部] ✅ 段落整合完成")
    print(f"[连贯性整合部] 总字数：{len(full_draft)}")
    print(f"[连贯性整合部] 大纲连贯性评分：{continuity['logic_continuity']:.1f}/100")

    return {"continuity": continuity}
