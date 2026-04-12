# romanticstory/main.py
from romanticstory.graph.workflow import create_workflow
from romanticstory.states.romantic_story_state import MainState


def main():
    app = create_workflow()

    initial_state: MainState = {
        "user_input": """全网搜索相关案例，找一篇关于农民工的爱情故事，进行改编""",
        "plan_state": {},
        "character_state": {},
        "plot_state": {},
        "current_segment_index": 0,
        "segments": [],
        "current_polish_index": 0  # ✅ 新增：抛光索引初始化为 0
    }

    print("🚀 开始生成故事...")

    # 运行工作流
    final_state = None
    for event in app.stream(initial_state):  # 这里加config
        for node_name, output in event.items():
            print(f"\n✅ 节点 [{node_name}] 处理完毕")
            print(event)
            final_state = output

    print("\n" + "=" * 60)
    print("🎉 故事生成完毕！")
    print("=" * 60)

    # 打印完整故事
    if final_state and "segments" in final_state:
        print("\n" + "=" * 60)
        print("📖 完整故事")
        print("=" * 60)

        full_story = ""
        for seg in final_state.get("segments", []):
            print(f"\n{'=' * 20} {seg['para_id']} {'=' * 20}")
            print(seg['content'])
            full_story += f"\n\n【{seg['para_id']}】\n{seg['content']}"

        print("\n" + "=" * 60)
        print(f"📊 完整故事总字数：{len(full_story)} 字符")
        print("=" * 60)


if __name__ == "__main__":
    main()
