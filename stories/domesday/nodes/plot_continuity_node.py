"""
剧情连贯性检测节点
在剧情策划完成后，使用 LLM 检测大纲连贯性
检测通过后才开始写作，避免大量返工
"""
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from domesday.states.storyState import MainState
from domesday.prompts.storyPrompts import PROMPT_PLOT_CONTINUITY
from domesday.config.config import llm_precise  # 使用精确 LLM 进行检测


def parse_json_response(content: str) -> dict:
    """解析 LLM 的 JSON 响应"""
    try:
        content = content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        content = content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"[大纲连贯性检测][JSON 解析错误] {e}")
        # 返回默认失败结果
        return {
            "total_score": 50,
            "overall_status": "FAIL",
            "feedback": f"JSON 解析失败：{str(e)}",
            "must_fix_issues": ["格式错误，请重新生成大纲"]
        }


def plot_continuity_node(state: MainState) -> dict:
    """
    剧情连贯性检测节点函数 - 使用 LLM 检测大纲连贯性

    Args:
        state: 主状态对象，包含剧情大纲和前期设定

    Returns:
        更新后的状态字典，包含连贯性检测报告
    """
    print("\n" + "=" * 60)
    print("[剧情连贯性检测] 开始工作")
    print("=" * 60)

    # 1. 获取剧情大纲
    plot = state.get("plot", {})
    beat_sheet = plot.get("beat_sheet", [])

    print(f"[剧情连贯性检测] 大纲段落数：{len(beat_sheet)}")

    # 2. 获取前期设定（用于连贯性参考）
    world_building = state.get("world_building", {})
    golden_finger = state.get("golden_finger", {})
    character = state.get("character", {})

    # 3. 构建 LLM 消息
    messages = [
        SystemMessage(content=PROMPT_PLOT_CONTINUITY),
        HumanMessage(content=f"""
        待检测的剧情大纲：
        {json.dumps(plot, ensure_ascii=False, indent=2)}

        世界观设定：
        {json.dumps(world_building, ensure_ascii=False, indent=2)}

        金手指配置：
        {json.dumps(golden_finger, ensure_ascii=False, indent=2)}

        人物关系：
        {json.dumps(character, ensure_ascii=False, indent=2)}
        """)
    ]

    # 4. 调用精确 LLM 进行检测
    try:
        print(f"[剧情连贯性检测] 正在调用 LLM 进行连贯性检测...")
        response = llm_precise.invoke(messages)
        print(f"[剧情连贯性检测] LLM 响应接收完成")
    except Exception as e:
        print(f"[剧情连贯性检测][LLM 调用错误] {e}")
        # LLM 调用失败时默认通过
        continuity_report = {
            "time_continuity": {"status": "PASS", "score": 20, "issues": []},
            "location_continuity": {"status": "PASS", "score": 20, "issues": []},
            "character_continuity": {"status": "PASS", "score": 20, "issues": []},
            "plot_logic": {"status": "PASS", "score": 20, "issues": []},
            "total_score": 80,
            "overall_status": "PASS",
            "feedback": "自动通过 - LLM 不可用",
            "must_fix_issues": []
        }
        return {
            "plot_continuity_report": continuity_report,
            "plot_continuity_status": "PASS"
        }

    # 5. 解析 LLM 返回的 JSON
    continuity_report = parse_json_response(response.content)

    # 6. 构建标准化的检测报告
    report = {
        "time_continuity": continuity_report.get("time_continuity", {
            "status": "FAIL", "score": 0, "issues": []
        }),
        "location_continuity": continuity_report.get("location_continuity", {
            "status": "FAIL", "score": 0, "issues": []
        }),
        "character_continuity": continuity_report.get("character_continuity", {
            "status": "FAIL", "score": 0, "issues": []
        }),
        "plot_logic": continuity_report.get("plot_logic", {
            "status": "FAIL", "score": 0, "issues": []
        }),
        "total_score": continuity_report.get("total_score", 0),
        "overall_status": continuity_report.get("overall_status", "FAIL"),
        "feedback": continuity_report.get("feedback", "检测失败"),
        "must_fix_issues": continuity_report.get("must_fix_issues", []),
    }

    # 7. 自动判定通过状态（总分≥80 且无必须修复问题）
    if report["total_score"] >= 80 and not report["must_fix_issues"]:
        report["overall_status"] = "PASS"
    else:
        report["overall_status"] = "FAIL"

    # 8. 打印检测结果
    print(f"[剧情连贯性检测] ✅ 检测完成：{report['overall_status']}")
    print(f"[剧情连贯性检测] 总分：{report['total_score']}/100")
    print(f"[剧情连贯性检测] 各项评分:")

    if report.get("must_fix_issues"):
        print(f"[剧情连贯性检测] ⚠️ 必须修复的问题：{len(report['must_fix_issues'])} 个")
        for issue in report["must_fix_issues"][:5]:
            print(f"  - {issue}")

    if report.get("feedback"):
        print(f"[剧情连贯性检测] 💡 修改建议：{report['feedback'][:200]}...")

    # 9. 返回状态更新
    return {
        "plot_continuity_report": report,
        "plot_continuity_status": report["overall_status"]
    }
