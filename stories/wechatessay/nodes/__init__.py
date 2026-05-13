"""
微信公众号文章创作工作流 - 节点模块（v2 架构）

所有节点通过 create_deep_agent 创建，支持：
- 动态工具注册
- CompositeBackend 持久化
- Memory 三层机制
- Skill 加载
"""

from wechatessay.nodes.source_node import source_node, total_analysis_node
from wechatessay.nodes.collect_node import collect_node
from wechatessay.nodes.analyse_node import analyse_node
from wechatessay.nodes.plot_node import plot_node
from wechatessay.nodes.write_node import write_node
from wechatessay.nodes.composition_node import composition_node
from wechatessay.nodes.legality_node import legality_node
from wechatessay.nodes.publish_node import publish_node

__all__ = [
    "source_node",
    "total_analysis_node",
    "collect_node",
    "analyse_node",
    "plot_node",
    "write_node",
    "composition_node",
    "legality_node",
    "publish_node",
]
