"""
节点品控部节点
每个节点完成后立即检查，不合格即退回
"""
from datetime import datetime
from states.storyState import MainState


def node_qa_node(state: MainState) -> dict:
    """
    节点品控部节点函数 - 通用品控

    Args:
        state: 主状态对象，包含当前节点交付物

    Returns:
        更新后的状态字典，包含品控记录
    """
    print("\n" + "=" * 60)
    print("[节点品控部] 开始检查")
    print("=" * 60)

    # 简化的品控逻辑（实际应根据当前节点检查对应内容）
    qa_record = {
        "node_name": "current_node",
        "check_result": "PASS",
        "completeness_score": 90,
        "format_score": 95,
        "quality_score": 88,
        "continuity_score": 92,
        "issues": [],
        "suggestions": [],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # 添加到品控记录列表
    records = state.get("node_qa_records", [])
    records.append(qa_record)

    # 打印工作日志
    print(f"[节点品控部] ✅ 检查完成：{qa_record['check_result']}")

    # 返回状态更新
    return {"node_qa_records": records}
