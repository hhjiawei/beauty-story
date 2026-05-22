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

from wechatessay.config import (
    BACKEND_CONFIG,
    MEMORY_CONFIG,
    MODEL_CONFIG,
    PUBLISH_CONFIG,
    RAG_CONFIG,
    SOURCES_DIR,
)
from wechatessay.graphs.graph import build_graph, build_graph_no_hitl
from wechatessay.states.vx_state import GraphState


def resolve_input_path(input_path: str) -> str:
    """
    解析输入路径。

    规则：
    1. 如果传入的是相对路径（不含盘符/根路径），
       自动拼接为 project_root/backends/sources/{input_path}
    2. 如果传入的是绝对路径，原样返回
    3. 如果 path 是目录，扫描其中所有 .txt 文件并返回第一个
       （或直接返回目录路径由 source_node 扫描）

    示例：
        "articles.txt"        →  "{project}/backends/sources/articles.txt"
        "./articles.txt"      →  "{project}/backends/sources/articles.txt"
        "/abs/path/file.txt"  →  "/abs/path/file.txt"
        "C:\\data\\file.txt"  →  "C:\\data\\file.txt"
    """
    # 空路径保护
    if not input_path:
        raise ValueError("input_path 不能为空")

    # 先去掉前后空白和引号
    raw = input_path.strip().strip('"').strip("'")

    # 已经是绝对路径？（Unix /x 或 Windows C:\ 或 Windows \\server）
    p = Path(raw)
    if p.is_absolute():
        return str(p)

    # 相对路径 → 拼接到 backends/sources/
    sources_root = SOURCES_DIR
    resolved = sources_root / p
    return str(resolved.resolve())


def list_source_files(ext: str = ".txt") -> List[str]:
    """
    列出 backends/sources/ 目录下所有指定扩展名的文件。

    Returns:
        文件路径列表（相对于 sources 目录）
    """
    sources_root = SOURCES_DIR
    if not sources_root.exists():
        return []

    files = sorted(
        f.name for f in sources_root.iterdir()
        if f.is_file() and f.suffix.lower() == ext.lower()
    )
    return files


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

        # ── 逐段写作追踪（write_node 专用，初始值） ──
        current_segment_index=-1,       # -1 表示尚未开始
        segment_contents=[],            # 空的段落内容列表
        segment_golden_sentences=[],    # 空的金句列表
        segment_approved=[],            # 空的审核状态列表
        write_node_phase="",            # 空字符串，由 write_node 首次进入时初始化
        total_segments=0,               # 总段落数，由 write_node 根据大纲设置
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

"""

---

## 基本用法

```bash
# 进入项目根目录后执行
python -m wechatessay.main [参数]
```
---

## 参数说明

| 参数 | 简写 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `--input` | `-i` | `None` | 文章链接 txt 文件路径。只写文件名会自动定位到 `backends/sources/` 目录 |
| `--no-hitl` | — | `False` | **跳过人工审核**，全自动跑完（HITL = Human In The Loop） |
| `--output` | `-o` | `./output` | 结果输出目录 |
| `--style` | — | `口语化大白话` | 写作风格，可选：`口语化大白话`、`严肃科普`、`共情引导`、`讽刺犀利` |
| `--word-count` | — | `2000` | 目标字数 |

---

## 使用场景示例

### 场景 1：不指定文件，自动使用 `backends/sources/` 下的第一个 txt
```bash
python -m wechatessay.main
```
> 如果 `backends/sources/` 下有多个 `.txt`，它会列出清单并**默认选第一个**。

### 场景 2：指定 `backends/sources/` 目录下的某个文件
```bash
# 只写文件名即可，自动解析到 backends/sources/articles.txt
python -m wechatessay.main --input articles.txt

# 或者
python -m wechatessay.main -i hot_news.txt
```

### 场景 3：指定绝对路径（任意位置的文件）
```bash
python -m wechatessay.main -i /home/user/data/my_links.txt
```

### 场景 4：全自动模式（无人值守）
```bash
python -m wechatessay.main -i articles.txt --no-hitl
```

### 场景 5：指定风格和字数
```bash
python -m wechatessay.main \
  -i articles.txt \
  --style "讽刺犀利" \
  --word-count 3000 \
  -o ./output_articles
```

---

## 文件内容要求

`--input` 指向的 `.txt` 文件里，**每行应该是一个文章链接**，例如：

```text
https://mp.weixin.qq.com/s/xxxxxxxxx
https://mp.weixin.qq.com/s/yyyyyyyyy
https://zhuanlan.zhihu.com/p/zzzzzzzzz
```

---

## 输出结果

运行结束后会在 `--output` 目录（默认 `./output`）生成：

| 文件 | 说明 |
|:---|:---|
| `result_YYYYMMDD_HHMMSS.json` | 完整状态序列化（包含所有节点结果） |
| `article_YYYYMMDD_HHMMSS.html` | 最终排版好的公众号 HTML |
| `article_YYYYMMDD_HHMMSS.txt` | 最终文章纯文本 |

---

## 一个完整的生产环境命令

```bash
python -m wechatessay.main \
  -i today_hot.txt \
  --style "口语化大白话" \
  --word-count 2500 \
  --no-hitl \
  -o ./output/$(date +%Y%m%d)
```

---

## 注意事项

1. **路径解析规则**：如果你给的是相对路径（如 `articles.txt`），它会自动拼接到项目根目录下的 `backends/sources/articles.txt`
2. **人工审核**：默认开启 HITL，工作流会在需要人工确认的节点**暂停**，此时需要检查 `pending_human_review` 并注入决策才能继续
3. **依赖检查**：确保 `.venv` 或环境里已安装 `langgraph`、`deepagents` 等项目依赖

如果你是想**在代码里直接调用**而不是走命令行，也可以这样：

```python
from wechatessay.main import run_workflow

final_state = run_workflow(
    input_path="backends/sources/articles.txt",
    no_hitl=True,
    writing_config={"style": "口语化大白话", "word_count": 2000}
)
```

需要我帮你把常用的命令写成 **shell/bat 脚本** 吗？

"""
def main():
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="微信公众号文章 AI 创作工作流")
    parser.add_argument(
        "--input", "-i",
        default=None,
        help="文章链接 txt 文件路径。相对文件名自动解析到 backends/sources/（如 'articles.txt'）",
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
        default=3000,
        help="目标字数",
    )

    args = parser.parse_args()

    # ── 解析 input_path ──
    if args.input:
        raw_input = args.input
    else:
        # 未指定 --input，列出 sources 目录下的可用文件
        available = list_source_files(".txt")
        if not available:
            print(f"⚠️  {SOURCES_DIR} 目录下没有找到 .txt 文件")
            print(f"   请将文章链接列表 txt 文件放入该目录，或用 --input 指定路径")
            return
        print(f"📁 发现以下 txt 文件（在 {SOURCES_DIR}）：")
        for i, f in enumerate(available, 1):
            print(f"   {i}. {f}")
        raw_input = available[0]
        print(f"   默认使用: {raw_input}")

    # 解析为完整路径
    input_path = resolve_input_path(raw_input)
    print(f"📄 输入文件: {input_path}")

    # ── 执行 ──
    writing_config = {
        "style": args.style,
        "word_count": args.word_count,
    }

    run_workflow(
        input_path=input_path,
        no_hitl=args.no_hitl,
        output_dir=args.output,
        writing_config=writing_config,
    )


if __name__ == "__main__":
    main()