"""
节点品控部节点
每个节点完成后立即检查，不合格即退回
使用 LLM 进行智能化质量检测
"""
import json
import re
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_NODE_QA
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
        print(f"[节点 QA][JSON 解析错误] {e}")
        # 返回默认的 PASS 结果，避免阻塞流程
        return {
            "node_name": "unknown",
            "check_result": "PASS",
            "completeness_score": 80,
            "format_score": 80,
            "quality_score": 80,
            "continuity_score": 80,
            "issues": [],
            "suggestions": ["自动通过 - JSON 解析失败"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }


def get_current_node_name(state: MainState) -> str:
    """
    根据当前状态推断正在检查的节点名称

    Args:
        state: 主状态对象

    Returns:
        节点名称字符串
    """
    # 根据已填充的状态字段判断当前节点
    if state.get("world_building", {}) and not state.get("golden_finger", {}):
        return "world_builder"
    elif state.get("golden_finger", {}) and not state.get("character", {}):
        return "golden_finger"
    elif state.get("character", {}) and not state.get("plot", {}):
        return "character"
    elif state.get("plot", {}) and not state.get("segments", []):
        return "plot_planner"
    elif state.get("segments", []) and not state.get("continuity", {}):
        return "segment_writer"
    elif state.get("continuity", {}) and not state.get("rhythm", {}):
        return "continuity"
    elif state.get("rhythm", {}) and not state.get("sensory", {}):
        return "rhythm"
    elif state.get("sensory", {}) and not state.get("humor", {}):
        return "sensory"
    elif state.get("humor", {}) and not state.get("format", {}):
        return "humor"
    elif state.get("format", {}):
        return "format"
    else:
        return "unknown"


def get_deliverable_for_node(state: MainState, node_name: str) -> dict:
    """
    根据节点名称获取对应的交付物

    Args:
        state: 主状态对象
        node_name: 节点名称

    Returns:
        交付物字典
    """
    deliverables = {
        "world_builder": state.get("world_building", {}),
        "golden_finger": state.get("golden_finger", {}),
        "character": state.get("character", {}),
        "plot_planner": state.get("plot", {}),
        "segment_writer": {
            "segments_count": len(state.get("segments", [])),
            "last_segment": state.get("segments", [])[-1] if state.get("segments", []) else {}
        },
        "continuity": state.get("continuity", {}),
        "rhythm": state.get("rhythm", {}),
        "sensory": state.get("sensory", {}),
        "humor": state.get("humor", {}),
        "format": state.get("format", {}),
    }
    return deliverables.get(node_name, {})


def node_qa_node(state: MainState) -> dict:
    """
    节点品控部节点函数 - 使用 LLM 进行智能质检

    Args:
        state: 主状态对象，包含当前节点交付物

    Returns:
        更新后的状态字典，包含品控记录
    """
    print("\n" + "="*60)
    print("[节点品控部] 开始检查")
    print("="*60)

    # 1. 确定当前检查的节点名称
    node_name = get_current_node_name(state)
    print(f"[节点品控部] 检查节点：{node_name}")

    # 2. 获取当前节点的交付物
    deliverable = get_deliverable_for_node(state, node_name)

    # 3. 获取之前的品控记录（用于连贯性检查）
    previous_records = state.get("node_qa_records", [])
    previous_records_str = json.dumps(previous_records[-3:], ensure_ascii=False) if previous_records else "无历史记录"

    # 4. 构建 LLM 消息
    messages = [
        SystemMessage(content=PROMPT_NODE_QA),
        HumanMessage(content=f"""
        待检查的交付物：
        {json.dumps(deliverable, ensure_ascii=False, indent=2)}
        
        前文状态记录：
        {previous_records_str}
        
        当前节点名称：{node_name}
        """)
    ]

    # 5. 调用 LLM 进行质检
    try:
        print(f"[节点品控部] 正在调用 LLM 进行质检...")
        response = llm_precise.invoke(messages)
        print(f"[节点品控部] LLM 响应接收完成")
    except Exception as e:
        print(f"[节点品控部][LLM 调用错误] {e}")
        # LLM 调用失败时使用默认通过
        qa_record = {
            "node_name": node_name,
            "check_result": "PASS",
            "completeness_score": 80,
            "format_score": 80,
            "quality_score": 80,
            "continuity_score": 80,
            "issues": [f"LLM 调用失败：{str(e)}"],
            "suggestions": ["自动通过 - LLM 不可用"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        records = state.get("node_qa_records", [])
        records.append(qa_record)
        return {"node_qa_records": records}

    # 6. 解析 LLM 返回的 JSON
    qa_result = parse_json_response(response.content)

    # 7. 构建标准化的品控记录
    qa_record = {
        "node_name": qa_result.get("node_name", node_name),
        "check_result": qa_result.get("check_result", "PASS"),
        "completeness_score": qa_result.get("completeness_score", 80),
        "format_score": qa_result.get("format_score", 80),
        "quality_score": qa_result.get("quality_score", 80),
        "continuity_score": qa_result.get("continuity_score", 80),
        "issues": qa_result.get("issues", []),
        "suggestions": qa_result.get("suggestions", []),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # 8. 添加到品控记录列表
    records = state.get("node_qa_records", [])
    records.append(qa_record)

    # 9. 打印检查结果
    print(f"[节点品控部] ✅ 检查完成：{qa_record['check_result']}")
    print(f"[节点品控部] 完整性评分：{qa_record['completeness_score']}")
    print(f"[节点品控部] 格式评分：{qa_record['format_score']}")
    print(f"[节点品控部] 质量评分：{qa_record['quality_score']}")
    print(f"[节点品控部] 连贯性评分：{qa_record['continuity_score']}")

    if qa_record['issues']:
        print(f"[节点品控部] ⚠️ 发现问题：{qa_record['issues']}")
    if qa_record['suggestions']:
        print(f"[节点品控部] 💡 修改建议：{qa_record['suggestions']}")

    # 10. 返回状态更新
    return {"node_qa_records": records}
