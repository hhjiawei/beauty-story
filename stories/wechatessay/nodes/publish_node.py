"""
wechatessay.nodes.publish_node

节点8: publish_node — 发布节点（基于 wenyan-mcp）

职责：
1. 从 composition_result + image_result 获取排版后的文章
2. 将文章转为 Markdown 格式（含 frontmatter）
3. 通过 MCP 调用 wenyan-mcp 的 publish_article 工具
4. 发布到微信公众号草稿箱，获取 mediaId
5. 保存发布结果

依赖：
- wenyan-mcp 必须在 MCP 配置中启用
- WECHAT_APP_ID 和 WECHAT_APP_SECRET 环境变量已配置
- 运行机器 IP 已在微信公众号后台白名单中

节点流向：image → publish → END
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from wechatessay.config import PUBLISH_CONFIG
from wechatessay.states.vx_state import (
    CompositionNode,
    GraphState,
    ImageOutputNode,
    PublishNode,
)
from wechatessay.tools.mcp_tools.mcp_tool import mcp_manager

logger = logging.getLogger(__name__)

# wenyan-mcp 工具名前缀
WENYAN_SERVER_NAME = "wenyan"
PUBLISH_TOOL_NAME = "publish_article"


# ═══════════════════════════════════════════════
# Markdown 构造
# ═══════════════════════════════════════════════

def _extract_title(composition: CompositionNode) -> str:
    """从排版结果中提取文章标题。"""
    article = composition.formatted_article
    if article.parts and article.parts[0].title_alternatives:
        return article.parts[0].title_alternatives[0]
    return "未命名文章"


def _build_frontmatter(
    title: str,
    cover_path: Optional[str] = None,
    author: str = "",
    source_url: str = "",
) -> str:
    """构建 wenyan-mcp 所需的 frontmatter。"""
    lines = ["---", f"title: {title}"]

    if cover_path:
        lines.append(f"cover: {cover_path}")
    if author:
        lines.append(f"author: {author}")
    if source_url:
        lines.append(f"source_url: {source_url}")

    lines.append("---")
    return "\n".join(lines)


def _article_to_markdown(
    composition: CompositionNode,
    image_result: Optional[ImageOutputNode] = None,
) -> str:
    """
    将排版后的文章转为 Markdown 格式（含 frontmatter）。

    优先使用带图片标记的文章文本，否则使用原始排版文本。
    """
    title = _extract_title(composition)
    author = PUBLISH_CONFIG.get("default_author", "")

    # 封面图路径
    cover_path = None
    if image_result and image_result.cover_image_path:
        cover_path = image_result.cover_image_path

    # 文章正文（优先使用带图片标记的版本）
    if image_result and image_result.article_with_images:
        body = image_result.article_with_images
    else:
        body = composition.formatted_article.full_text or ""

    # 将 HTML 图片标记转为 Markdown 图片语法
    body = _convert_img_tags_to_markdown(body)

    # 构建 frontmatter + 正文
    frontmatter = _build_frontmatter(title, cover_path, author)

    return f"{frontmatter}\n\n{body}"


def _convert_img_tags_to_markdown(text: str) -> str:
    """
    将 HTML <img> 标签转为 Markdown 图片语法。

    <img src='path' alt='desc'> → ![desc](path)
    """
    import re

    # 匹配 <img src='...' alt='...'> 或 <img src="..." alt="...">
    def _replace_img(match: re.Match) -> str:
        src = match.group(1)
        alt = match.group(2) if match.group(2) else "插图"
        return f"\n\n![{alt}]({src})\n\n"

    # 匹配各种格式的 img 标签
    patterns = [
        r"<img\s+src=['\"]([^'\"]+)['\"]\s+alt=['\"]([^'\"]*)['\"][^>]*>",
        r"<img\s+alt=['\"]([^'\"]*)['\"]\s+src=['\"]([^'\"]+)['\"][^>]*>",
        r"<img\s+src=['\"]([^'\"]+)['\"][^>]*>",
    ]

    result = text
    for pattern in patterns:
        result = re.sub(pattern, _replace_img, result)

    return result


# ═══════════════════════════════════════════════
# wenyan-mcp 发布
# ═══════════════════════════════════════════════

async def _publish_via_wenyan_mcp(
    markdown_content: str,
    theme_id: str = "default",
    app_id: str = "",
) -> dict:
    """
    通过 wenyan-mcp 的 MCP 工具发布文章。

    Args:
        markdown_content: 含 frontmatter 的 Markdown 文本
        theme_id: wenyan-mcp 主题ID
        app_id: 微信公众号 AppID（多号发布时使用）

    Returns:
        {"success": bool, "media_id": str, "message": str}
    """
    try:
        # 获取 wenyan-mcp 的工具
        wenyan_tools = await mcp_manager.get_tools_by_server(WENYAN_SERVER_NAME)
        if not wenyan_tools:
            return {
                "success": False,
                "media_id": "",
                "message": f"wenyan-mcp 未配置或未连接。请检查 MCP 配置中是否启用了 {WENYAN_SERVER_NAME} 服务器。",
            }

        # 找到 publish_article 工具
        publish_tool = None
        for tool in wenyan_tools:
            if PUBLISH_TOOL_NAME in tool.name:
                publish_tool = tool
                break

        if publish_tool is None:
            return {
                "success": False,
                "media_id": "",
                "message": f"wenyan-mcp 中未找到 {PUBLISH_TOOL_NAME} 工具。可用工具: {[t.name for t in wenyan_tools]}",
            }

        logger.info(f"[publish_node] 调用 wenyan-mcp 发布文章，主题={theme_id}")

        # 构造工具参数
        tool_input = {
            "content": markdown_content,
            "theme_id": theme_id,
        }
        if app_id:
            tool_input["app_id"] = app_id

        # 调用 publish_article 工具
        result = await publish_tool.ainvoke(tool_input)

        # 解析结果
        if isinstance(result, str):
            # 工具返回字符串（通常是成功消息）
            if "media ID" in result or "成功" in result:
                # 提取 mediaId
                import re
                media_match = re.search(r"media\s*ID\s*is\s+(\w+)", result, re.IGNORECASE)
                media_id = media_match.group(1) if media_match else ""
                return {
                    "success": True,
                    "media_id": media_id,
                    "message": result,
                }
            else:
                return {
                    "success": False,
                    "media_id": "",
                    "message": result,
                }
        elif isinstance(result, dict):
            # 工具返回字典
            content = result.get("content", "")
            if isinstance(content, list) and content:
                text = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
            else:
                text = str(content)

            if "media ID" in text or "成功" in text:
                import re
                media_match = re.search(r"media\s*ID\s*is\s+(\w+)", text, re.IGNORECASE)
                media_id = media_match.group(1) if media_match else ""
                return {
                    "success": True,
                    "media_id": media_id,
                    "message": text,
                }
            else:
                return {
                    "success": False,
                    "media_id": "",
                    "message": text,
                }
        else:
            return {
                "success": False,
                "media_id": "",
                "message": f"未知返回格式: {type(result)} - {str(result)[:200]}",
            }

    except Exception as e:
        logger.error(f"[publish_node] wenyan-mcp 发布失败: {e}")
        return {
            "success": False,
            "media_id": "",
            "message": f"发布异常: {e}",
        }


# ═══════════════════════════════════════════════
# 节点入口
# ═══════════════════════════════════════════════

def publish_node(state: GraphState) -> GraphState:
    """同步入口包装。"""
    return asyncio.run(publish_node_async(state))


async def publish_node_async(state: GraphState) -> GraphState:
    """
    publish_node 主逻辑 — 通过 wenyan-mcp 发布到微信公众号草稿箱。

    流程：
    1. 读取 composition_result + image_result
    2. 构造 Markdown（含 frontmatter）
    3. 通过 MCP 调用 wenyan-mcp 的 publish_article
    4. 保存发布结果（mediaId + 状态）
    """
    composition = state.get("composition_result")
    if not composition:
        state["error_message"] = "缺少 composition_result"
        state["error_node"] = "publish_node"
        return state

    image_result = state.get("image_result")

    # 步骤1：构造 Markdown
    logger.info("[publish_node] 开始构造 Markdown...")
    markdown_content = _article_to_markdown(composition, image_result)

    # 提取封面路径和标题
    cover_path = image_result.cover_image_path if image_result else None
    title = _extract_title(composition)

    # 步骤2：获取主题配置
    theme_id = PUBLISH_CONFIG.get("theme_id", "default")
    app_id = PUBLISH_CONFIG.get("wechat_app_id", "")

    logger.info(f"[publish_node] 文章标题: {title}")
    logger.info(f"[publish_node] Markdown 长度: {len(markdown_content)} 字符")
    logger.info(f"[publish_node] 使用主题: {theme_id}")

    # 步骤3：通过 wenyan-mcp 发布
    publish_log = [f"[{datetime.now().isoformat()}] 开始发布到微信公众号"]

    result = await _publish_via_wenyan_mcp(
        markdown_content=markdown_content,
        theme_id=theme_id,
        app_id=app_id,
    )

    # 步骤4：保存结果
    if result["success"]:
        publish_status = "published"
        publish_log.append(f"[{datetime.now().isoformat()}] 发布成功，mediaId={result['media_id']}")
        publish_log.append(f"[{datetime.now().isoformat()}] 主题: {theme_id}")
        logger.info(f"[publish_node] 发布成功！mediaId={result['media_id']}")
    else:
        publish_status = "failed"
        publish_log.append(f"[{datetime.now().isoformat()}] 发布失败: {result['message']}")
        logger.error(f"[publish_node] 发布失败: {result['message']}")

    publish_node_result = PublishNode(
        themeId=theme_id,
        appId=app_id,
        markdownContent=markdown_content,
        coverImagePath=cover_path or "",
        mediaId=result.get("media_id", ""),
        publishStatus=publish_status,
        publishMessage=result.get("message", ""),
        publishLog=publish_log,
    )

    state["publish_result"] = publish_node_result
    state["current_node"] = "publish_node"
    state["node_status"]["publish_node"] = "completed"

    logger.info(f"[publish_node] 完成: 状态={publish_status}")
    return state
