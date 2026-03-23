import json
import re


def parse_json_response(content: str) -> dict:
    """
    解析 LLM 的 JSON 响应

    Args:
        content: LLM 返回的内容

    Returns:
        解析后的字典
    """
    try:
        # 清理 Markdown 代码块标记
        content = content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        content = content.strip()

        # 解析 JSON
        return json.loads(content)
    except Exception as e:
        print(f"[JSON 解析错误] {e}")
        return {}
