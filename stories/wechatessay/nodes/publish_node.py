"""
Publish Node - 发布节点

职责：
1. 整理发布所需全部信息
2. 生成文章摘要和关键词
3. 准备朋友圈转发文案
4. 保存最终草稿

Agent 模式：NodeAgent 执行发布整理
"""

import json
import os
from datetime import datetime
from typing import Dict, Any

from wechatessay.agents.agent_factory import get_node_agent, discover_tools_for_node
from wechatessay.states.vx_state import GraphState, PublishNode
from wechatessay.prompts import vx_prompt
from wechatessay.utils.json_utils import parse_json_response
from wechatessay.config import DEFAULT_LLM_MODEL, WORKSPACE_DIR


def publish_node(state: GraphState, **kwargs) -> Dict[str, Any]:
    """发布节点"""
    print("\n" + "=" * 50)
    print("🚀 [publish_node] 开始整理发布信息")
    print("=" * 50)

    backend = kwargs.get("backend")
    store = kwargs.get("store")
    thread_id = kwargs.get("thread_id", "default")

    article_output = state.get("article_output", {})
    composition_result = state.get("composition_result", {})
    legality_result = state.get("legality_result", {})
    blueprint = state.get("blueprint_result", {})

    tools = discover_tools_for_node("publish_node")
    print(f"  🔧 publish_node 可用工具: {[t.name for t in tools]}")

    full_text = article_output.get("fullText", "")
    if not full_text:
        parts = article_output.get("parts", [])
        full_text = "\n\n".join([p.get("content", "") for p in parts])

    title = "未命名文章"
    parts = article_output.get("parts", [])
    if parts and parts[0].get("titleAlternatives"):
        title = parts[0]["titleAlternatives"][0]
    else:
        wt = blueprint.get("writingTemplate", {})
        if wt:
            title = wt.get("title", title)

    publish_result = _prepare_publish(
        title=title,
        content=full_text,
        composition=composition_result,
        legality=legality_result,
        blueprint=blueprint,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    draft_path = _save_draft(title, full_text, composition_result)
    publish_result["originalDraftPath"] = draft_path

    print(f"   - 标题: {publish_result.get('finalTitle', 'N/A')[:40]}")
    print(f"   - 草稿路径: {draft_path}")

    return {
        "publish_result": publish_result,
        "should_continue": False,
        "current_node": "publish_node"
    }


def _prepare_publish(
    title: str,
    content: str,
    composition: Dict,
    legality: Dict,
    blueprint: Dict,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """使用 Agent 整理发布信息"""
    agent = get_node_agent(
        node_name="publish_node",
        system_prompt=vx_prompt.PUBLISH_SYSTEM_PROMPT,
        llm_model=DEFAULT_LLM_MODEL,
        temperature=0.5,
        max_tokens=2000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    json_schema = vx_prompt.get_json_schema_prompt(PublishNode)

    user_prompt = vx_prompt.PUBLISH_USER_PROMPT_TEMPLATE.format(
        article_content=content[:1500],
        composition_result=json.dumps(composition, ensure_ascii=False, indent=2)[:1000],
        legality_result=json.dumps(legality, ensure_ascii=False, indent=2)[:500],
        blueprint=json.dumps(blueprint, ensure_ascii=False, indent=2)[:500],
        json_schema=json_schema
    )

    response = agent.invoke(user_prompt, max_iterations=5, use_memory=True)

    if not response:
        return _default_publish(title, content)

    try:
        result = parse_json_response(response.content)
        result.setdefault('finalTitle', title)
        result.setdefault('finalContent', content)
        result.setdefault('isPublished', False)
        result.setdefault('publishTime', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return result
    except Exception:
        return _default_publish(title, content)


def _default_publish(title: str, content: str) -> Dict:
    """默认发布信息"""
    summary = content[:100] + "..." if len(content) > 100 else content
    keywords = [w for w in title.replace("，", " ").split() if len(w) > 2][:5]
    if not keywords:
        keywords = ["公众号文章"]

    return {
        "platforms": [{"platformName": "微信公众号", "isEnabled": True}],
        "finalTitle": title,
        "finalContent": content,
        "summary": summary,
        "keywords": keywords,
        "coverImageUrl": None,
        "isPublished": False,
        "publishTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "originalDraftPath": None
    }


def _save_draft(title: str, content: str, composition: Dict) -> str:
    """保存草稿"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in '._-' else '_' for c in title[:20])

    draft_dir = os.path.join(WORKSPACE_DIR, "drafts")
    os.makedirs(draft_dir, exist_ok=True)

    md_path = os.path.join(draft_dir, f"{safe}_{ts}.md")
    md_content = f"""# {title}

> 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

{content}

---

*本文由 AI 辅助创作*
"""
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"  ✅ Markdown 草稿已保存: {md_path}")
    except Exception as e:
        print(f"  ⚠️ 保存失败: {e}")

    # HTML 版本
    html = composition.get("formattedHtml", "")
    if html:
        html_path = os.path.join(draft_dir, f"{safe}_{ts}.html")
        try:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  ✅ HTML 草稿已保存: {html_path}")
        except Exception as e:
            print(f"  ⚠️ HTML 保存失败: {e}")

    return md_path
