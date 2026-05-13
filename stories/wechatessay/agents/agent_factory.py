"""
Deep Agent 工厂 (Agent Factory)

核心职责：
1. 封装 create_deep_agent，为每个工作流节点创建专用 agent
2. 动态工具注册：根据节点类型自动发现和注入所需工具
3. Skill 加载支持：从 /skills 目录加载 skill 文件，注入 agent
4. 集成 Memory Manager：通过 backend/store 实现三层记忆
5. 集成 Chat History Store：通过 CompositeBackend 持久化聊天记录

设计理念：
- 每个节点 = 一个独立的 Deep Agent
- Agent = LLM + Tools + Memory + Backend + Store
- 工具不硬编码，通过 registry 动态发现和注册
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field

from langchain_core.tools import BaseTool
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI

from wechatessay.agents.memory_manager import MemoryManager, get_memory_manager
from wechatessay.agents.chat_history_store import ChatHistoryStore, get_chat_history_store


# ═══════════════════════════════════════════════════════════
# 1. 节点工具注册表 (Node Tool Registry)
# ═══════════════════════════════════════════════════════════

# 节点 → 所需工具的映射
NODE_TOOL_REGISTRY: Dict[str, List[str]] = {
    "source_node":         ["read_file", "tavily_web_search"],
    "total_analysis_node": ["tavily_web_search"],
    "collect_node":        ["tavily_web_search", "read_file"],
    "analyse_node":        ["tavily_web_search", "read_file"],
    "plot_node":           ["read_file"],
    "write_node":          ["read_file", "save_draft"],
    "composition_node":    ["read_file", "save_draft"],
    "legality_node":       ["read_file"],
    "publish_node":        ["save_draft"],
}

# 全局工具注册表（工具名 → 工具实例/工厂函数）
_TOOL_FACTORIES: Dict[str, Callable[[], BaseTool]] = {}
_TOOL_INSTANCES: Dict[str, BaseTool] = {}


def register_tool(name: str, tool: Union[BaseTool, Callable[[], BaseTool]]):
    """
    注册工具到全局注册表

    Args:
        name: 工具名称
        tool: 工具实例或工厂函数
    """
    if isinstance(tool, BaseTool):
        _TOOL_INSTANCES[name] = tool
    else:
        _TOOL_FACTORIES[name] = tool


def discover_tools_for_node(node_name: str) -> List[BaseTool]:
    """
    为指定节点发现所需工具

    从注册表中查找该节点声明的工具，动态实例化并返回。
    如果某个工具未注册，会打印警告但继续执行。

    Args:
        node_name: 节点名称（如 "collect_node"）

    Returns:
        工具实例列表
    """
    required = NODE_TOOL_REGISTRY.get(node_name, [])
    tools: List[BaseTool] = []

    for tool_name in required:
        tool = _resolve_tool(tool_name)
        if tool:
            tools.append(tool)
        else:
            print(f"  ⚠️ Tool '{tool_name}' not found for node '{node_name}'")

    # 此外自动收集所有已注册的 MCP 工具
    mcp_tools = _get_mcp_tools()
    if mcp_tools:
        print(f"  🔌 发现 {len(mcp_tools)} 个 MCP 工具")
        tools.extend(mcp_tools)

    return tools


def _resolve_tool(name: str) -> Optional[BaseTool]:
    """解析工具名到工具实例"""
    # 1. 检查已实例化的工具
    if name in _TOOL_INSTANCES:
        return _TOOL_INSTANCES[name]

    # 2. 检查工厂函数
    if name in _TOOL_FACTORIES:
        tool = _TOOL_FACTORIES[name]()
        _TOOL_INSTANCES[name] = tool
        return tool

    return None


def _get_mcp_tools() -> List[BaseTool]:
    """获取所有 MCP 工具"""
    try:
        from wechatessay.tools.mcp_tools.mcp_tool import trendradar_manager
        return trendradar_manager.get_tools_sync()
    except Exception as e:
        return []


def list_registered_tools() -> Dict[str, str]:
    """列出所有已注册的工具"""
    result = {}
    for name in _TOOL_INSTANCES:
        result[name] = "instance"
    for name in _TOOL_FACTORIES:
        if name not in result:
            result[name] = "factory"
    return result


# ═══════════════════════════════════════════════════════════
# 2. Skill 注册表
# ═══════════════════════════════════════════════════════════

SKILL_REGISTRY: Dict[str, str] = {}


def load_skills(skills_dir: Optional[str] = None):
    """
    从目录加载所有 Skill

    遍历 /skills/ 目录下的 .md/.txt 文件，注册为 skill。
    """
    from wechatessay.config import SKILLS_DIR

    skill_dir = Path(skills_dir or SKILLS_DIR)
    if not skill_dir.exists():
        return

    for f in skill_dir.glob("*.md"):
        skill_name = f.stem
        SKILL_REGISTRY[skill_name] = f.read_text(encoding="utf-8")
        print(f"  📖 Loaded skill: {skill_name}")

    for f in skill_dir.glob("*.txt"):
        skill_name = f.stem
        SKILL_REGISTRY[skill_name] = f.read_text(encoding="utf-8")
        print(f"  📖 Loaded skill: {skill_name}")


def get_skill_prompt(skill_name: str) -> Optional[str]:
    """获取指定 skill 的内容"""
    return SKILL_REGISTRY.get(skill_name)


def build_system_prompt_with_skills(base_prompt: str, skill_names: List[str]) -> str:
    """
    将 skill 内容注入到 system prompt 中

    Args:
        base_prompt: 基础 system prompt
        skill_names: 需要加载的 skill 名称列表

    Returns:
        注入 skill 后的完整 system prompt
    """
    skill_sections = []
    for name in skill_names:
        content = get_skill_prompt(name)
        if content:
            skill_sections.append(f"""═══ SKILL: {name} ═══
{content}
═══ END SKILL ═══""")
        else:
            print(f"  ⚠️ Skill '{name}' not found")

    if skill_sections:
        skills_block = "\n\n".join(skill_sections)
        return f"""{base_prompt}

