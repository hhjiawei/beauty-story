"""LLM 接入抽象。

- OpenAICompatChatModel：OpenAI 兼容协议（/chat/completions），每节点独立档案
- MockChatModel：演示与测试用，按 system prompt 中的节点标记路由到 canned 生成器
- get_chat_model(node_id)：读 node_model_map → profile → 返回可调用对象
"""
from __future__ import annotations

import json
from typing import Protocol

import httpx
from sqlmodel import select

from .db import session
from .models import ModelProfile, NodeModelMap


class ChatModel(Protocol):
    def chat(self, system: str, user: str) -> str: ...


class OpenAICompatChatModel:
    def __init__(self, profile: ModelProfile):
        self.profile = profile

    def chat(self, system: str, user: str) -> str:
        url = self.profile.base_url.rstrip("/") + "/chat/completions"
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {self.profile.api_key}"},
            json={
                "model": self.profile.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": self.profile.temperature,
            },
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


class MockChatModel:
    """按 system prompt 里的 <!-- NODE:xxx --> 标记路由到 mock_llm_responses 中的生成器。"""

    def __init__(self):
        from . import mock_llm_responses
        self._routers = mock_llm_responses.ROUTERS

    def chat(self, system: str, user: str) -> str:
        for marker, fn in self._routers.items():
            if marker in system:
                return fn(system, user)
        raise ValueError("MockChatModel: 未识别的节点标记")


def get_profile_for_node(node_id: str) -> ModelProfile:
    with session() as s:
        m = s.get(NodeModelMap, node_id)
        if m is None:
            raise RuntimeError(f"节点 {node_id} 未绑定模型档案，请到模型设置页配置")
        p = s.get(ModelProfile, m.profile_id)
        if p is None:
            raise RuntimeError(f"节点 {node_id} 绑定的档案 {m.profile_id} 不存在")
        return p


def get_chat_model(node_id: str) -> ChatModel:
    p = get_profile_for_node(node_id)
    if p.provider == "mock":
        return MockChatModel()
    return OpenAICompatChatModel(p)


def test_profile_connection(profile: ModelProfile) -> dict:
    """设置页「测试连接」：发一条最小请求。"""
    try:
        if profile.provider == "mock":
            return {"ok": True, "detail": "mock 档案恒可用"}
        url = profile.base_url.rstrip("/") + "/chat/completions"
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {profile.api_key}"},
            json={
                "model": profile.model,
                "messages": [{"role": "user", "content": "ping，回复 pong"}],
                "max_tokens": 8,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return {"ok": True, "detail": resp.json()["choices"][0]["message"]["content"][:50]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": str(e)}


def extract_json(text: str):
    """从 LLM 输出提取 JSON（容错 markdown 代码块包裹）。"""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
        t = t.strip()
        if t.startswith("json"):
            t = t[4:].strip()
    start = min([i for i in (t.find("["), t.find("{")) if i != -1], default=-1)
    if start > 0:
        t = t[start:]
    return json.loads(t)
