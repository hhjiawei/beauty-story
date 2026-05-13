"""
微信公众号文章创作工作流 - 主程序入口（v2 架构）

基于 LangGraph + DeepAgents 的完整文章创作工作流。

使用方法:
    python main.py --input articles.txt [--auto] [--memory]

v2 架构改进：
- 使用 create_deep_agent 创建节点 Agent
- CompositeBackend 持久化聊天记录到 records
- Memory 三层机制：Context + RAG + Summarization
- 工具动态注册，不硬编码
- Skill 自动加载
"""

import os
import sys
import json
import argparse
import uuid
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv
load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    print("⚠️ 警告: OPENAI_API_KEY 未设置，请在 .env 文件中配置")

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from graphs.graph import create_graph, init_deepagents_backend
from states.vx_state import GraphState
from wechatessay.config import HUMAN_IN_THE_LOOP, MEMORY_DIR
from agents.memory_manager import get_memory_manager
from agents.chat_history_store import get_chat_history_store


class InteractiveCLI:
    """交互式命令行界面"""

    def display_welcome(self):
        print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║         📝 微信公众号文章 AI 创作工作流 v2.0                  ║
║                                                              ║
║    LangGraph + DeepAgents + Memory + Skills                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """)

    def display_progress(self, state: Dict[str, Any]):
        current_node = state.get("current_node", "unknown")
        node_names = {
            "load_memories": "📚 加载记忆",
            "source_node": "📚 读取文章",
            "total_analysis_node": "📊 汇总分析",
            "collect_node": "🔍 收集信息",
            "analyse_node": "🎯 分析角度",
            "plot_node": "📋 设计大纲",
            "write_node": "✍️ 写作文章",
            "composition_node": "🎨 排版设计",
            "legality_node": "🔍 合规检查",
            "publish_node": "🚀 发布文章",
        }
        print(f"\n{'─' * 50}")
        print(f"当前步骤: {node_names.get(current_node, current_node)}")
        print(f"{'─' * 50}")

    def get_human_feedback(self, prompt: str = "") -> str:
        print()
        if prompt:
            print(prompt)
        print("\n💬 请输入反馈:")
        print("   ✅ ok / 满意  → 继续")
        print("   📝 修改意见    → 重新执行")
        print("   ❌ stop       → 结束")
        print()
        try:
            return input("您的反馈 > ").strip() or "ok"
        except (EOFError, KeyboardInterrupt):
            return "stop"

    def display_result(self, state: Dict[str, Any]):
        publish_result = state.get("publish_result", {})
        print("""
