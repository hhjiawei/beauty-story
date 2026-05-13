"""
Legality Node - 合规性检测节点

职责：
1. 错别字检查
2. AI味检测
3. 敏感词审查
4. 事实核查
5. 版权风险检查
6. 极端情绪检查
7. 隐私泄露检查

Agent 模式：NodeAgent 执行合规检查，结合规则检查
"""

import json
import re
from typing import Dict, Any, List

from wechatessay.agents.agent_factory import get_node_agent, discover_tools_for_node
from wechatessay.states.vx_state import GraphState, LegalityNode as LegalityState
from wechatessay.prompts import vx_prompt
from wechatessay.utils.json_utils import parse_json_response
from wechatessay.config import DEFAULT_LLM_MODEL


# 敏感词
SENSITIVE_WORDS = [
    "反动", "颠覆", "分裂", "暴乱", "政变",
    "色情", "淫秽",
    "屠杀", "残杀", "血腥",
    "种族歧视", "地域歧视",
]

# AI 套话模式
AI_PATTERNS = [
    r"让我们", r"不难发现", r"总而言之", r"值得注意的是",
    r"在这个.*时代", r"随着.*的发展", r"这是一个.*的问题",
    r"相信.*会", r"笔者", r"本文", r"综上所述", r"由此可见",
]


def legality_node(state: GraphState, **kwargs) -> Dict[str, Any]:
    """合规检查节点"""
    print("\n" + "=" * 50)
    print("🔍 [legality_node] 开始合规检查")
    print("=" * 50)

    backend = kwargs.get("backend")
    store = kwargs.get("store")
    thread_id = kwargs.get("thread_id", "default")

    article_output = state.get("article_output", {})
    blueprint = state.get("blueprint_result", {})

    full_text = article_output.get("fullText", "")
    if not full_text:
        parts = article_output.get("parts", [])
        full_text = "\n\n".join([p.get("content", "") for p in parts])

    if not full_text:
        return {"error_message": "没有文章内容", "should_continue": False}

    # Agent + 规则双重检查
    legality_result = _check_with_agent(full_text, blueprint, backend, store, thread_id)

    if not legality_result:
        legality_result = _rule_based_check(full_text)

    # 显示结果
    print(f"   - 综合评分: {legality_result.get('overallScore', 0)}/100")
    print(f"   - AI味评分: {legality_result.get('aiFlavorScore', 0)}/100 (越低越好)")
    print(f"   - 是否通过: {'✅' if legality_result.get('isPassed') else '❌'}")
    issues = legality_result.get("issues", [])
    print(f"   - 问题数量: {len(issues)}")
    for issue in issues[:5]:
        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(issue.get("severity"), "⚪")
        print(f"     {emoji} [{issue.get('severity', '?')}] {issue.get('issueType', '?')}: {issue.get('suggestion', 'N/A')[:50]}")

    return {
        "legality_result": legality_result,
        "current_node": "legality_node"
    }


def _check_with_agent(
    article_content: str,
    blueprint: Dict,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> Dict:
    """使用 Agent 进行合规检查"""
    agent = get_node_agent(
        node_name="legality_node",
        system_prompt=vx_prompt.LEGALITY_SYSTEM_PROMPT,
        llm_model=DEFAULT_LLM_MODEL,
        temperature=0.3,
        max_tokens=6000,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )

    json_schema = vx_prompt.get_json_schema_prompt(LegalityState)

    user_prompt = vx_prompt.LEGALITY_USER_PROMPT_TEMPLATE.format(
        article_content=article_content[:2500],
        blueprint=json.dumps(blueprint, ensure_ascii=False, indent=2)[:1000],
        json_schema=json_schema
    )

    response = agent.invoke(user_prompt, max_iterations=5, use_memory=True)

    if not response:
        return None

    try:
        result = parse_json_response(response.content)

        # 合并规则检查结果
        rule_result = _rule_based_check(article_content)
        result['checkItems'] = rule_result.get('checkItems', [])

        # 合并问题
        existing = result.get('issues', [])
        seen = {i.get('location', '') for i in existing}
        for ri in rule_result.get('issues', []):
            if ri.get('location', '') not in seen:
                existing.append(ri)
        result['issues'] = existing

        score = _calc_score(existing, result.get('aiFlavorScore', 50))
        result['overallScore'] = score
        result['isPassed'] = score >= 70

        return result
    except Exception as e:
        print(f"  ⚠️ Agent 检查失败: {e}，使用规则检查")
        return None


def _rule_based_check(article_content: str) -> Dict:
    """规则检查（备用）"""
    issues = []
    check_items = []

    # 敏感词
    check_items.append("敏感词检查")
    for word in SENSITIVE_WORDS:
        if word in article_content:
            idx = article_content.find(word)
            issues.append({
                "issueType": "sensitive_word",
                "location": f"第{idx // 100 + 1}行附近",
                "originalText": word,
                "suggestion": f"移除或替换「{word}」",
                "severity": "high"
            })

    # AI味
    check_items.append("AI味检测")
    ai_count = 0
    for pattern in AI_PATTERNS:
        matches = re.findall(pattern, article_content)
        ai_count += len(matches)
        for match in matches:
            idx = article_content.find(match)
            issues.append({
                "issueType": "ai_flavor",
                "location": f"第{idx // 100 + 1}行附近",
                "originalText": match,
                "suggestion": f"替换AI套话「{match}」",
                "severity": "medium"
            })

    ai_score = max(0, 100 - ai_count * 10)

    # 标点
    check_items.append("标点符号检查")
    if re.search(r'[，。！？]{3,}', article_content):
        issues.append({
            "issueType": "typo",
            "location": "全文",
            "originalText": "连续标点",
            "suggestion": "避免连续使用多个标点",
            "severity": "low"
        })

    # 段落长度
    check_items.append("段落长度检查")
    for i, para in enumerate(article_content.split('\n')):
        if len(para) > 300:
            issues.append({
                "issueType": "typo",
                "location": f"第{i+1}段",
                "originalText": para[:50] + "...",
                "suggestion": "段落过长，建议拆分",
                "severity": "low"
            })

    score = _calc_score(issues, ai_score)

    return {
        "isPassed": score >= 70,
        "overallScore": score,
        "issues": issues,
        "typoCheck": [i["suggestion"] for i in issues if i["issueType"] == "typo"],
        "aiFlavorAnalysis": f"检测到 {ai_count} 处 AI 特征",
        "aiFlavorScore": ai_score,
        "suggestions": _gen_suggestions(issues),
        "correctedText": None,
        "checkItems": check_items
    }


def _calc_score(issues: List[Dict], ai_flavor_score: int) -> int:
    """计算评分"""
    base = 100
    for issue in issues:
        s = issue.get("severity", "low")
        base -= {"high": 15, "medium": 8, "low": 3}.get(s, 3)
    return max(0, min(100, int(base * 0.7 + ai_flavor_score * 0.3)))


def _gen_suggestions(issues: List[Dict]) -> List[str]:
    """生成优化建议"""
    suggestions = []
    high = sum(1 for i in issues if i.get("severity") == "high")
    ai = sum(1 for i in issues if i.get("issueType") == "ai_flavor")
    if high > 0:
        suggestions.append(f"优先处理 {high} 个高危问题")
    if ai > 3:
        suggestions.append("AI味较重，建议增加个人化表达")
    suggestions.append("通读全文确保语气自然流畅")
    suggestions.append("检查标点符号使用是否规范")
    return suggestions
