# romantic_story/config.py
import os
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent

# 配置 API
OPENAI_API_KEY = "sk-0638b83c1e6a47eca1aeade34c493f6a"
OPENAI_API_BASE = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE

# 初始化 LLM
llm = ChatOpenAI(
    model=MODEL_NAME,
    temperature=0.7,
)

def get_agent(system_prompt: str):
    """
    创建深度 Agent 实例
    """
    return create_deep_agent(
        model=llm,
        system_prompt=system_prompt
    )