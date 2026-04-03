# romanticstory/main.py
from romanticstory.graph.workflow import create_workflow
from romanticstory.states.romantic_story_state import MainState


def main():
    app = create_workflow()

    initial_state: MainState = {
        "user_input": """2022年底，湖南张家界，新娘吴某在婚礼前夜与网名为"小白龙"的男性网友相约见面，新娘与小白龙是长期炮友，两人在聊天记录中商定进行无保护性行为并涉及多人参与的露骨约定。次日便是吴某与新郎黄某的婚礼，黄某为这场婚姻已付出20万元彩礼。然而，"小白龙"事后竟在微信群中炫耀与新娘的私密聊天记录，内容恰好被新郎的朋友看到并转发给黄某。婚礼前夜，黄某得知自己即将迎娶的新娘竟在前一天与他人发生不正当关系，震惊与愤怒之下取消了婚礼。事件经网络传播后引发轩然大波，吴某退还全部彩礼并与黄某离婚，黄某母亲因此事气到住院，吴某本人也因铺天盖地的舆论压力一度传出轻生消息，最终远走他乡躲避风波，而"小白龙"则未受任何实质影响。这场婚礼闹剧以婚姻破裂、新娘身败名裂、新郎人财两空收场，不要凭空捏造其他人物和剧情，以女性视角为第一人称视角展开描述""",
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
