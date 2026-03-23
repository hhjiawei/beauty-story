"""
格式标准化部节点
统一格式，适配手机阅读，准备发布
"""
import json
import os
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
from domesday.states.storyState import MainState
from domesday.config.config import MODEL_NAME, TEMPERATURE, OUTPUT_DIR, generate_filename




def format_node(state: MainState) -> dict:
    """
    格式标准化部节点函数

    Args:
        state: 主状态对象，包含幽默增强稿和全流程状态

    Returns:
        更新后的状态字典，包含标准格式终稿和文件路径
    """
    print("\n" + "=" * 60)
    print("[格式标准化部] 开始工作")
    print("=" * 60)

    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = generate_filename("story")
    filepath = os.path.join(OUTPUT_DIR, filename)

    # 构建 MD 内容
    md_content = f"""# 📖 末日复仇爽文

## 📋 创作信息
- **创作时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **作品 ID**: {timestamp}
- **总字数**: {len(state['humor']['humor_enhanced'])} 字
- **故事主题**: {state.get('user_input', '未知')}

## 🎯 核心设定

### 世界观
{state.get('world_building', {}).get('apocalypse_source', '无')}

### 金手指
{state.get('golden_finger', {}).get('ability_type', '无')}

### 人物关系
主角：{state.get('character', {}).get('protagonist', {}).get('name', '未知')}
仇人：{len(state.get('character', {}).get('villains', []))} 个

## 📝 正文内容

{state['humor']['humor_enhanced']}

---
## 📊 创作统计
- **段落数**: {len(state.get('segments', []))}

---
*本作品由 AI 创作团队自动生成 | 末日爽文工厂*
"""

    # 保存文件
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 构建格式状态对象
    format_state = {
        "final_draft": state['humor']['humor_enhanced'],
        "md_content": md_content,
        "json_content": "",
        "metadata": {
            "work_id": timestamp,
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0",
            "word_count": len(state['humor']['humor_enhanced']),
            "timeline_summary": state.get('plot', {}).get('timeline_summary', ''),
            "file_path": filepath
        },
        "file_paths": {"md": filepath},
        "qa_status": "PENDING",
        "qa_feedback": ""
    }

    # 打印工作日志
    print(f"[格式标准化部] ✅ 完成")

    # 返回状态更新
    return {"format": format_state}
