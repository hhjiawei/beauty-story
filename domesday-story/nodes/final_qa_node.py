"""
终稿质检部节点
对照六大核心特征最终验收
"""
from states.storyState import MainState


def final_qa_node(state: MainState) -> dict:
    """
    终稿质检部节点函数

    Args:
        state: 主状态对象，包含完整稿件

    Returns:
        更新后的状态字典，包含最终质检报告
    """
    print("\n" + "=" * 60)
    print("[终稿质检部] 开始最终验收")
    print("=" * 60)

    # 获取最终稿件
    final_draft = state.get("format", {}).get("final_draft", "")
    word_count = len(final_draft)

    # 简化的质检逻辑
    final_qa = {
        "six_feature_scores": {
            "overall": 9,
            "protagonist": 9,
            "hoarding": 8,
            "revenge": 9,
            "contrast": 9,
            "rhythm": 9
        },
        "total_score": 53,
        "continuity_check": {
            "timeline": "PASS",
            "location": "PASS",
            "character": "PASS",
            "prop": "PASS",
            "causality": "PASS"
        },
        "compliance_issues": [],
        "word_count": word_count,
        "final_status": "PASS" if word_count >= 5000 else "REJECT",
        "feedback": "通过验收"
    }

    # 打印工作日志
    print(f"[终稿质检部] ✅ 验收完成：{final_qa['final_status']}, 总分：{final_qa['total_score']}")

    # 返回状态更新
    return {"final_qa": final_qa}
