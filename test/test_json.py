import json
import re

json_text = """
```json
{
  "hotspotTitle": "台军购预算大缩水：蓝白联手砍掉近半，1.25万亿变7800亿，美国急了",
  "verticalTrack": "台海局势/国际政治/军事博弈",
  "coreDemand": "台湾立法机构2026年5月8日表决通过蓝白版"军购特别条例"，将军购预算上限从赖清德当局要求的1.25万亿新台币砍至7800亿新台币。美方对此强烈不满，鼓动台当局继续增加防务投入。国台办回应称"以卵击石"，强调反对"台独"和外来干涉。",
  "emotionalTendency": "neutral",
  "writingStyle": "严肃科普",
  "writingStructure": "观点前置",
  "eventLine": [
    "2025年11月，赖清德绕过台湾社会和立法机构，向美媒投书宣布将提出400亿美元（约1.25万亿新台币）的"特别防务预算案"",
    "国民党与民众党质疑预算规模过大、项目不透明，多次联手阻挡该预算案推进",
    "蓝白阵营共同提出军购版本，分两批匡列总计7800亿新台币，其中第一波3000亿、第二波4800亿，全部用于采购美方武器",
    "2026年5月8日，台立法机构表决通过蓝白版"军购特别条例"，民进党民意代表因不满预算被削，集体投下弃权票",
    "美国国务院发言人称对预算"无益拖延"后终获通过"感到鼓舞"，同时鼓动台当局继续增加防务投入",
    "美国国务卿鲁比奥回应称对台政策不变，不希望现状发生强制改变",
    "国民党主席郑丽文批民进党"挂羊头卖狗肉"，呼吁扩大两岸和平对话与交流；台防务部门称排除部分采购项目恐造成"战力缺口"",
    "国台办发言人此前及后续多次强调，台湾是中国的台湾，美方应恪守一个中国原则，停止干涉中国内政"
  ],
  "regionScope": "中国台湾地区（台北市台湾立法机构）",
  "publicComplaints": "岛内民众质疑巨额军购预算规模过大、项目不透明，民进党当局过去采购制度漏洞百出，弊案连环（如马桶商、茶叶行都能标到防务案）却无人究责，被视为将台湾安全变成个人谋求权力和利益的工具",
  "dataComparison": {
    "keySpecificData": "预算上限从1.25万亿新台币降至7800亿新台币（削减约37.6%）；分两批：第一批3000亿新台币、第二批4800亿新台币；全部用于采购美方武器，不含台湾自主研发的无人机和导弹",
    "horizontalComparison": "赖清德当局原提出400亿美元（约1.25万亿新台币），蓝白版本降至7800亿新台币，对比削减约4700亿新台币"
  },
  "extendedContent": {
    "macroBackground": "台海局势持续紧张，中美博弈加剧背景下，美国持续通过军售介入台湾问题。赖清德当局试图通过巨额军购强化"以武拒统"能力，但岛内在野阵营及民众对财政负担和采购透明度提出强烈质疑。",
    "deepReasons": "军购预算被砍的直接原因是在野阵营对预算规模、项目透明度以及民进党采购制度弊案频出的不信任；深层原因则是岛内民众对巨额军购加重财政负担、以及"以武拒统"策略可持续性的普遍质疑，加之两岸和平对话的声音仍在岛内具有一定影响力。",
    "positiveFocus": "国民党主张"扩大两岸和平对话与交流，稳住两岸和平关系，排除所有战争和军事冲突的可能性"，展现出岛内仍有推动两岸和平对话的政治力量；蓝白联手制衡巨额军购，体现了民主制度下对财政透明和预算合理性的监督机制。"
  },
  "creationIdeas": [
    "【军费黑洞解剖】从"马桶商、茶叶行都能标防务案"切入，深挖台当局军购采购制度漏洞，揭露军购资金流向不透明的问题，引发读者对公帑使用的反思",
    "【台海博弈真相】以"美国急了"为视角，分析美方在台湾军购案中的真实利益诉求——并非真正关心台湾安全，而是借军售获取经济利益并牵制中国大陆",
    "【以小见大谈和平】以国民党郑丽文"扩大两岸和平对话与交流"的喊话为切入点，对比两岸在和平与发展方面的现实选择，探讨和平路径的可能性",
    "【普通人视角看军费】从1.25万亿→7800亿新台币的巨额数字落地到台湾普通民众的实际负担（税负、社会福利挤压等），拉近与读者距离，引发共情思考"
  ]
}
```

"""
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


# 使用
answer = parse_json_response(json_text)
print(answer)