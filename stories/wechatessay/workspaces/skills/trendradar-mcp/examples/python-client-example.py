#!/usr/bin/env python3
"""
TrendRadar MCP 客户端示例
演示如何使用 MCP 客户端与 TrendRadar MCP 服务器交互

前置要求:
1. 安装 MCP SDK: pip install mcp
2. 运行 TrendRadar MCP 服务器
"""

import asyncio
import json
from typing import List, Dict, Any
import sys

# 检查是否已安装 mcp
try:
    import mcp
    from mcp import ClientSession, StdioServerParameters
    from mcp.client import stdio
except ImportError:
    print("错误: 未安装 MCP SDK")
    print("安装命令: pip install mcp")
    sys.exit(1)


class TrendRadarClient:
    """TrendRadar MCP 客户端示例"""
    
    def __init__(self, transport: str = "stdio", server_url: str = None):
        """
        初始化客户端
        
        Args:
            transport: 传输模式，'stdio' 或 'http'
            server_url: HTTP 模式下的服务器 URL
        """
        self.transport = transport
        self.server_url = server_url
        self.session = None
        
    async def connect(self):
        """连接 MCP 服务器"""
        print(f"连接 TrendRadar MCP 服务器 ({self.transport} 模式)...")
        
        if self.transport == "stdio":
            # stdio 模式
            server_params = StdioServerParameters(
                command="trendradar-mcp",
                args=["--transport=stdio"]
            )
            self.session = await stdio.connect_with_params(server_params)
            
        elif self.transport == "http":
            # HTTP 模式
            # 注意: HTTP 模式需要额外配置，这里仅示例
            print("HTTP 模式需要额外配置，请参考 MCP SDK 文档")
            raise NotImplementedError("HTTP 模式示例暂未实现")
        
        else:
            raise ValueError(f"不支持的传输模式: {self.transport}")
        
        print("连接成功!")
        
    async def list_tools(self):
        """列出所有可用工具"""
        if not self.session:
            await self.connect()
        
        tools = await self.session.list_tools()
        print(f"可用工具 ({len(tools.tools)} 个):")
        for i, tool in enumerate(tools.tools, 1):
            print(f"  {i}. {tool.name}: {tool.description}")
        return tools.tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用 MCP 工具"""
        if not self.session:
            await self.connect()
        
        print(f"调用工具: {tool_name}")
        print(f"参数: {json.dumps(arguments, ensure_ascii=False, indent=2)}")
        
        try:
            result = await self.session.call_tool(tool_name, arguments=arguments)
            
            # 解析结果
            if result.content:
                for content in result.content:
                    if content.type == "text":
                        print(f"结果:\n{content.text[:500]}...")  # 只显示前500字符
                        return json.loads(content.text)
            
            print("无返回结果")
            return {}
            
        except Exception as e:
            print(f"工具调用失败: {e}")
            return {}
    
    async def disconnect(self):
        """断开连接"""
        if self.session:
            await self.session.close()
            print("连接已关闭")


# ==================== 示例函数 ====================

async def example_basic_queries(client: TrendRadarClient):
    """基础查询示例"""
    print("\n" + "="*60)
    print("1. 基础查询示例")
    print("="*60)
    
    # 1.1 获取最新新闻
    print("\n1.1 获取最新新闻 (前10条)")
    news = await client.call_tool("get_latest_news", {
        "limit": 10,
        "include_url": False  # 节省 token
    })
    
    # 1.2 解析日期范围
    print("\n1.2 解析自然语言日期")
    date_range = await client.call_tool("resolve_date_range", {
        "expression": "最近7天"
    })
    
    # 1.3 查询特定日期新闻
    print("\n1.3 查询昨天新闻")
    yesterday_news = await client.call_tool("get_news_by_date", {
        "date": "yesterday",
        "limit": 5
    })


async def example_trend_analysis(client: TrendRadarClient):
    """趋势分析示例"""
    print("\n" + "="*60)
    print("2. 趋势分析示例")
    print("="*60)
    
    # 2.1 获取热点话题
    print("\n2.1 自动提取热点话题 (前10)")
    topics = await client.call_tool("get_trending_topics", {
        "top_n": 10,
        "extract_mode": "auto_extract"
    })
    
    # 2.2 分析话题趋势
    print("\n2.2 分析'人工智能'趋势")
    trend = await client.call_tool("analyze_topic_trend", {
        "topic": "人工智能",
        "date_range": "最近7天"
    })
    
    # 2.3 情感分析
    print("\n2.3 今日新闻情感分析")
    sentiment = await client.call_tool("analyze_sentiment", {
        "date": "today",
        "limit": 20
    })


async def example_rss_queries(client: TrendRadarClient):
    """RSS 查询示例"""
    print("\n" + "="*60)
    print("3. RSS 查询示例")
    print("="*60)
    
    # 3.1 获取最新 RSS
    print("\n3.1 获取最新 RSS 内容")
    rss = await client.call_tool("get_latest_rss", {
        "feeds": ["hacker-news"],
        "limit": 5
    })
    
    # 3.2 搜索 RSS
    print("\n3.2 搜索 RSS 中的'AI'内容")
    search = await client.call_tool("search_rss", {
        "keyword": "AI",
        "days": 7,
        "limit": 5
    })


async def example_system_management(client: TrendRadarClient):
    """系统管理示例"""
    print("\n" + "="*60)
    print("4. 系统管理示例")
    print("="*60)
    
    # 4.1 系统状态
    print("\n4.1 获取系统状态")
    status = await client.call_tool("get_system_status", {})
    
    # 4.2 配置信息
    print("\n4.2 获取当前配置")
    config = await client.call_tool("get_current_config", {})
    
    # 4.3 可用日期
    print("\n4.3 列出可用日期")
    dates = await client.call_tool("list_available_dates", {
        "source": "local"
    })


async def example_advanced_workflows(client: TrendRadarClient):
    """高级工作流示例"""
    print("\n" + "="*60)
    print("5. 高级工作流示例")
    print("="*60)
    
    # 5.1 跨平台新闻聚合
    print("\n5.1 跨平台新闻聚合")
    aggregated = await client.call_tool("aggregate_news", {
        "date": "today",
        "limit": 10
    })
    
    # 5.2 时期对比
    print("\n5.2 周环比对比")
    comparison = await client.call_tool("compare_periods", {
        "period1": "this week",
        "period2": "last week",
        "mode": "overview"
    })
    
    # 5.3 生成摘要报告
    print("\n5.3 生成日报摘要")
    report = await client.call_tool("generate_summary_report", {
        "type": "daily",
        "date": "today"
    })


async def main():
    """主函数"""
    print("TrendRadar MCP 客户端示例")
    print("="*60)
    
    # 创建客户端
    client = TrendRadarClient(transport="stdio")
    
    try:
        # 连接服务器
        await client.connect()
        
        # 列出所有工具
        tools = await client.list_tools()
        print(f"共发现 {len(tools)} 个工具")
        
        # 运行示例
        await example_basic_queries(client)
        await example_trend_analysis(client)
        await example_rss_queries(client)
        await example_system_management(client)
        await example_advanced_workflows(client)
        
        print("\n" + "="*60)
        print("所有示例执行完成!")
        
    except Exception as e:
        print(f"执行出错: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # 断开连接
        await client.disconnect()


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())