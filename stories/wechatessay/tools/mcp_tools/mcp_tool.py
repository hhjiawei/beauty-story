"""
wechatessay.tools.mcp_tools.mcp_tool

MCP 连接封装层。
负责：
- 从 mcp_config.json 读取配置
- 连接各 MCP 服务器
- 将所有 MCP 工具转换为 LangChain 标准工具
- 管理连接生命周期
- 拼接为 total_tools 供 create_deep_agent 使用
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from wechatessay.config import MCP_CONFIG_PATH


class MCPToolManager:
    """
    MCP 工具管理器。

    使用单例模式避免重复连接。
    从 mcp_config.json 读取配置，支持环境变量替换。
    """

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
            cls._instance._tools = None
            cls._instance._config = None
        return cls._instance

    def _load_config(self) -> Dict[str, Any]:
        """
        加载 MCP 配置文件，支持环境变量替换。

        格式：${ENV_VAR} 会被替换为对应的环境变量值。
        """
        config_path = Path(MCP_CONFIG_PATH)
        if not config_path.exists():
            raise FileNotFoundError(f"MCP config not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            raw = f.read()

        # 环境变量替换 ${VAR_NAME}
        import re
        def _replace_env(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        raw = re.sub(r'\$\{([^}]+)\}', _replace_env, raw)
        self._config = json.loads(raw)
        return self._config

    def _build_client_config(self) -> Dict[str, Any]:
        """
        构建 MultiServerMCPClient 所需的配置字典。

        过滤掉 enabled=false 的服务器，提取必要字段。
        """
        config = self._load_config()
        client_config = {}

        for server_name, server_conf in config.get("mcpServers", {}).items():
            if not server_conf.get("enabled", True):
                continue

            entry = {
                "transport": server_conf.get("transport", "streamable_http"),
                "url": server_conf["url"],
            }
            # 可选 headers
            if "headers" in server_conf:
                entry["headers"] = server_conf["headers"]

            client_config[server_name] = entry

        return client_config

    async def _ensure_connected(self):
        """懒连接：只在第一次获取工具时建立连接。"""
        if self._client is not None:
            return

        client_config = self._build_client_config()
        if not client_config:
            self._tools = []
            return

        self._client = MultiServerMCPClient(client_config)

    async def get_tools(self) -> List[BaseTool]:
        """
        获取所有 MCP 工具（已转换为 LangChain 格式）。

        返回所有已启用 MCP 服务器的工具合集。
        """
        await self._ensure_connected()
        if self._tools is None:
            if self._client is None:
                self._tools = []
            else:
                self._tools = await self._client.get_tools()
        return self._tools or []

    def get_tools_sync(self) -> List[BaseTool]:
        """同步获取工具（供同步代码调用）。"""
        return asyncio.run(self.get_tools())

    async def get_tools_by_server(self, server_name: str) -> List[BaseTool]:
        """
        获取指定服务器的工具。

        注意：MultiServerMCPClient 返回的是合并后的工具列表，
        工具名称通常带有服务器前缀。
        """
        tools = await self.get_tools()
        prefix = f"{server_name}__"
        return [t for t in tools if t.name.startswith(prefix)]

    async def disconnect(self):
        """清理 MCP 连接。"""
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None
            self._tools = None

    @asynccontextmanager
    async def session(self):
        """上下文管理器：自动连接和断开。"""
        try:
            tools = await self.get_tools()
            yield tools
        finally:
            await self.disconnect()

    def get_config(self) -> Optional[Dict[str, Any]]:
        """获取原始配置（用于调试）。"""
        return self._config


# ── 全局实例（单例） ──
mcp_manager = MCPToolManager()


# ── 便捷函数 ──

async def get_total_tools(
    custom_tools: Optional[List[BaseTool]] = None,
) -> List[BaseTool]:
    """
    获取所有工具的合集：MCP 工具 + 自定义工具。

    这是给 create_deep_agent 传入 tools 参数的推荐方式。

    Args:
        custom_tools: 额外的自定义工具列表

    Returns:
        total_tools: MCP 工具 + 自定义工具 的合并列表
    """
    mcp_tools = await mcp_manager.get_tools()
    total_tools = list(mcp_tools)
    if custom_tools:
        total_tools.extend(custom_tools)
    return total_tools


def get_total_tools_sync(
    custom_tools: Optional[List[BaseTool]] = None,
) -> List[BaseTool]:
    """同步版本：获取所有工具的合集。"""
    return asyncio.run(get_total_tools(custom_tools))


async def reload_mcp_tools() -> List[BaseTool]:
    """重新加载 MCP 配置和工具（热更新用）。"""
    await mcp_manager.disconnect()
    mcp_manager._config = None
    return await mcp_manager.get_tools()
