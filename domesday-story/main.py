"""
入口文件 - 程序启动点
"""
from graph.storyGraph import app
from config.config import OUTPUT_DIR
import os


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 末日爽文创作团队启动")
    print("=" * 60)

    # 用户输入
    user_input = input("\n📝 请输入故事主题：")
    if not user_input:
        user_input = "女主前世被闺蜜和男友骗进丧尸群，重生后回到末世前一个月，末世原因是脚气变异"
        print(f"使用默认主题：{user_input}")

    # 初始化状态
    initial_state = {
        "user_input": user_input,
        "world_building": {},
        "golden_finger": {},
        "character": {},
        "plot": {},
        "segments": [],
        "continuity": {},
        "rhythm": {},
        "sensory": {},
        "humor": {},
        "format": {},
        "node_qa_records": [],
        "final_qa": {},
        "continuity_tracker": {
            "timeline": [],
            "locations": [],
            "character_states": {},
            "prop_inventory": {},
            "plot_causality": []
        },
        "iteration_count": 0,
        "current_stage": "init",
        "current_segment_index": 0
    }

    print("\n⏳ 开始创作流程...")
    print("-" * 60)

    try:
        # 流式输出进度
        for chunk in app.stream(initial_state):
            for node_name, output in chunk.items():
                print(f"✅ 完成节点：[{node_name}]")

        print("-" * 60)
        print("🎉 创作完成！")

        # 获取最终状态
        final_state = app.invoke(initial_state)

        # 显示结果
        if final_state.get("format", {}).get("metadata", {}).get("file_path"):
            filepath = final_state["format"]["metadata"]["file_path"]
            word_count = final_state.get("format", {}).get("metadata", {}).get("word_count", 0)

            print(f"\n📁 文件已保存：{filepath}")
            print(f"📊 总字数：{word_count}")
            print(f"📂 输出目录：{OUTPUT_DIR}")

            # 询问是否打开文件
            open_file = input("\n是否打开文件查看？(y/n): ")
            if open_file.lower() == 'y':
                os.startfile(filepath)  # Windows
                # Mac/Linux 使用：os.system(f"open {filepath}")

    except Exception as e:
        print(f"\n❌ 发生错误：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()