╔══════════════════════════════════════════════════════════════╗
║                      ✅ 工作流完成                            ║
╚══════════════════════════════════════════════════════════════╝""")
        if publish_result:
            print(f"📰 标题: {publish_result.get('finalTitle', 'N/A')}")
            print(f"📝 摘要: {publish_result.get('summary', 'N/A')[:100]}...")
            print(f"🏷️ 关键词: {', '.join(publish_result.get('keywords', []))}")
            print(f"💾 草稿: {publish_result.get('originalDraftPath', 'N/A')}")

        memories = state.get("revision_memories", [])
        if memories:
            print(f"\n📊 共记录 {len(memories)} 条修改意见")


def run_workflow(input_path: str, auto_mode: bool = False) -> Dict[str, Any]:
    """
    执行工作流
    """
    cli = InteractiveCLI()
    cli.display_welcome()

    if not os.path.exists(input_path):
        print(f"❌ 文件不存在: {input_path}")
        return {}

    # 初始化 DeepAgents Backend
    print("🚀 初始化 DeepAgents Backend...")
    composite_backend, store = init_deepagents_backend()

    # 初始化 Memory
    memory = get_memory_manager(backend=composite_backend, store=store)

    # 初始化 ChatHistoryStore
    thread_id = str(uuid.uuid4())[:8]
    chat_store = get_chat_history_store(backend=composite_backend, thread_id=thread_id)

    # 创建图
    graph = create_graph(
        backend=composite_backend,
        store=store,
        thread_id=thread_id,
    )

    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 100
    }

    initial_state: GraphState = {
        "input_path": input_path,
        "per_article_results": [],
        "total_article_results": None,
        "search_result": None,
        "blueprint_result": None,
        "plot_result": None,
        "article_output": None,
        "composition_result": None,
        "legality_result": None,
        "publish_result": None,
        "current_node": "",
        "human_feedback": None,
        "awaiting_human": False,
        "revision_count": 0,
        "should_continue": True,
        "error_message": None,
        "user_memories": [],
        "revision_memories": []
    }

    print(f"📁 输入: {input_path}")
    print(f"🧵 线程: {thread_id}")
    print(f"🤖 人机协同: {'开启' if HUMAN_IN_THE_LOOP and not auto_mode else '关闭'}")
    print(f"🧠 Memory: Context + RAG + Summarization")
    print(f"💾 ChatHistory: CompositeBackend records/")
    print()

    try:
        current_state = initial_state

        for event in graph.stream(initial_state, config, stream_mode="values"):
            current_state = event

            if current_state.get("error_message"):
                print(f"\n❌ 错误: {current_state['error_message']}")
                return current_state

            current_node = current_state.get("current_node", "")
            if current_node:
                cli.display_progress(current_state)

            # 人机协同
            if current_state.get("awaiting_human") and not auto_mode:
                feedback = cli.get_human_feedback()
                current_state["human_feedback"] = feedback
                current_state["awaiting_human"] = False

                if feedback.lower() not in ["ok", "满意", "continue", "y", "yes"]:
                    current_state["revision_count"] = current_state.get("revision_count", 0) + 1
                    current_state["revision_memories"].append({
                        "node": current_node,
                        "feedback": feedback
                    })

                if feedback.lower() in ["stop", "终止", "结束", "exit", "quit"]:
                    current_state["should_continue"] = False
                    print("\n🛑 已终止")
                    return current_state

                continue

            if current_state.get("publish_result"):
                break

        cli.display_result(current_state)
        return current_state

    except Exception as e:
        print(f"\n❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return current_state if 'current_state' in locals() else initial_state


def main():
    parser = argparse.ArgumentParser(
        description="微信公众号文章 AI 创作工作流 v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py --input articles.txt           # 交互模式
  python main.py --input articles.txt --auto    # 自动模式
  python main.py --memory                       # 查看记忆
  python main.py --reset                        # 重置记忆
        """
    )
    parser.add_argument("--input", "-i", type=str, help="文章链接 txt 文件路径")
    parser.add_argument("--auto", "-a", action="store_true", help="自动模式")
    parser.add_argument("--memory", "-m", action="store_true", help="查看记忆")
    parser.add_argument("--reset", "-r", action="store_true", help="重置记忆")
    args = parser.parse_args()

    if args.memory:
        memory_file = Path(MEMORY_DIR) / "user_memories.json"
        if memory_file.exists():
            with open(memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                print("📚 用户记忆:")
                for i, m in enumerate(data.get("memories", []), 1):
                    print(f"  {i}. {m}")
        else:
            print("📚 暂无记忆")
        return

    if args.reset:
        memory_file = Path(MEMORY_DIR) / "user_memories.json"
        if memory_file.exists():
            memory_file.unlink()
        print("🗑️ 记忆已重置")
        return

    if not args.input:
        print("❌ 请指定 --input")
        parser.print_help()
        return

    final_state = run_workflow(args.input, auto_mode=args.auto)

    if final_state:
        state_file = Path(ROOT) / "backends" / "workspaces" / "last_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            simple = {k: v for k, v in final_state.items()
                     if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(simple, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n💾 状态已保存: {state_file}")
        except Exception as e:
            print(f"⚠️ 保存失败: {e}")


if __name__ == "__main__":
    main()
