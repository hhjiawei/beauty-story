import json
import re


def clean_markdown(text: str) -> str:
    """移除 markdown 代码块标记"""
    text = re.sub(r'^```json\s*', '', text.strip())
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def fix_unescaped_quotes(raw: str) -> str:
    """
    修复 JSON 字符串值内部未转义的双引号。
    通过状态机判断引号是"字符串边界"还是"字符串内容"。
    """
    output = []
    in_string = False
    prev_char = None
    i = 0

    while i < len(raw):
        char = raw[i]

        if char == '"' and prev_char != '\\':
            if in_string:
                # 向前看：跳过空白，检查下一个字符是否是 JSON 结构符
                j = i + 1
                while j < len(raw) and raw[j] in ' \t\n\r':
                    j += 1

                if j < len(raw) and raw[j] in [',', ':', '}', ']', '\n']:
                    # 是字符串结束符
                    in_string = False
                    output.append('"')
                else:
                    # 是字符串内部的引号，需要转义
                    output.append('\\"')
            else:
                # 字符串开始
                in_string = True
                output.append('"')
        else:
            output.append(char)

        prev_char = char
        i += 1

    return ''.join(output)


def parse_json_response(content: str) -> dict:
    """完整的 JSON 解析流程：先尝试直接解析，失败则修复后重试"""
    cleaned = clean_markdown(content)

    # 第一次：尝试直接解析（可能是合法 JSON）
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 第二次：修复未转义引号后解析
    try:
        fixed = fix_unescaped_quotes(cleaned)
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        print(f"[JSON 解析错误] {e}")
        return {}
