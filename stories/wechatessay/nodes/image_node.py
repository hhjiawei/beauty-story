"""
wechatessay.nodes.image_node — 配图节点

设计：整个 huashu-wechat-image skill 目录作为 skills 参数，
agent 自主读取 SKILL.md 执行全流程。prompt 极简，不拆 skill。
节点流向：composition → image → publish
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Any


from deepagents import create_deep_agent

from wechatessay.agents.backend import load_backend
from wechatessay.config import MODEL_CONFIG, get_model_instance
from wechatessay.states.vx_state import (
    GeneratedImage,
    GraphState,
    ImageOutputNode,
)
from wechatessay.tools.image_tools.image_tool import upload_image, doubao_generate_image
from wechatessay.utils.json_utils import parse_json_response

logger = logging.getLogger(__name__)

SKILL_DIR = Path(__file__).resolve().parent.parent / "backends" / "skills" / "huashu-wechat-image"




def _create_agent() -> Any:
    """Create agent: skill→skills param, tools→generate_image+upload_image."""
    backend = load_backend()
    model = get_model_instance(MODEL_CONFIG.get("default_model"))
    skills = [str(SKILL_DIR)] if SKILL_DIR.exists() else []
    system_prompt = (
        "你是一个公众号配图助手。"
        "严格按照 skill 定义的工作流程为文章配图。"
        "\n工具: doubao_generate_image(生成图片), upload_image(上传图床)"
        "\n输出 JSON: coverImageUrl, bodyImageUrls[], articleWithImages, totalGenerated, imagePlan{}"
        "过程无需用户检查，直接输出最后结果，结果一定要 JSON结构，不许落盘，不许保存到文件夹，不许擅自加描述、总结等其他内容，你输出的结果只有JSON结构"
        "只要产生的JSON结构，必须在最后一个AIMessage中，后续不许产生任何message 不许产生toolMessage 和其他aiMessage"
        "任务完成后，确认下是否产生用户想要的实际内容，而不是概括的内容，也不是中间过程内容，是做好插图的内容"
    )
    return create_deep_agent(
        model=model, tools=[doubao_generate_image, upload_image],
        system_prompt=system_prompt, backend=backend,
        skills=skills, name="image_designer",
    )


def image_node(state: GraphState) -> GraphState:
    return asyncio.run(_async(state))


async def _async(state: GraphState) -> GraphState:
    composition = state.get("composition_result") # 都有哪些内容 可以用来丰富作图
    if not composition:
        state["error_message"] = "缺少 composition_result"
        state["error_node"] = "image_node"
        return state

    article = composition.formatted_article
    text = article or ""
    if not text:
        state["image_result"] = ImageOutputNode()
        state["current_node"] = "image_node"
        _mark_completed(state)
        return state

    # 图片插入位置
    image_placement = composition.format_spec.get("imagePlacement")

    # title = article.parts[0].title_alternatives[0] if article.parts else "未命名"
    # logger.info(f"[image_node] 配图: {title} ({len(text)}字)")

    try:
        agent = _create_agent()
        task = (
            f"请为以下文章配图。\n\n"
            # f"标题: {title}\n"
            f"字数: {len(text)}字\n\n"
            f"文章内容:\n{text}\n\n"
            f"图片插入位置参考: \n{image_placement}\n\n"
            f"请严格按照 SKILL.md 的工作流程完成。"
        )
        result = await agent.ainvoke({"messages": [{"role": "user", "content": task}]})
        response = result["messages"][-1].content if result.get("messages") else ""
    except Exception as e:
        logger.error(f"[image_node] 失败: {e}")
        state["error_message"] = f"配图失败: {e}"
        state["error_node"] = "image_node"
        return state

    image_result = _parse_result(response)

    if image_result.article_with_images:
        article.full_text = image_result.article_with_images
        if article.parts:
            article.parts[0].content = image_result.article_with_images
        state["composition_result"] = composition

    state["image_result"] = image_result
    state["current_node"] = "image_node"
    _mark_completed(state)
    logger.info(f"[image_node] 完成: {image_result.total_generated}张")
    return state


def _mark_completed(state: GraphState) -> None:
    """安全标记节点完成。"""
    if "node_status" not in state or state.get("node_status") is None:
        state["node_status"] = {}
    state["node_status"]["image_node"] = "completed"


def _parse_result(response: str) -> ImageOutputNode:
    try:
        data = parse_json_response(response)
        if not isinstance(data, dict):
            return ImageOutputNode()

        cover = data.get("coverImageUrl", "")
        body_urls = [
            u for u in data.get("bodyImageUrls", [])
            if isinstance(u, str) and u.startswith("http")
        ]
        body_images = [
            GeneratedImage(position=f"插图{i+1}", image_path=url, description="", ratio="16:9")
            for i, url in enumerate(body_urls)
        ]

        return ImageOutputNode(
            coverImagePath=cover if cover.startswith("http") else None,
            bodyImages=body_images,
            totalGenerated=data.get("totalGenerated", len(body_images) + (1 if cover.startswith("http") else 0)),
            articleWithImages=data.get("articleWithImages", ""),
        )
    except Exception:
        return ImageOutputNode()
