"""deepagents 工厂单测：默认挂载播种、工作区技能副本、agent 调用链路、配置校验。

每个内容节点 = 一个 deepagents 实例（独立模型 + 独立 skills 目录 + 可选 MCP 工具），
这些测试用 mock 模型档案验证整条「配置 → 构建 → 调用」链路。
"""
import json

import pytest

from app import config, prompts
from app.agents import factory
from app.agents.node_registry import CONTENT_NODES, DEFAULT_SKILL_MOUNTS
from app.db import session
from app.models import McpServer, NodeAgentConfig


def test_default_configs_seeded(tmp_env):
    """tmp_env 播种后：六个内容节点都有 §5.1 默认挂载。"""
    for node in CONTENT_NODES:
        cfg = factory.get_node_agent_config(node)
        assert cfg["skills"] == DEFAULT_SKILL_MOUNTS[node], node
        assert cfg["mcp_ids"] == []


def test_workspace_skills_copied(tmp_env):
    """构建 agent 时，挂载技能被复制进该节点工作区（deepagents 渐进加载源）。"""
    system, _, _ = prompts.build_n1_event_card_mining(
        {"source_type": "person", "source_text": "x", "target_minutes": 10,
         "episode_no": 1, "prev_episode_bridge": None})
    factory.build_node_agent("n1_event_card_mining", system)
    ws = config.AGENT_WORKSPACE_DIR / "n1_event_card_mining" / "skills"
    assert (ws / "historical-event-cards" / "SKILL.md").exists()
    # 未挂载的技能不出现在工作区
    assert not (ws / "ammo-depot").exists()


def test_run_node_agent_mock_roundtrip(tmp_env):
    """mock 档案下，agent 经 deepagents 全栈跑通并按 NODE 标记路由出 JSON。"""
    state = {"source_type": "person", "source_text": "桀为虐政淫荒", "target_minutes": 10,
             "episode_no": 1, "prev_episode_bridge": None}
    system, user, _ = prompts.build_n1_event_card_mining(state)
    raw = factory.run_node_agent("n1_event_card_mining", system, user)
    cards = json.loads(raw)
    assert isinstance(cards, list) and cards[0]["卡号"] == "C-001"


def test_save_config_validation(tmp_env):
    """非法节点/不存在技能/不存在 MCP id 都要拦下。"""
    with pytest.raises(ValueError, match="非法节点"):
        factory.save_node_agent_config("n99_nope", [], [])
    with pytest.raises(ValueError, match="不存在于技能库"):
        factory.save_node_agent_config("n1_event_card_mining", ["no-such-skill"], [])
    with pytest.raises(ValueError, match="MCP 服务器"):
        factory.save_node_agent_config("n1_event_card_mining", ["ammo-depot"], [999])


def test_save_config_then_workspace_follows(tmp_env):
    """前端改挂载 → 下次构建工作区技能随之变化。"""
    factory.save_node_agent_config("n2_style_robe_selection",
                                   ["style-library", "ammo-depot"], [])
    system, _, _ = prompts.build_n2_style_robe_selection(
        {"source_type": "person", "source_text": "x", "target_minutes": 10,
         "episode_no": 1, "prev_episode_bridge": None,
         "event_cards": [], "style_card": {}},
        mounted_skills=factory.get_node_agent_config("n2_style_robe_selection")["skills"])
    factory.reset_agent_cache()
    factory.build_node_agent("n2_style_robe_selection", system)
    ws = config.AGENT_WORKSPACE_DIR / "n2_style_robe_selection" / "skills"
    assert (ws / "style-library").exists() and (ws / "ammo-depot").exists()
    assert not (ws / "persona-writer").exists()   # 已被前端摘掉


def test_mcp_binding_unknown_server_fails_clearly(tmp_env):
    """绑定了被删除的 MCP 服务器：构建时报带节点名的清晰错误（可重试）。"""
    with session() as s:
        srv = McpServer(name="dead", transport="http", url="http://127.0.0.1:1/mcp")
        s.add(srv); s.commit(); s.refresh(srv)
        sid = srv.id
        row = s.get(NodeAgentConfig, "n6_storyboard_translation")
        row.mcp_ids_json = json.dumps([sid])
        s.add(row); s.commit()
        s.delete(srv); s.commit()
    factory.reset_agent_cache()
    with pytest.raises(RuntimeError, match="MCP 服务器不存在"):
        factory.build_node_agent("n6_storyboard_translation", "sys")


def test_mcp_unreachable_fails_clearly(tmp_env):
    """MCP 服务器连不上：报带节点名与服务器名的错误（进 node_runs，可重试）。"""
    with session() as s:
        srv = McpServer(name="unreachable", transport="http",
                        url="http://127.0.0.1:1/mcp")
        s.add(srv); s.commit(); s.refresh(srv)
        sid = srv.id
        row = s.get(NodeAgentConfig, "n6_storyboard_translation")
        row.mcp_ids_json = json.dumps([sid])
        s.add(row); s.commit()
    factory.reset_agent_cache()
    with pytest.raises(RuntimeError, match=r"\[n6_storyboard_translation\].*unreachable"):
        factory.build_node_agent("n6_storyboard_translation", "sys")


def test_mcp_server_crud_and_config_roundtrip(tmp_env):
    with session() as s:
        srv = McpServer(name="fs", transport="stdio", command="npx",
                        args_json='["-y","@modelcontextprotocol/server-filesystem","/tmp"]')
        s.add(srv); s.commit(); s.refresh(srv)
        sid = srv.id
    cfg = factory.save_node_agent_config("n1_event_card_mining",
                                         ["historical-event-cards"], [sid])
    assert cfg["mcp_ids"] == [sid]
    assert cfg["is_default"] is False
