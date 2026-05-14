"""
wechatessay.main

项目入口文件。

使用方法：
    python -m wechatessay.main --input /path/to/articles.txt

工作流程：
1. 读取 txt 文件中的文章链接列表
2. 构建 LangGraph 并执行
3. 处理人机协同中断
4. 输出最终结果
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from wechatessay.config import MEMORY_CONFIG, MODEL_CONFIG, PUBLISH_CONFIG, RAG_CONFIG
from wechatessay.graphs.graph import build_graph, build_graph_no_hitl
from wechatessay.states.vx_state import GraphState
from wechatessay.utils.json_utils import safe_json_dump


def create_initial_state(input_path: str, writing_config: dict = None) -> GraphState:
    """
    创建初始 GraphState。

    Args:
        input_path: 文章链接 txt 文件路径
        writing_config: 写作配置覆盖项（可选）

    Returns:
        初始化的 GraphState
    """
    return GraphState(
        input_path=input_path,
        per_article_results=[],
        total_article_results=None,
        search_result=None,
        blueprint_result=None,
        plot_result=None,
        article_output=None,
        composition_result=None,
        legality_result=None,
        publish_result=None,
        current_node="",
        node_status={
            "source_node": "pending",
            "collect_node": "pending",
            "analyse_node": "pending",
            "plot_node": "pending",
            "write_node": "pending",
            "composition_node": "pending",
            "legality_node": "pending",
            "publish_node": "pending",
        },
        human_reviews=[],
        pending_human_review=None,
        revision_notes=None,
        retry_counts={
            "collect_node": 0,
            "analyse_node": 0,
            "plot_node": 0,
            "write_node": 0,
            "composition_node": 0,
            "legality_node": 0,
        },
        writing_config=writing_config or {},
        error_message=None,
        error_node=None,
    )


def save_result(state: GraphState, output_dir: str = "./output") -> str:
    """
    保存最终结果为 JSON 文件。

    Returns:
        输出文件路径
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"result_{timestamp}.json"

    # 序列化状态
    state_dict = _serialize_state(state)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(state_dict, f, ensure_ascii=False, indent=2, default=str)

    # 同时保存 HTML
    if state.get("publish_result"):
        html_file = out_dir / f"article_{timestamp}.html"
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(state["publish_result"].final_article_html)
        print(f"[main] HTML 已保存: {html_file}")

    # 同时保存纯文本
    if state.get("article_output"):
        txt_file = out_dir / f"article_{timestamp}.txt"
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write(state["article_output"].full_text)
        print(f"[main] 文本已保存: {txt_file}")

    print(f"[main] 结果已保存: {out_file}")
    return str(out_file)


def _serialize_state(state: GraphState) -> dict:
    """将 GraphState 序列化为可 JSON 化的字典。"""
    result = {}
    for key, value in state.items():
        if value is None:
            result[key] = None
        elif hasattr(value, "model_dump"):
            result[key] = value.model_dump(by_alias=True)
        elif isinstance(value, list):
            result[key] = [
                item.model_dump(by_alias=True) if hasattr(item, "model_dump") else item
                for item in value
            ]
        elif isinstance(value, dict):
            result[key] = {
                k: v.model_dump(by_alias=True) if hasattr(v, "model_dump") else v
                for k, v in value.items()
            }
        else:
            result[key] = value
    return result


def print_progress(state: GraphState) -> None:
    """打印当前进度。"""
    current = state.get("current_node", "")
    status = state.get("node_status", {})

    print(f"\n{'=' * 50}")
    print(f"当前节点: {current}")
    print(f"节点状态:")
    for node, st in status.items():
        icon = {
            "pending": "⏳",
            "running": "🔄",
            "waiting_human": "👤",
            "approved": "✅",
            "rejected": "❌",
            "completed": "✅",
            "failed": "💥",
        }.get(st, "❓")
        print(f"  {icon} {node}: {st}")

    if state.get("pending_human_review"):
        review = state["pending_human_review"]
        print(f"\n👤 等待人工审核: {review.get('node')}")
        print(f"说明: {review.get('instruction', '')}")

    if state.get("error_message"):
        print(f"\n💥 错误: {state['error_message']} (节点: {state.get('error_node')})")

    print(f"{'=' * 50}\n")


def run_workflow(
    input_path: str,
    no_hitl: bool = False,
    output_dir: str = "./output",
    writing_config: dict = None,
) -> GraphState:
    """
    执行完整工作流。

    Args:
        input_path: 文章链接 txt 文件路径
        no_hitl: 是否跳过人工审核（自动通过）
        output_dir: 输出目录
        writing_config: 写作配置

    Returns:
        最终状态
    """
    print(f"[main] 开始执行工作流")
    print(f"[main] 输入文件: {input_path}")
    print(f"[main] 人工审核: {'关闭' if no_hitl else '开启'}")

    # 1. 创建初始状态
    state = create_initial_state(input_path, writing_config)

    # 2. 构建图
    if no_hitl:
        graph = build_graph_no_hitl()
    else:
        graph = build_graph()

    # 3. 执行工作流
    try:
        final_state = graph.invoke(state)

        # 4. 处理可能的人工审核中断
        if not no_hitl and final_state.get("pending_human_review"):
            print_progress(final_state)
            print("[main] 工作流暂停，等待人工审核...")
            print("[main] 请检查 pending_human_review 内容并注入人工决策")
            return final_state

        # 5. 打印进度和保存结果
        print_progress(final_state)
        save_result(final_state, output_dir)

        return final_state

    except Exception as e:
        print(f"[main] 工作流执行失败: {e}")
        state["error_message"] = str(e)
        return state


def main():
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="微信公众号文章 AI 创作工作流")
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="文章链接 txt 文件路径",
    )
    parser.add_argument(
        "--no-hitl",
        action="store_true",
        help="跳过人工审核（自动通过）",
    )
    parser.add_argument(
        "--output", "-o",
        default="./output",
        help="输出目录",
    )
    parser.add_argument(
        "--style",
        default="口语化大白话",
        choices=["口语化大白话", "严肃科普", "共情引导", "讽刺犀利"],
        help="写作风格",
    )
    parser.add_argument(
        "--word-count",
        type=int,
        default=2000,
        help="目标字数",
    )

    args = parser.parse_args()

    writing_config = {
        "style": args.style,
        "word_count": args.word_count,
    }

    run_workflow(
        input_path=args.input,
        no_hitl=args.no_hitl,
        output_dir=args.output,
        writing_config=writing_config,
    )


if __name__ == "__main__":
    main()
