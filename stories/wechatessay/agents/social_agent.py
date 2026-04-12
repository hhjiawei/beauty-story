import os

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, FilesystemBackend
from langchain_openai import ChatOpenAI

OPENAI_API_KEY = "468d6aba-3c9e-407f-ad91-d5f904662742"
OPENAI_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
MODEL_NAME = "doubao-seed-2-0-pro-260215"

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE

llm = ChatOpenAI(
    model=MODEL_NAME,
    temperature=1.5,
    max_tokens=30000
)

def create_social_agent():

    # 配置路由：默认临时，/memories/走永久存储
    composite_backend = lambda rt: CompositeBackend(
        default=StateBackend(rt),  # 默认用临时后端
        # /memories/路径走永久存储
        routes={"/memories/": FilesystemBackend(root_dir="E:\\pycode\\beauty-story\\stories\\wechatessay\\store\\memories", virtual_mode=True),
                "/workspace/": FilesystemBackend(root_dir="E:\\pycode\\beauty-story\\stories\\wechatessay\\store\\workspace", virtual_mode=True)
                }
    )

    # 创建智能体
    agent = create_deep_agent(
        name="",
        system_prompt="",
        model=llm,
        memory=[], # 额外的上下文
        skills=["/skills/main/"],
        subagents=[],
        backend=composite_backend

    )