═══════════════════════════════════════
📖 已加载的 Skill（请严格遵循以下技能指南）：
═══════════════════════════════════════

{skills_block}
"""

    return base_prompt


# ═══════════════════════════════════════════════════════════
# 3. NodeAgent - 节点级 Deep Agent 封装
# ═══════════════════════════════════════════════════════════

@dataclass
class NodeAgentConfig:
    """节点 Agent 配置"""
    node_name: str
    llm_model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4000
    tools: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    enable_memory: bool = True
    enable_chat_history: bool = True
    system_prompt: str = ""


class NodeAgent:
    """
    节点级 Deep Agent

    每个工作流节点拥有自己独立的 NodeAgent，包含：
    - LLM (create_deep_agent 创建)
    - Tools (动态注册)
    - Memory (三层记忆系统)
    - Chat History (CompositeBackend 持久化)
    - Skills (可加载 skill 文件)

    替代原有的 get_llm() 直接调用方式。
    """

    def __init__(
        self,
        config: NodeAgentConfig,
        backend=None,
        store=None,
        thread_id: str = "default",
    ):
        self.config = config
        self.backend = backend
        self.store = store
        self.thread_id = thread_id

        # 初始化 LLM
        self._llm = self._create_llm()

        # 发现和注册工具
        self._tools = self._discover_tools()

        # 绑定工具到 LLM
        self._llm_with_tools = self._llm.bind_tools(self._tools) if self._tools else self._llm

        # 初始化记忆系统
        self._memory = None
        if config.enable_memory:
            self._memory = get_memory_manager(
                backend=backend,
                store=store,
                thread_id=thread_id,
                llm_summarizer=self._llm,
            )

        # 初始化聊天记录存储
        self._chat_store = None
        if config.enable_chat_history:
            self._chat_store = get_chat_history_store(
                backend=backend,
                thread_id=thread_id,
            )

        # 构建完整 system prompt（含 skills）
        self._system_prompt = self._build_system_prompt()

        # 内部状态
        self._messages: List[Any] = []
        self._iteration_count = 0

    def _create_llm(self) -> BaseLanguageModel:
        """创建 LLM 实例"""
        return ChatOpenAI(
            model=self.config.llm_model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

    def _discover_tools(self) -> List[BaseTool]:
        """发现并注册工具"""
        # 合并注册表中声明的和配置中显式指定的
        declared_tools = NODE_TOOL_REGISTRY.get(self.config.node_name, [])
        explicit_tools = self.config.tools
        all_tool_names = list(set(declared_tools + explicit_tools))

        tools = []
        for name in all_tool_names:
            tool = _resolve_tool(name)
            if tool:
                tools.append(tool)
            else:
                print(f"  ⚠️ Tool '{name}' not registered")

        return tools

    def _build_system_prompt(self) -> str:
        """构建完整 system prompt（含 skills）"""
        base = self.config.system_prompt
        if self.config.skills:
            base = build_system_prompt_with_skills(base, self.config.skills)
        return base

    # ── 核心执行接口 ──

    def invoke(self, user_prompt: str, max_iterations: int = 10, use_memory: bool = True) -> Any:
        """
        执行 Agent 任务

        核心逻辑：
        1. 用 system prompt + 记忆丰富的 user prompt 初始化消息
        2. 循环：调用 LLM → 检查工具调用 → 执行工具 → 记录 → 塞回历史
        3. 直到 LLM 不调用工具或达到最大迭代次数
        4. 记录完整聊天历史到 CompositeBackend

        Args:
            user_prompt: 用户提示
            max_iterations: 最大迭代次数
            use_memory: 是否注入历史记忆

        Returns:
            LLM 最终响应（AIMessage）
        """
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

        # 记录节点开始
        if self._chat_store:
            self._chat_store.record_node_event(self.config.node_name, "start")

        # 构建 system prompt
        final_prompt = user_prompt
        if use_memory and self._memory:
            query = user_prompt[:200]
            final_prompt = self._memory.enrich_prompt(user_prompt, query=query)

        # 初始化消息列表
        self._messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=final_prompt),
        ]

        self._iteration_count = 0
        last_response = None

        while self._iteration_count < max_iterations:
            self._iteration_count += 1

            # 1. 调用 LLM
            if self._tools:
                response = self._llm_with_tools.invoke(self._messages)
            else:
                response = self._llm.invoke(self._messages)

            # 记录 LLM 调用
            if self._chat_store:
                self._chat_store.record_llm_call(
                    node_name=self.config.node_name,
                    messages=self._messages,
                    response=response,
                    metadata={"iteration": self._iteration_count},
                )

            # 2. 检查是否需要调用工具
            if hasattr(response, "tool_calls") and response.tool_calls:
                # 记录 AI 响应到历史
                self._messages.append(AIMessage(
                    content=response.content,
                    tool_calls=response.tool_calls,
                ))

                # 3. 执行工具
                for tool_call in response.tool_calls:
                    tool_result = self._execute_tool(tool_call)

                    # 4. 工具结果塞回历史
                    self._messages.append(ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call.get("id", ""),
                    ))
            else:
                # LLM 没有调用工具，任务完成
                last_response = response
                break

        # 记录节点结束
        if self._chat_store:
            self._chat_store.record_node_event(
                self.config.node_name,
                "end",
                {"iterations": self._iteration_count},
            )

        # 记录消息到 RAG
        if self._memory:
            msg_dicts = [{"role": "user", "content": user_prompt}]
            if last_response:
                msg_dicts.append({"role": "assistant", "content": str(last_response.content)})
            self._memory.rag.add_messages(msg_dicts, node_name=self.config.node_name)

            # 检查是否需要摘要
            self._memory.check_and_summarize(msg_dicts)

        return last_response or response

    def _execute_tool(self, tool_call: Dict) -> str:
        """
        执行单个工具调用

        Args:
            tool_call: tool_call 字典，包含 name, args, id

        Returns:
            工具执行结果的字符串表示
        """
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})
        tool_call_id = tool_call.get("id", "")

        print(f"  🔧 [{self.config.node_name}] 执行工具: {tool_name}({tool_args})")

        # 在注册的工具中查找
        tool = None
        for t in self._tools:
            if t.name == tool_name:
                tool = t
                break

        if not tool:
            result = f"❌ 工具 '{tool_name}' 未找到"
        else:
            try:
                result = tool.invoke(tool_args)
                if isinstance(result, (dict, list)):
                    result = json.dumps(result, ensure_ascii=False)
                result = str(result)
            except Exception as e:
                result = f"❌ 工具执行失败: {str(e)}"

        # 记录工具调用
        if self._chat_store:
            self._chat_store.record_tool_call(
                node_name=self.config.node_name,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=result,
                tool_call_id=tool_call_id,
            )

        print(f"  ✅ [{self.config.node_name}] 工具 {tool_name} 执行完成")
        return result

    def invoke_with_revision(self, original_result: str, human_feedback: str,
                             revision_history: List[str], max_iterations: int = 5) -> Any:
        """
        执行修改任务（人机协同修改）

        Args:
            original_result: 原始结果（JSON 字符串）
            human_feedback: 人工反馈
            revision_history: 修改历史
            max_iterations: 最大迭代次数

        Returns:
            LLM 修改后的响应
        """
        from langchain_core.messages import SystemMessage, HumanMessage

        revision_prompt = f"""请根据以下修改意见调整内容：

