# romantic_story/config.py
import os

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent

# 配置 API
OPENAI_API_KEY = "sk-c619888c986041ba9646db331483d4c6"
OPENAI_API_BASE = "https://api.deepseek.com"
MODEL_NAME = "deepseek-reasoner"

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE

# 初始化 LLM
llm = ChatOpenAI(
    model=MODEL_NAME,
    temperature=0.7,
)


# llm = ChatOllama(
#     model="qwen3.5:35b",
#     base_url="http://localhost:11434",
#     num_predict=15000
# )
