import json
import logging

from langgraph.constants import END, START
from langgraph.graph import StateGraph

from wechatessay.nodes import collect_node, analyse_node
from wechatessay.nodes.plot_node import plot_node
from wechatessay.nodes.source_node import map_analyze_single, reduce_merge_results
from wechatessay.nodes.write_node import write_node
from wechatessay.states.vx_state import MapReduceState, GraphState


def create_sub_workflow():
    # sub-graph
    sub_map_reduce_graph = StateGraph(MapReduceState)
    sub_map_reduce_graph.add_node("map_node", map_analyze_single)
    sub_map_reduce_graph.add_node("reduce_node", reduce_merge_results)

    sub_map_reduce_graph.set_entry_point("map_node")
    sub_map_reduce_graph.add_edge("map_node", "reduce_node")
    sub_map_reduce_graph.add_edge("reduce_node", END)

    map_reduce_graph = sub_map_reduce_graph.compile()
    return map_reduce_graph


def create_main_workflow():
    # main-graph

    map_reduce_graph = create_sub_workflow()

    main_graph = StateGraph(GraphState)
    main_graph.add_node("map_reduce_node", map_reduce_graph)
    main_graph.add_node("collect_node", collect_node)
    main_graph.add_node("analyse_node", analyse_node)
    main_graph.add_node("plot_node", plot_node)
    main_graph.add_node("write_node", write_node)

    main_graph.add_edge(START, "map_reduce_node")
    main_graph.add_edge("map_reduce_node", "collect_node")
    main_graph.add_edge("collect_node", "analyse_node")
    main_graph.add_edge("analyse_node", "plot_node")
    main_graph.add_edge("plot_node", "write_node")
    main_graph.add_edge("write_node", END)

    app = main_graph.compile()
    return app
