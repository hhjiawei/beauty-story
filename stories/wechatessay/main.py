# romanticstory/main.py
from wechatessay.graph import create_main_workflow
from wechatessay.states.vx_state import GraphState


def main():
    app = create_main_workflow()

    initial_state: GraphState = {
        # ── 输入层 ──
        "input_path": "",  # 文章所在目录或文件路径（工作流入口）
        "articles_content": "",  # 可选：直接传入内容，跳过文件读取

        # ── map-reduce层 ──
        "map_reduce_content": {},  # 将文件内容通过map-reduce后的中间结果，最后会赋给analysis_result

        # ── 节点产出层（按工作流顺序） ──
        "analysis_result": {},  # 文章分析（热点追踪表）
        "search_result": {},  # 热点调研
        "blueprint_result": {},  # 写作蓝图
        "plot_result": {},  # 写作指令/情节
        "article_output": {},  # 最终文章输出

        # ── 控制与调试层 ──
        "error": "",  # 错误信息
        "raw_response": "",  # LLM 原始响应（调试）
        "current_node": ""  # 当前节点标识（追踪）
    }

    print("🚀 开始生成故事...")

    # 运行工作流
    for event in app.stream(initial_state):  # 这里加config
        for node_name, output in event.items():
            print(f"\n✅ 节点 [{node_name}] 处理完毕")
            print(event)

    print("\n" + "=" * 60)
    print("🎉 文章生成完毕！")
    print("=" * 60)




if __name__ == "__main__":
    main()
