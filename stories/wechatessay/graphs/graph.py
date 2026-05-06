import json
import logging

from langgraph.constants import END, START
from langgraph.graph import StateGraph

from wechatessay.nodes.collect_node import search_collect_node
from wechatessay.nodes.analyse_node import blueprint_node

from wechatessay.nodes.plot_node import plot_node
from wechatessay.nodes.source_node import map_analyze_single, reduce_merge_results
from wechatessay.nodes.write_node import write_node
from wechatessay.states.vx_state import GraphState


def create_main_workflow():
    # main-graph

    main_graph = StateGraph(GraphState)

    main_graph.add_node("map_node", map_analyze_single)
    main_graph.add_node("reduce_node", reduce_merge_results)
    main_graph.add_node("collect_node", search_collect_node)
    main_graph.add_node("analyse_node", blueprint_node)
    main_graph.add_node("plot_node", plot_node)
    main_graph.add_node("write_node", write_node)

    main_graph.set_entry_point("map_node")
    main_graph.add_edge("map_node", "reduce_node")
    main_graph.add_edge("reduce_node", "collect_node")
    main_graph.add_edge("collect_node", "analyse_node")
    main_graph.add_edge("analyse_node", "plot_node")
    main_graph.add_edge("plot_node", "write_node")
    main_graph.add_edge("write_node", END)

    app = main_graph.compile()
    return app
