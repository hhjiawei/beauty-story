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

from langchain.tools import tool

from deepagents import create_deep_agent

from wechatessay.agents.backend import load_backend
from wechatessay.config import MODEL_CONFIG, get_model_instance
from wechatessay.states.vx_state import (
    GeneratedImage,
    GraphState,
    ImageOutputNode,
)
from wechatessay.utils.json_utils import parse_json_response

logger = logging.getLogger(__name__)

SKILL_DIR = Path(__file__).resolve().parent.parent / "backends" / "skills" / "huashu-wechat-image"


@tool
def generate_image(prompt: str, output_path: str, aspect: str = "wide") -> str:
    """Generate image via Gemini 3 Pro. Args: prompt(EN), output_path, aspect(cover/wide/standard/square)."""
    script = SKILL_DIR / "scripts" / "generate_image.py"
    if not script.exists():
        return f"Error: {script} not found"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = ["python3", str(script), "--prompt", prompt, "--filename", output_path, "--aspect", aspect]
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        cmd.extend(["--api-key", api_key])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and Path(output_path).exists():
            return f"OK: {output_path}"
        return f"Error: {r.stderr[:200]}"
    except Exception as e:
        return f"Error: {e}"


@tool
def upload_image(image_path: str) -> str:
    """Upload image to ImgBB, return permanent URL."""
    script = SKILL_DIR / "references" / "upload_image.py"
    if not script.exists():
        return f"Error: {script} not found"
    api_key = os.environ.get("IMGBB_API_KEY", "")
    if not api_key:
        return "Error: IMGBB_API_KEY not set"
    try:
        r = subprocess.run(["python3", str(script), image_path, "--api-key", api_key],
                          capture_output=True, text=True, timeout=120)
        for line in r.stdout.split("\n"):
            url = line.strip()
            if url.startswith("https://"):
                return url
        return f"Error: {r.stderr[:200]}"
    except Exception as e:
        return f"Error: {e}"


def _create_agent() -> Any:
    """Create agent: skill→skills param, tools→generate_image+upload_image."""
    backend = load_backend()
    model = get_model_instance(MODEL_CONFIG.get("default_model"))
    skills = [str(SKILL_DIR)] if SKILL_DIR.exists() else []
    system_prompt = (
        "你是一个公众号配图助手。"
        "严格按照 skill 定义的工作流程为文章配图。"
        "\n工具: generate_image(生成图片), upload_image(上传图床)"
        "\n输出 JSON: coverImageUrl, bodyImageUrls[], articleWithImages, totalGenerated, imagePlan{}"
    )
    return create_deep_agent(
        model=model, tools=[generate_image, upload_image],
        system_prompt=system_prompt, backend=backend,
        skills=skills, name="image_designer",
    )


def image_node(state: GraphState) -> GraphState:
    return asyncio.run(_async(state))


async def _async(state: GraphState) -> GraphState:
    composition = state.get("composition_result")
    if not composition:
        state["error_message"] = "缺少 composition_result"
        state["error_node"] = "image_node"
        return state

    article = composition.formatted_article
    text = article.full_text or ""
    if not text:
        state["image_result"] = ImageOutputNode()
        state["current_node"] = "image_node"
        _mark_completed(state)
        return state

    title = article.parts[0].title_alternatives[0] if article.parts else "未命名"
    logger.info(f"[image_node] 配图: {title} ({len(text)}字)")

    try:
        agent = _create_agent()
        task = (
            f"请为以下文章配图。\n\n"
            f"标题: {title}\n"
            f"字数: {len(text)}字\n\n"
            f"文章内容:\n{text[:6000]}\n\n"
            f"图片输出目录: /mnt/agents/output/images/\n"
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
