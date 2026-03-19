import os

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI




"""
故事架构师的deep agent

"""

OPENAI_API_KEY = "sk-0638b83c1e6a47eca1aeade34c493f6a"
OPENAI_API_BASE = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"
# 设置环境变量
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE

llm = ChatOpenAI(
    model=MODEL_NAME,
)


agent = create_deep_agent(
    model=llm,
    tools=[web_search],
    system_prompt=PLAN_SUMMARY_PROMPT
)