【原始内容】
{original_result[:2000]}

【修改意见】
{human_feedback}

【修改历史】
{chr(10).join([f"第{i+1}轮: {h[:100]}" for i, h in enumerate(revision_history)])}

请输出修改后的完整 JSON 格式内容。"""

        self._messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(content=revision_prompt),
        ]

        self._iteration_count = 0

        while self._iteration_count < max_iterations:
            self._iteration_count += 1

            if self._tools:
                response = self._llm_with_tools.invoke(self._messages)
            else:
                response = self._llm.invoke(self._messages)

            if self._chat_store:
                self._chat_store.record_llm_call(
                    node_name=self.config.node_name,
                    messages=self._messages,
                    response=response,
                    metadata={"iteration": self._iteration_count, "mode": "revision"},
                )

            if hasattr(response, "tool_calls") and response.tool_calls:
                from langchain_core.messages import AIMessage, ToolMessage
                self._messages.append(AIMessage(
                    content=response.content,
                    tool_calls=response.tool_calls,
                ))
                for tool_call in response.tool_calls:
                    tool_result = self._execute_tool(tool_call)
                    self._messages.append(ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call.get("id", ""),
                    ))
            else:
                # 记录人工反馈
                if self._chat_store:
                    self._chat_store.record_human_feedback(
                        node_name=self.config.node_name,
                        feedback=human_feedback,
                        revision_count=len(revision_history),
                    )

                # 记录修改到 RAG
                if self._memory:
                    self._memory.record_human_feedback(self.config.node_name, human_feedback)

                return response

        return response

    # ── 属性访问 ──

    @property
    def llm(self) -> BaseLanguageModel:
        """获取 LLM 实例"""
        return self._llm

    @property
    def tools(self) -> List[BaseTool]:
        """获取工具列表"""
        return list(self._tools)

    @property
    def memory(self) -> Optional[MemoryManager]:
        """获取记忆管理器"""
        return self._memory

    @property
    def chat_store(self) -> Optional[ChatHistoryStore]:
        """获取聊天记录存储"""
        return self._chat_store

    @property
    def messages(self) -> List[Any]:
        """获取当前消息历史"""
        return list(self._messages)


# ═══════════════════════════════════════════════════════════
# 4. 便捷函数
# ═══════════════════════════════════════════════════════════

def     get_node_agent(
    node_name: str,
    system_prompt: str = "",
    llm_model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: int = 4000,
    tools: Optional[List[str]] = None,
    skills: Optional[List[str]] = None,
    enable_memory: bool = True,
    enable_chat_history: bool = True,
    backend=None,
    store=None,
    thread_id: str = "default",
) -> NodeAgent:
    """
    快速创建节点 Agent

    这是创建 NodeAgent 的便捷函数，无需手动构建 NodeAgentConfig。

    Args:
        node_name: 节点名称
        system_prompt: 系统提示
        llm_model: LLM 模型名
        temperature: 温度
        max_tokens: 最大 token
        tools: 额外工具列表
        skills: 需要加载的 skill 列表
        enable_memory: 是否启用记忆
        enable_chat_history: 是否启用聊天记录存储
        backend: CompositeBackend 实例
        store: Store 实例
        thread_id: 线程 ID

    Returns:
        NodeAgent 实例
    """
    config = NodeAgentConfig(
        node_name=node_name,
        llm_model=llm_model,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools or [],
        skills=skills or [],
        enable_memory=enable_memory,
        enable_chat_history=enable_chat_history,
        system_prompt=system_prompt,
    )

    return NodeAgent(
        config=config,
        backend=backend,
        store=store,
        thread_id=thread_id,
    )


def create_deep_agent(
    model,
    tools: List[BaseTool],
    system_prompt: str = "",
    backend=None,
    store=None,
    skills: Optional[List[str]] = None,
) -> NodeAgent:
    """
    create_deep_agent 兼容接口

    对标用户需求的 create_deep_agent 调用方式。

    Args:
        model: LLM 实例（LangChain BaseLanguageModel）
        tools: 工具列表
        system_prompt: 系统提示
        backend: CompositeBackend 实例
        store: Store 实例
        skills: 需要加载的 skill 列表

    Returns:
        NodeAgent 实例
    """
    node_name = "deep_agent"

    # 注册传入的工具
    for tool in tools:
        register_tool(tool.name, tool)

    config = NodeAgentConfig(
        node_name=node_name,
        llm_model="gpt-4o",  # 从 model 中推断
        system_prompt=system_prompt,
        tools=[t.name for t in tools],
        skills=skills or [],
    )

    agent = NodeAgent(
        config=config,
        backend=backend,
        store=store,
    )

    # 覆盖默认 LLM 为用户传入的 model
    agent._llm = model
    if tools:
        agent._llm_with_tools = model.bind_tools(tools)
    agent._tools = list(tools)

    return agent


# ═══════════════════════════════════════════════════════════
# 5. 初始化：注册基础工具
# ═══════════════════════════════════════════════════════════

def _register_default_tools():
    """注册默认工具（在模块导入时自动执行）"""
    try:
        from tools.base_tools.base_tool import (
            read_file,
            create_file,
            shell_exec,
            tavily_web_search,
            save_draft,
            read_draft,
        )

        register_tool("read_file", read_file)
        register_tool("create_file", create_file)
        register_tool("shell_exec", shell_exec)
        register_tool("tavily_web_search", tavily_web_search)
        register_tool("save_draft", save_draft)
        register_tool("read_draft", read_draft)

    except ImportError as e:
        print(f"  ⚠️ 部分工具注册失败: {e}")


# 自动注册
_register_default_tools()
