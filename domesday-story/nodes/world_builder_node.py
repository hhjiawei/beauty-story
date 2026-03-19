"""
世界观设定部节点
负责设计末日来源、世界规则、时间线、地理环境


#### 1. 世界观设定部 (World Building Dept)

| 项目 | 详细说明 |
|------|----------|
| **核心职责** | 设计末日来源、世界规则、时间线、地理环境 |
| **输入** | 用户主题、市场热点 |
| **输出** | 《世界观设定文档》(800-1000 字) |
| **连贯性保障** | ①明确末日爆发具体日期 ②定义变异规则边界 ③标注关键地点 |

"""
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from states.storyState import MainState
from prompts.storyPrompts import PROMPT_WORLD_BUILDER
from config.config import llm_default  # ✅ 直接导入预创建的 LLM 实例

# 初始化 LLM
llm = llm_default


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


def world_builder_node(state: MainState) -> dict:
    """
    世界观设定部节点函数

    Args:
        state: 主状态对象，包含用户输入等信息

    Returns:
        更新后的状态字典，包含世界观设定
    """
    print("\n" + "=" * 60)
    print("[世界观设定部] 开始工作")
    print("=" * 60)

    # 构建消息
    messages = [
        SystemMessage(content=PROMPT_WORLD_BUILDER),
        HumanMessage(content=state["user_input"])
    ]

    # 调用 LLM
    response = llm.invoke(messages)

    # 解析 JSON 响应
    world_data = parse_json_response(response.content)

    # 构建世界观状态对象
    world_building = {
        "apocalypse_name": world_data.get("apocalypse_name", "未知末日"), # 末日名称（4-10 字）
        "apocalypse_source": world_data.get("apocalypse_source", ""),   # 末日来源详细描述（300 字以上）
        "outbreak_date": world_data.get("outbreak_date", ""),           # 爆发具体日期时间
        "key_locations": world_data.get("key_locations", []),           # 地址信息
        "timeline": world_data.get("timeline", []),                     # 时间时间线
        "special_rules": world_data.get("special_rules", ""),           # 特殊设定及限制条件
        "qa_status": "PENDING",                                         # 质量保证状态
        "qa_feedback": ""                                               # 质量保证反馈
    }

    # 打印工作日志
    print(f"[世界观设定部] ✅ 完成：{world_building['apocalypse_name']}")
    print(f"[世界观设定部] 爆发时间：{world_building['outbreak_date']}")

    # 返回状态更新
    return {
        "world_building": world_building,
        "iteration_count": state["iteration_count"] + 1
    }
