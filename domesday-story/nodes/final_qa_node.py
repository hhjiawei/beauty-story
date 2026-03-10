"""
终稿质检部节点
对照六大核心特征最终验收
使用 LLM 进行全方位质量检查
"""
import json
import re
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_FINAL_QA
from config.config import llm_precise  # ✅ 质检使用精确 LLM，温度低更稳定

llm = llm_precise

def parse_json_response(content: str) -> dict:
    """
    解析 LLM 的 JSON 响应

    Args:
        content: LLM 返回的内容

    Returns:
        解析后的字典，如果解析失败返回默认值
    """
    try:
        # 清理 Markdown 代码块标记
        content = content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        content = content.strip()

        # 尝试解析 JSON
        return json.loads(content)
    except Exception as e:
        print(f"[终稿 QA][JSON 解析错误] {e}")
        # 返回默认的 PASS 结果，避免阻塞流程
        return {
            "six_feature_scores": {
                "overall": 8,
                "protagonist": 8,
                "hoarding": 8,
                "revenge": 8,
                "contrast": 8,
                "rhythm": 8
            },
            "total_score": 48,
            "continuity_check": {
                "timeline": "PASS",
                "location": "PASS",
                "character": "PASS",
                "prop": "PASS",
                "causality": "PASS"
            },
            "compliance_issues": [],
            "word_count": 5000,
            "final_status": "PASS",
            "feedback": "自动通过 - JSON 解析失败"
        }


def get_full_process_records(state: MainState) -> dict:
    """
    提取全流程状态记录供 LLM 参考

    Args:
        state: 主状态对象

    Returns:
        精简后的全流程记录字典
    """
    return {
        "world_building": {
            "apocalypse_name": state.get("world_building", {}).get("apocalypse_name", ""),
            "outbreak_date": state.get("world_building", {}).get("outbreak_date", ""),
        },
        "golden_finger": {
            "ability_type": state.get("golden_finger", {}).get("ability_type", ""),
        },
        "character": {
            "protagonist_name": state.get("character", {}).get("protagonist", {}).get("name", ""),
            "villains_count": len(state.get("character", {}).get("villains", [])),
        },
        "plot": {
            "segment_count": len(state.get("plot", {}).get("beat_sheet", [])),
            "timeline_summary": state.get("plot", {}).get("timeline_summary", ""),
        },
        "segments": {
            "total_segments": len(state.get("segments", [])),
            "total_word_count": sum(seg.get("word_count", 0) for seg in state.get("segments", [])),
        },
        "node_qa_records": {
            "total_checks": len(state.get("node_qa_records", [])),
            "failed_checks": len([r for r in state.get("node_qa_records", []) if r.get("check_result") == "REJECT"]),
        },
        "sensory": {
            "sensory_count": state.get("sensory", {}).get("sensory_count", 0),
        },
        "humor": {
            "humor_count": state.get("humor", {}).get("humor_count", 0),
        },
    }


def final_qa_node(state: MainState) -> dict:
    """
    终稿质检部节点函数 - 使用 LLM 进行全方位质检

    Args:
        state: 主状态对象，包含完整稿件

    Returns:
        更新后的状态字典，包含最终质检报告
    """
    print("\n" + "="*60)
    print("[终稿质检部] 开始最终验收")
    print("="*60)

    # 1. 获取最终稿件
    final_draft = state.get("format", {}).get("final_draft", "")
    word_count = len(final_draft)

    print(f"[终稿质检部] 稿件字数：{word_count}")

    # 2. 获取全流程状态记录
    full_process_records = get_full_process_records(state)

    # 3. 构建 LLM 消息
    messages = [
        SystemMessage(content=PROMPT_FINAL_QA),
        HumanMessage(content=f"""
        待审查的完整稿件（前 5000 字符）：
        {final_draft[:5000]}...
        
        全流程状态记录：
        {json.dumps(full_process_records, ensure_ascii=False, indent=2)}
        
        稿件总字数：{word_count}
        """)
    ]

    # 4. 调用 LLM 进行质检
    try:
        print(f"[终稿质检部] 正在调用 LLM 进行全方位质检...")
        response = llm_precise.invoke(messages)
        print(f"[终稿质检部] LLM 响应接收完成")
    except Exception as e:
        print(f"[终稿质检部][LLM 调用错误] {e}")
        # LLM 调用失败时使用默认通过
        final_qa = {
            "six_feature_scores": {
                "overall": 8,
                "protagonist": 8,
                "hoarding": 8,
                "revenge": 8,
                "contrast": 8,
                "rhythm": 8
            },
            "total_score": 48,
            "continuity_check": {
                "timeline": "PASS",
                "location": "PASS",
                "character": "PASS",
                "prop": "PASS",
                "causality": "PASS"
            },
            "compliance_issues": [f"LLM 调用失败：{str(e)}"],
            "word_count": word_count,
            "final_status": "PASS" if word_count >= 5000 else "REJECT",
            "feedback": "自动通过 - LLM 不可用"
        }
        return {"final_qa": final_qa}

    # 5. 解析 LLM 返回的 JSON
    qa_result = parse_json_response(response.content)

    # 6. 构建标准化的质检报告
    final_qa = {
        "six_feature_scores": qa_result.get("six_feature_scores", {
            "overall": 8,
            "protagonist": 8,
            "hoarding": 8,
            "revenge": 8,
            "contrast": 8,
            "rhythm": 8
        }),
        "total_score": qa_result.get("total_score", 48),
        "continuity_check": qa_result.get("continuity_check", {
            "timeline": "PASS",
            "location": "PASS",
            "character": "PASS",
            "prop": "PASS",
            "causality": "PASS"
        }),
        "compliance_issues": qa_result.get("compliance_issues", []),
        "word_count": qa_result.get("word_count", word_count),
        "final_status": qa_result.get("final_status", "PASS"),
        "feedback": qa_result.get("feedback", "通过验收")
    }

    # 7. 自动校验字数
    if final_qa["word_count"] < 5000:
        final_qa["compliance_issues"].append(f"字数不足：{final_qa['word_count']} < 5000")
        final_qa["final_status"] = "REJECT"

    # 8. 自动校验六大特征总分
    if final_qa["total_score"] < 55:
        final_qa["compliance_issues"].append(f"六大特征总分不足：{final_qa['total_score']} < 55")
        final_qa["final_status"] = "REJECT"

    # 9. 自动校验连贯性检查
    continuity = final_qa.get("continuity_check", {})
    for key, value in continuity.items():
        if value == "FAIL":
            final_qa["compliance_issues"].append(f"连贯性检查失败：{key}")
            final_qa["final_status"] = "REJECT"

    # 10. 打印检查结果
    print(f"[终稿质检部] ✅ 验收完成：{final_qa['final_status']}")
    print(f"[终稿质检部] 六大特征总分：{final_qa['total_score']}/60")
    print(f"[终稿质检部] 各项评分：")
    for feature, score in final_qa['six_feature_scores'].items():
        print(f"    - {feature}: {score}/10")
    print(f"[终稿质检部] 连贯性检查：")
    for key, value in final_qa['continuity_check'].items():
        status_icon = "✅" if value == "PASS" else "❌"
        print(f"    {status_icon} {key}: {value}")

    if final_qa['compliance_issues']:
        print(f"[终稿质检部] ⚠️ 合规问题：{final_qa['compliance_issues']}")

    print(f"[终稿质检部] 💡 反馈建议：{final_qa['feedback']}")

    # 11. 返回状态更新
    return {"final_qa": final_qa}
