import os
from typing import Literal
from tavily import TavilyClient
from langchain.tools import tool

TAVILY_API_KEY = "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"

tavily_client = TavilyClient(api_key=TAVILY_API_KEY)


@tool
def internet_search(
        query: str,
        max_results: int = 5,
        topic: Literal["general", "news", "finance"] = "general",
        include_raw_content: bool = False,
):
    """运行网络搜索"""
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )
