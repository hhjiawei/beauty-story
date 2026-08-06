"""LangChain 聊天模型适配层：把流水线「模型档案」转成 deepagents 可用的 BaseChatModel。

- provider=mock   → MockRouterChatModel（按 system 中的 <!-- NODE:xxx --> 标记路由，
                    零依赖演示/测试；复用 mock_llm_responses.ROUTERS）
- provider=openai → ChatOpenAI（OpenAI 兼容端点：DeepSeek/Kimi/Qwen 等均可）
- 其他 provider   → 尝试 init_chat_model("provider:model")（anthropic/google_genai...）
"""
from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from ..models import ModelProfile


def _content_text(content: Any) -> str:
    """LangChain 消息 content 可能是 str 或 content-block 列表，统一取文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return str(content or "")


class MockRouterChatModel(BaseChatModel):
    """按 system 消息里的 <!-- NODE:xxx --> 标记路由到 mock_llm_responses 生成器。

    deepagents 会把技能元数据等附加到 system prompt，但 NODE 标记始终在文首，
    路由逻辑与旧 MockChatModel 完全一致。工具绑定直接透传（mock 不发起工具调用，
    各节点 canned 输出即最终答复）。
    """

    @property
    def _llm_type(self) -> str:
        return "mock-router"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        from .. import mock_llm_responses

        system_text = "\n".join(
            _content_text(m.content) for m in messages if m.type == "system"
        )
        user_text = _content_text(messages[-1].content) if messages else ""
        for marker, fn in mock_llm_responses.ROUTERS.items():
            if marker in system_text:
                return ChatResult(generations=[ChatGeneration(
                    message=AIMessage(content=fn(system_text, user_text)))])
        raise ValueError(
            f"MockRouterChatModel: 未识别的节点标记（system 前 120 字：{system_text[:120]!r}）"
        )


def chat_model_for_profile(profile: ModelProfile) -> BaseChatModel:
    """模型档案 → LangChain BaseChatModel（deepagents model= 入参）。"""
    if profile.provider == "mock":
        return MockRouterChatModel()
    if profile.provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=profile.model,
            api_key=profile.api_key,
            base_url=profile.base_url or None,
            temperature=profile.temperature,
            timeout=300,
            max_retries=2,
        )
    # 其他厂商：走 langchain 统一初始化（需自行安装对应集成包）
    from langchain.chat_models import init_chat_model

    return init_chat_model(f"{profile.provider}:{profile.model}",
                           temperature=profile.temperature)
