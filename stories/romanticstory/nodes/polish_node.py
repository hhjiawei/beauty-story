# romanticstory/nodes/polish_node.py
import json
import os

from deepagents import create_deep_agent
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from romanticstory.config.config import llm
from romanticstory.prompts.romantic_story_prompt import POLISH_PROMPT
from romanticstory.states.romantic_story_state import MainState, SegmentState
from utils.json_util import parse_json_response


# 配置 API
OPENAI_API_KEY = "468d6aba-3c9e-407f-ad91-d5f904662742"
OPENAI_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
MODEL_NAME = "doubao-seed-2-0-pro-260215"

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE

# 初始化 LLM
"""
temperature 参数默认为 1.0。

我们建议您根据如下表格，按使用场景设置 temperature。
场景	温度
代码生成/数学解题 	0.0
数据抽取/分析	1.0
通用对话	1.3
翻译	1.3
创意类写作/诗歌创作	1.5  当模型的「温度」较高时（如 0.8、1 或更高），模型会更倾向于从较多样且不同的词汇中选择，这使得生成的文本风险性更高、创意性更强，
"""
llm = ChatOpenAI(
    model=MODEL_NAME,
    temperature=0.8,
)



def polish_node(state: MainState) -> dict:
    """
    抛光部：去 AI 感、检查标点符号、优化文风
    每次只处理一个段落，避免 token 限制
    """
    print("\n" + "=" * 60)
    print(f"[抛光部] 开始工作 - 段落索引：{state.get('current_polish_index', 0)}")
    print("=" * 60)

    # ===================================================================
    # 步骤 1: 从 MainState 提取必要信息
    # ===================================================================
    current_polish_index = state.get("current_polish_index", 0)
    segments = state.get("segments", [])

    # 安全检查：索引超出范围则直接返回
    if current_polish_index >= len(segments):
        print(f"[抛光部] ⚠️ 索引 {current_polish_index} 超出段落范围 {len(segments)}，完成抛光")
        return {"current_polish_index": current_polish_index}

    # 提取当前段落
    current_segment = segments[current_polish_index]

    print(f"[抛光部] 📋 当前段落：{current_segment.get('para_id', 'N/A')}")
    print(f"[抛光部] 📋 段落字数：{len(current_segment.get('content', ''))} 字符")

    # ===================================================================
    # 步骤 2: 构建抛光上下文（只包含当前段落）
    # ===================================================================
    polish_context = {
        "para_id": current_segment.get("para_id", ""),
        "content": current_segment.get("content", "")
    }

    # ===================================================================
    # 步骤 3: 构建消息并调用 LLM
    # ===================================================================


    # messages = [
    #     SystemMessage(content=POLISH_PROMPT),
    #     HumanMessage(content=f"""
    #     请对以下小说段落进行抛光处理：
    #
    #     【待抛光段落】
    #     {json.dumps(polish_context, ensure_ascii=False, indent=2)}
    #
    #     请输出 JSON 格式：{{"para_id": "P1", "content": "抛光后内容"}}
    #     """)
    # ]
    #
    # # 调用 LLM
    # response = llm.invoke(messages)


    agent = create_deep_agent(
        model=llm,
        system_prompt=POLISH_PROMPT,
    )

    response = agent.invoke({"messages": [HumanMessage(content=f"""
        请对以下小说段落进行抛光处理：

        【待抛光段落】
        {json.dumps(polish_context, ensure_ascii=False, indent=2)}

        请输出 JSON 格式：{{"para_id": "P1", "content": "抛光后内容"}}
        """)]})

    response = response["messages"][-1]

    # ===================================================================
    # 步骤 4: 解析响应并构建更新后的 segment
    # ===================================================================
    response_data = parse_json_response(response.content)

    # 获取抛光后的内容
    polished_content = response_data.get("content", "")

    # 如果解析失败，使用原始内容
    if not polished_content:
        print("[抛光部] ⚠️ 抛光解析失败，使用原始内容")
        polished_content = current_segment.get("content", "")

    # 构建更新后的 segment 对象
    updated_segment: SegmentState = {
        "para_id": current_segment.get("para_id", f"P{current_polish_index}"),
        "content": polished_content
    }

    # 更新 segments 列表
    updated_segments = segments[:current_polish_index] + [updated_segment] + segments[current_polish_index + 1:]

    # ===================================================================
    # 步骤 5: 打印当前段落抛光结果
    # ===================================================================
    print(f"\n[抛光部] ✅ 段落 {updated_segment['para_id']} 抛光完成")
    print(f"[抛光部] ✅ 抛光后字数：{len(polished_content)} 字符")
    print(f"[抛光部] 📝 内容预览：{polished_content[:200]}...")

    # ===================================================================
    # 步骤 6: 返回状态更新
    # ===================================================================
    return {
        "segments": updated_segments,
        "current_polish_index": current_polish_index + 1
    }
