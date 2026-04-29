import json
import logging

from langgraph.constants import END
from langgraph.graph import StateGraph

from wechatessay.nodes.source_node import map_analyze_single, reduce_merge_results
from wechatessay.states.vx_state import MapReduceState
from wechatessay.utils.vx_util import create_mapreduce_state


def build_mapreduce_graph(checkpointer=None):
    """构建 Map-Reduce 分析 Graph"""
    builder = StateGraph(MapReduceState)

    builder.add_node("map_analyze", map_analyze_single)
    builder.add_node("reduce_merge", reduce_merge_results)

    builder.set_entry_point("map_analyze")
    builder.add_edge("map_analyze", "reduce_merge")
    builder.add_edge("reduce_merge", END)

    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO)


    async def main():
        state = create_mapreduce_state(input_path="")
        graph = build_mapreduce_graph()
        result = await graph.ainvoke(state)

        if result.get("error"):
            print(f"错误: {result['error']}")

        if result.get("analysis_result"):
            print("\\n=== 最终汇总结果 ===")
            print(json.dumps(
                result["analysis_result"].model_dump(by_alias=True),
                ensure_ascii=False, indent=2
            ))

        print(f"\\n共分析 {len(result.get('per_article_results', []))} 篇文章")


    asyncio.run(main())







