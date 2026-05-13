"""
MCP 连接封装层

负责：
- 连接 trendradar MCP 服务器
- 将 MCP 工具转换为 LangChain 标准工具
- 管理连接生命周期
"""

import asyncio
from contextlib import asynccontextmanager
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_core.tools import BaseTool


class MCPManager:
    """
    MCP 服务器管理器
    使用单例模式避免重复连接，支持 async with 上下文管理
    """

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
            cls._instance._tools = None
        return cls._instance

    async def _ensure_connected(self):
        """懒连接：只在第一次获取工具时建立连接"""
        if self._client is not None:
            return

        # 这里添加mcp服务
        self._client = MultiServerMCPClient({
            "trendradar": {
                "transport": "streamable_http",
                "url": "http://localhost:3333/mcp"
                # 如果需要认证，加 headers：
                # "headers": {"Authorization": "Bearer YOUR_TOKEN"}
            }
        })

    async def get_tools(self) -> list[BaseTool]:
        """获取 trendradar 的所有 MCP 工具（已转换为 LangChain 格式）"""
        await self._ensure_connected()
        if self._tools is None:
            self._tools = await self._client.get_tools()
        return self._tools

    def get_tools_sync(self) -> list[BaseTool]:
        """同步获取工具（供同步代码调用）"""
        return asyncio.run(self.get_tools())

    async def disconnect(self):
        """清理 MCP 连接"""
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None
            self._tools = None

    @asynccontextmanager
    async def session(self):
        """上下文管理器：自动连接和断开"""
        try:
            tools = await self.get_tools()
            yield tools
        finally:
            await self.disconnect()


# 全局实例（单例）
mcp_manager = MCPManager()


async def get_all_tools() -> list[BaseTool]:
    """
    获取所有可用工具（基础工具 + MCP 工具）

    Returns:
        合并后的工具列表
    """
    from wechatessay.tools.base_tools.base_tool import BASE_TOOLS

    all_tools = list(BASE_TOOLS)

    try:
        mcp_tools = await mcp_manager.get_tools()
        all_tools.extend(mcp_tools)
    except Exception as e:
        print(f"⚠️ MCP tools not available: {e}")

    return all_tools


def get_all_tools_sync() -> list[BaseTool]:
    """同步获取所有工具"""
    return asyncio.run(get_all_tools())
