from wechatessay.prompts.vx_prompt import SOURCE_PROMPT
from wechatessay.states.vx_state import Creating
from wechatessay.tools.vx_tools import read_file, tavily_web_search





# 根据用户输入内容，读取input路径下的所有文章，生成《热点追踪表》（含事件背景/信源清单/切入角度/风险评级），时间线、争议点标注



source_sub_agent = {
    "name": "source-sub-agent",
    "description": "解析输入的民生类文章素材，提取碎片化信息并进行结构化整理，生成标准化的热点追踪表信息，将信息结构化输出到Creating对象",
    "system_prompt": SOURCE_PROMPT,
    "tools": [read_file],
    "model": "openai:gpt-5.4",
    "skills": [],
    "response_format": Creating,
}


collect_sub_agent = {
    "name": "collect-sub-agent",
    "description": "Used to research more in depth questions",
    "system_prompt": "You are a great researcher",
    "tools": [],
    "model": "openai:gpt-5.4",
    "skills": [],
}


analyse_sub_agent = {
    "name": "analyse-sub-agent",
    "description": "Used to research more in depth questions",
    "system_prompt": "You are a great researcher",
    "tools": [],
    "model": "openai:gpt-5.4",
    "skills": [],
}


plot_sub_agent = {
    "name": "plot-sub-agent",
    "description": "Used to research more in depth questions",
    "system_prompt": "You are a great researcher",
    "tools": [],
    "model": "openai:gpt-5.4",
    "skills": [],
}


write_sub_agent = {
    "name": "write-sub-agent",
    "description": "Used to research more in depth questions",
    "system_prompt": "You are a great researcher",
    "tools": [],
    "model": "openai:gpt-5.4",
    "skills": [],
}



composition_sub_agent = {
    "name": "composition-sub-agent",
    "description": "Used to research more in depth questions",
    "system_prompt": "You are a great researcher",
    "tools": [],
    "model": "openai:gpt-5.4",
    "skills": [],
}


legality_sub_agent= {
    "name": "legality-sub-agent",
    "description": "Used to research more in depth questions",
    "system_prompt": "You are a great researcher",
    "tools": [],
    "model": "openai:gpt-5.4",
    "skills": [],
}

