"""deepagents 实例工厂（执行方案 §3/§4/§5.1 的落地）。

每个内容节点 = 一个 deepagents 实例：
- 独立模型配置（node_model_map → 模型档案 → LangChain BaseChatModel）
- 独立 skills 目录（按节点挂载清单复制进该节点工作区，deepagents 渐进加载）
- 可挂载 MCP 服务器工具（langchain-mcp-adapters → tools=）
- 由外层 LangGraph 主图编排（产出节点 → 人工闸门），本模块只管「造 agent、跑 agent」

前端可在设置页逐节点调整 skills / MCP 挂载（node_agent_configs 表），
未配置时按 §5.1 默认挂载表播种。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from sqlmodel import select

from .. import config
from ..db import session
from ..llm import get_profile_for_node
from ..models import McpServer, NodeAgentConfig
from ..skills_loader import skill_exists
from .lc_models import _content_text, chat_model_for_profile
from .node_registry import CONTENT_NODES, DEFAULT_SKILL_MOUNTS

__all__ = ["CONTENT_NODES", "DEFAULT_SKILL_MOUNTS"]

# agent 缓存：(node_id, system哈希, 技能指纹, MCP指纹) → compiled agent
_AGENT_CACHE: dict[tuple, object] = {}
_MCP_CLIENTS: list = []          # 持有 MCP client 防 GC（tools 依赖其会话管理）


# ---------------------------------------------------------------- 节点配置（DB）

def ensure_default_node_configs() -> None:
    """按 §5.1 挂载表为未配置的节点播种默认 skills。幂等。"""
    with session() as s:
        for node_id, skills in DEFAULT_SKILL_MOUNTS.items():
            if s.get(NodeAgentConfig, node_id) is None:
                s.add(NodeAgentConfig(node_id=node_id,
                                      skills_json=json.dumps(skills, ensure_ascii=False)))
        s.commit()


def get_node_agent_config(node_id: str) -> dict:
    """读节点挂载配置；库里没有就回退 §5.1 默认表。"""
    with session() as s:
        row = s.get(NodeAgentConfig, node_id)
        if row is None:
            return {"node_id": node_id,
                    "skills": list(DEFAULT_SKILL_MOUNTS.get(node_id, [])),
                    "mcp_ids": [], "is_default": True}
        skills = json.loads(row.skills_json or "[]")
        mcp_ids = json.loads(row.mcp_ids_json or "[]")
        return {"node_id": node_id, "skills": skills, "mcp_ids": mcp_ids,
                # 内容与 §5.1 默认表一致即视为「默认挂载」（前端展示用）
                "is_default": skills == DEFAULT_SKILL_MOUNTS.get(node_id, []) and not mcp_ids,
                "updated_at": row.updated_at.isoformat()}


def save_node_agent_config(node_id: str, skills: list[str], mcp_ids: list[int]) -> dict:
    """前端保存挂载配置。校验：节点合法、技能存在、MCP 服务器存在。"""
    if node_id not in CONTENT_NODES:
        raise ValueError(f"非法节点 id: {node_id}（内容节点：{CONTENT_NODES}）")
    for name in skills:
        if not skill_exists(name):
            raise ValueError(f"技能「{name}」不存在于技能库 {config.SKILLS_DIR}")
    with session() as s:
        for mid in mcp_ids:
            if s.get(McpServer, int(mid)) is None:
                raise ValueError(f"MCP 服务器 id={mid} 不存在")
        row = s.get(NodeAgentConfig, node_id)
        if row is None:
            row = NodeAgentConfig(node_id=node_id)
        row.skills_json = json.dumps(list(skills), ensure_ascii=False)
        row.mcp_ids_json = json.dumps([int(x) for x in mcp_ids])
        row.updated_at = datetime.now(UTC)
        s.add(row)
        s.commit()
    return get_node_agent_config(node_id)


# ---------------------------------------------------------------- MCP 工具装载

def mcp_server_to_client_config(srv: McpServer) -> dict:
    """McpServer 行 → langchain-mcp-adapters 连接配置。"""
    if srv.transport in ("http", "sse", "websocket"):
        cfg: dict = {"transport": srv.transport, "url": srv.url}
        headers = json.loads(srv.headers_json or "{}")
        if headers:
            cfg["headers"] = headers
        return cfg
    if srv.transport == "stdio":
        cfg = {"transport": "stdio", "command": srv.command,
               "args": json.loads(srv.args_json or "[]")}
        env = json.loads(srv.env_json or "{}")
        if env:
            cfg["env"] = env
        return cfg
    raise ValueError(f"不支持的 MCP transport: {srv.transport}")


async def _fetch_mcp_tools(servers: list[McpServer]):
    from langchain_mcp_adapters.client import MultiServerMCPClient

    conf = {f"mcp{srv.id}_{srv.name}": mcp_server_to_client_config(srv) for srv in servers}
    client = MultiServerMCPClient(conf)
    tools = await client.get_tools()
    return client, tools


def _load_mcp_tools(node_id: str, mcp_ids: list[int]):
    """同步包装：装载节点绑定的全部 MCP 服务器工具。失败即节点错误（可重试）。"""
    if not mcp_ids:
        return []
    with session() as s:
        servers = [s.get(McpServer, int(mid)) for mid in mcp_ids]
    missing = [mid for mid, srv in zip(mcp_ids, servers) if srv is None]
    if missing:
        raise RuntimeError(f"[{node_id}] 绑定的 MCP 服务器不存在: {missing}")
    servers = [srv for srv in servers if srv.enabled]
    if not servers:
        return []
    try:
        client, tools = asyncio.run(_fetch_mcp_tools(servers))
    except Exception as e:  # noqa: BLE001
        names = [srv.name for srv in servers]
        raise RuntimeError(f"[{node_id}] MCP 服务器 {names} 连接/取工具失败: {e}") from e
    _MCP_CLIENTS.append(client)     # 保持引用，避免会话被回收
    return tools


def test_mcp_server(server_id: int) -> dict:
    """设置页「测试连接」：列出服务器暴露的工具名。"""
    with session() as s:
        srv = s.get(McpServer, server_id)
    if srv is None:
        return {"ok": False, "detail": "服务器不存在"}
    try:
        client, tools = asyncio.run(_fetch_mcp_tools([srv]))
        _MCP_CLIENTS.append(client)
        return {"ok": True, "detail": f"连通，暴露 {len(tools)} 个工具",
                "tools": [t.name for t in tools]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": str(e)}


# ---------------------------------------------------------------- agent 构建与调用

def _prepare_workspace(node_id: str, skills: list[str]) -> Path:
    """节点工作区：把挂载的技能复制到 workspace/skills/ 下（deepagents 渐进加载源）。

    用复制而非软链：/mnt 挂载不支持软链；且每节点一份副本，互不污染。
    """
    ws = config.AGENT_WORKSPACE_DIR / node_id
    skills_dir = ws / "skills"
    if skills_dir.exists():
        shutil.rmtree(skills_dir)
    skills_dir.mkdir(parents=True, exist_ok=True)
    for name in skills:
        src = config.SKILLS_DIR / name
        if not (src / "SKILL.md").exists():
            raise RuntimeError(
                f"[{node_id}] 挂载的技能「{name}」不存在于技能库（{config.SKILLS_DIR}），"
                "请到设置页调整该节点的技能挂载")
        shutil.copytree(src, skills_dir / name)
    return ws


def _skills_fingerprint(skills: list[str]) -> str:
    """技能内容指纹（name+mtime），技能文件被编辑后自动使缓存失效。"""
    parts = []
    for name in skills:
        p = config.SKILLS_DIR / name / "SKILL.md"
        parts.append(f"{name}:{p.stat().st_mtime_ns if p.exists() else 'x'}")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def _config_stamp(node_id: str) -> str:
    """节点配置 + MCP 服务器表的更新时间戳（前端改配置后缓存自动失效）。"""
    with session() as s:
        row = s.get(NodeAgentConfig, node_id)
        stamps = [row.updated_at.isoformat() if row else "default"]
        stamps += [srv.updated_at.isoformat()
                   for srv in s.exec(select(McpServer)).all()]
    return "|".join(sorted(stamps))


def build_node_agent(node_id: str, system_prompt: str):
    """按节点当前配置构建一个 deepagents 实例（带缓存）。"""
    cfg = get_node_agent_config(node_id)
    skills, mcp_ids = cfg["skills"], cfg["mcp_ids"]
    key = (node_id, hashlib.sha1(system_prompt.encode()).hexdigest()[:12],
           _skills_fingerprint(skills), tuple(mcp_ids), _config_stamp(node_id))
    if key in _AGENT_CACHE:
        return _AGENT_CACHE[key]

    profile = get_profile_for_node(node_id)
    ws = _prepare_workspace(node_id, skills)
    tools = _load_mcp_tools(node_id, mcp_ids)
    agent = create_deep_agent(
        model=chat_model_for_profile(profile),
        system_prompt=system_prompt,
        tools=tools,
        backend=FilesystemBackend(root_dir=str(ws), virtual_mode=True),
        skills=["/skills/"] if skills else None,
        name=f"hvp_{node_id}",
    )
    _AGENT_CACHE[key] = agent
    return agent


def run_node_agent(node_id: str, system: str, user: str) -> str:
    """跑一次节点 agent，返回最终 AI 消息文本（供 extract_json 解析）。

    每次调用都是全新会话（无 checkpointer）：节点上下文由 prompts.py 显式组装，
    agent 内部的多轮（读技能文件/调 MCP 工具）只在本次任务内存活。
    """
    import uuid

    from ..logging_setup import get_logger

    agent = build_node_agent(node_id, system)
    # 必须显式给一个全新的独立 config：
    # 节点函数运行在外层流水线图的上下文里，若不切斷，内层 agent 会继承外层的
    # thread_id，resume/重试时 LangGraph 会把首次执行的结果「确定性重放」回来，
    # 模型根本不会被重新调用（已用最小复现验证）。
    fresh_cfg = {"configurable": {"thread_id": f"{node_id}-{uuid.uuid4().hex}"}}
    # 必须用 ainvoke：MCP 工具全是异步 StructuredTool（只有 coroutine），
    # 同步 invoke 会在模型调用 MCP 工具时抛
    # "StructuredTool does not support sync invocation"。
    result = asyncio.run(agent.ainvoke(
        {"messages": [{"role": "user", "content": user}]},
        config=fresh_cfg,
    ))
    messages = result.get("messages") or []
    if not messages:
        raise RuntimeError(f"[{node_id}] agent 未返回任何消息")
    text = _content_text(messages[-1].content)
    get_logger().info("%s agent 完成，消息数=%d，终稿 %d 字", node_id, len(messages), len(text))
    return text


def reset_agent_cache() -> None:
    """测试/配置大改用：清空 agent 缓存与 MCP client 引用。"""
    _AGENT_CACHE.clear()
    _MCP_CLIENTS.clear()
