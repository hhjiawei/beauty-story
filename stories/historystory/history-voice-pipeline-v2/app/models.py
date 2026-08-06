"""SQLModel 表结构（执行方案第九节）。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class Project(SQLModel, table=True):
    __tablename__ = "projects"
    id: str = Field(primary_key=True)
    title: str
    source_type: str                       # dynasty | person | event
    source_text: str
    target_minutes: int = 10
    episode_no: int = 1
    prev_episode_bridge: Optional[str] = None
    status: str = "created"                # created | running | done | archived
    created_at: datetime = Field(default_factory=_now)


class Run(SQLModel, table=True):
    __tablename__ = "runs"
    id: str = Field(primary_key=True)
    project_id: str = Field(index=True)
    thread_id: str                         # LangGraph checkpoint thread
    current_node: str = "n1_event_card_mining"
    status: str = "running"                # running | waiting_review | done | archived | error
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class NodeRun(SQLModel, table=True):
    __tablename__ = "node_runs"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    node_id: str
    model_profile_id: Optional[int] = None
    started_at: datetime = Field(default_factory=_now)
    finished_at: Optional[datetime] = None
    status: str = "running"                # running | ok | error
    token_usage: Optional[str] = None
    error: Optional[str] = None


class Artifact(SQLModel, table=True):
    __tablename__ = "artifacts"
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    node_id: str
    kind: str                              # event_cards|style_candidates|style_card|outline|theme_card|script|audit_report|storyboard|audio_unit|final_audio|subtitle
    version: int
    origin: str = "ai"                     # ai | human_edit | rework
    file_path: str
    created_at: datetime = Field(default_factory=_now)


class Review(SQLModel, table=True):
    __tablename__ = "reviews"
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: int
    run_id: str = Field(index=True)
    node_id: str
    action: str                            # approve | reject | regen_units
    feedback: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class ModelProfile(SQLModel, table=True):
    __tablename__ = "model_profiles"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.7
    provider: str = "openai"               # openai | mock（mock 供演示与测试）
    note: str = ""


class NodeModelMap(SQLModel, table=True):
    __tablename__ = "node_model_map"
    node_id: str = Field(primary_key=True)
    profile_id: int


class McpServer(SQLModel, table=True):
    """MCP 服务器登记表：节点 agent 可挂载其工具（deepagents tools=）。"""
    __tablename__ = "mcp_servers"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    transport: str = "http"                # http | sse | stdio | websocket
    url: str = ""                          # http/sse/websocket 用
    command: str = ""                      # stdio 用
    args_json: str = "[]"                  # stdio 参数
    env_json: str = "{}"                   # stdio 环境变量
    headers_json: str = "{}"               # http/sse 请求头（鉴权等）
    enabled: bool = True
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class NodeAgentConfig(SQLModel, table=True):
    """节点 Agent 配置：每个内容节点挂载哪些 skills / MCP 服务器。

    默认按执行方案 §5.1 节点技能挂载表播种，前端可逐节点调整。
    """
    __tablename__ = "node_agent_configs"
    node_id: str = Field(primary_key=True)
    skills_json: str = "[]"                # 技能名列表（按挂载顺序）
    mcp_ids_json: str = "[]"               # McpServer.id 列表
    updated_at: datetime = Field(default_factory=_now)


class VoiceRef(SQLModel, table=True):
    __tablename__ = "voice_refs"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    kind: str = "narrator"                 # narrator | emotion
    emotion_tag: str = ""
    file_path: str
    is_active: bool = False
    created_at: datetime = Field(default_factory=_now)


class PronunciationEntry(SQLModel, table=True):
    __tablename__ = "pronunciation_dict"
    word: str = Field(primary_key=True)
    pinyin: str
    source_run_id: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
