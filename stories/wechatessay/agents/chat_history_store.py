"""
聊天记录持久化存储 (Chat History Store)

基于 CompositeBackend 的 records 功能，将每个节点的聊天记录
（LLM 输入输出、工具调用结果等）持久化到文件系统。

实现方式：
- 通过 CompositeBackend 的虚拟文件系统接口读写记录
- 每条记录以 JSON 格式存储，key 为 thread_id + node_name + timestamp
- 支持追加写入和按 thread_id 检索

LangGraph Store 参考:
https://docs.langchain.com/oss/python/deepagents/backends#storebackend-langgraph-store
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)


class RecordType(Enum):
    """记录类型"""
    LLM_CALL = "llm_call"           # LLM 调用（输入 + 输出）
    TOOL_CALL = "tool_call"         # 工具调用
    TOOL_RESULT = "tool_result"     # 工具执行结果
    HUMAN_FEEDBACK = "human_feedback"  # 人工反馈
    NODE_START = "node_start"       # 节点开始
    NODE_END = "node_end"           # 节点结束


class ChatRecord:
    """单条聊天记录"""

    def __init__(
        self,
        record_type: RecordType,
        node_name: str,
        thread_id: str,
        content: Dict[str, Any],
        timestamp: Optional[float] = None,
    ):
        self.record_type = record_type
        self.node_name = node_name
        self.thread_id = thread_id
        self.content = content
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> Dict:
        return {
            "record_type": self.record_type.value,
            "node_name": self.node_name,
            "thread_id": self.thread_id,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "content": self.content,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ChatRecord":
        return cls(
            record_type=RecordType(data.get("record_type", "llm_call")),
            node_name=data.get("node_name", ""),
            thread_id=data.get("thread_id", ""),
            content=data.get("content", {}),
            timestamp=data.get("timestamp"),
        )


class ChatHistoryStore:
    """
    聊天记录存储器

    基于 CompositeBackend 的文件系统接口实现持久化存储。
    存储路径: /workspaces/records/{thread_id}/{node_name}/{timestamp}.json
    """

    RECORDS_DIR = "records"

    def __init__(self, backend=None, thread_id: str = "default"):
        """
        Args:
            backend: CompositeBackend 实例，如果为 None 则使用本地文件系统
            thread_id: 当前线程/会话 ID
        """
        self._backend = backend
        self._thread_id = thread_id
        self._memory_records: List[ChatRecord] = []

    def set_thread_id(self, thread_id: str):
        """切换当前线程 ID"""
        self._thread_id = thread_id

    def set_backend(self, backend):
        """设置/切换后端"""
        self._backend = backend

    def _make_key(self, node_name: str, record_type: str) -> str:
        """
        生成记录的存储 key
        key 格式: records/{thread_id}/{node_name}/{timestamp}_{type}.json
        """
        ts = str(int(time.time() * 1000))
        return f"{self.RECORDS_DIR}/{self._thread_id}/{node_name}/{ts}_{record_type}.json"

    def _write_to_backend(self, key: str, data: Dict) -> bool:
        """
        通过 CompositeBackend 写入数据
        """
        try:
            if self._backend is not None:
                # 使用 backend 的虚拟文件系统写入
                content = json.dumps(data, ensure_ascii=False, indent=2)
                self._backend.write_file(key, content)
                return True
        except Exception as e:
            print(f"  ⚠️ Backend write failed: {e}, falling back to local FS")

        # Fallback: 本地文件系统
        try:
            from config import WORKSPACE_DIR
            local_path = Path(WORKSPACE_DIR) / key
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"  ❌ Local write also failed: {e}")
            return False

    def _read_from_backend(self, key: str) -> Optional[Dict]:
        """通过 CompositeBackend 读取数据"""
        try:
            if self._backend is not None:
                content = self._backend.read_file(key)
                return json.loads(content)
        except Exception:
            pass

        # Fallback
        try:
            from config import WORKSPACE_DIR
            local_path = Path(WORKSPACE_DIR) / key
            if local_path.exists():
                with open(local_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass

        return None

    def _list_keys(self, prefix: str) -> List[str]:
        """列出指定前缀下的所有 key"""
        keys = []
        try:
            if self._backend is not None:
                # 尝试使用 backend 的 list 功能
                keys = self._backend.list_files(prefix)
        except Exception:
            pass

        if not keys:
            # Fallback: 本地遍历
            try:
                from config import WORKSPACE_DIR
                local_dir = Path(WORKSPACE_DIR) / prefix
                if local_dir.exists():
                    for f in local_dir.rglob("*.json"):
                        rel = f.relative_to(Path(WORKSPACE_DIR))
                        keys.append(str(rel).replace("\\", "/"))
            except Exception:
                pass

        return keys

    # ── 公开 API ──

    def record_llm_call(
        self,
        node_name: str,
        messages: List[BaseMessage],
        response: BaseMessage,
        metadata: Optional[Dict] = None,
    ):
        """记录 LLM 调用（输入消息 + 输出响应）"""
        msg_dicts = []
        for m in messages:
            d = {"type": m.__class__.__name__, "content": str(m.content)}
            if hasattr(m, "tool_calls") and m.tool_calls:
                d["tool_calls"] = m.tool_calls
            if hasattr(m, "tool_call_id") and m.tool_call_id:
                d["tool_call_id"] = m.tool_call_id
            msg_dicts.append(d)

        resp_dict = {
            "type": response.__class__.__name__,
            "content": str(response.content),
        }
        if hasattr(response, "tool_calls") and response.tool_calls:
            resp_dict["tool_calls"] = response.tool_calls

        content = {
            "input_messages": msg_dicts,
            "response": resp_dict,
            "metadata": metadata or {},
        }

        record = ChatRecord(
            record_type=RecordType.LLM_CALL,
            node_name=node_name,
            thread_id=self._thread_id,
            content=content,
        )
        self._memory_records.append(record)
        self._write_to_backend(self._make_key(node_name, "llm"), record.to_dict())

    def record_tool_call(
        self,
        node_name: str,
        tool_name: str,
        tool_args: Dict,
        tool_result: str,
        tool_call_id: Optional[str] = None,
    ):
        """记录工具调用"""
        content = {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "tool_result": tool_result[:2000] if len(str(tool_result)) > 2000 else tool_result,
            "tool_call_id": tool_call_id,
        }

        record = ChatRecord(
            record_type=RecordType.TOOL_CALL,
            node_name=node_name,
            thread_id=self._thread_id,
            content=content,
        )
        self._memory_records.append(record)
        self._write_to_backend(self._make_key(node_name, f"tool_{tool_name}"), record.to_dict())

    def record_human_feedback(self, node_name: str, feedback: str, revision_count: int = 0):
        """记录人工反馈"""
        content = {
            "feedback": feedback,
            "revision_count": revision_count,
        }

        record = ChatRecord(
            record_type=RecordType.HUMAN_FEEDBACK,
            node_name=node_name,
            thread_id=self._thread_id,
            content=content,
        )
        self._memory_records.append(record)
        self._write_to_backend(self._make_key(node_name, "feedback"), record.to_dict())

    def record_node_event(self, node_name: str, event: str, details: Optional[Dict] = None):
        """记录节点生命周期事件 (start/end)"""
        record_type = RecordType.NODE_START if event == "start" else RecordType.NODE_END
        content = {
            "event": event,
            "details": details or {},
        }

        record = ChatRecord(
            record_type=record_type,
            node_name=node_name,
            thread_id=self._thread_id,
            content=content,
        )
        self._memory_records.append(record)
        self._write_to_backend(self._make_key(node_name, event), record.to_dict())

    def get_thread_history(self, thread_id: Optional[str] = None) -> List[ChatRecord]:
        """获取指定线程的完整记录历史"""
        tid = thread_id or self._thread_id
        prefix = f"{self.RECORDS_DIR}/{tid}"
        keys = self._list_keys(prefix)

        records = []
        for key in sorted(keys):
            data = self._read_from_backend(key)
            if data:
                records.append(ChatRecord.from_dict(data))

        records.sort(key=lambda r: r.timestamp)
        return records

    def get_node_history(
        self,
        node_name: str,
        thread_id: Optional[str] = None,
    ) -> List[ChatRecord]:
        """获取指定节点在指定线程中的记录"""
        tid = thread_id or self._thread_id
        prefix = f"{self.RECORDS_DIR}/{tid}/{node_name}"
        keys = self._list_keys(prefix)

        records = []
        for key in sorted(keys):
            data = self._read_from_backend(key)
            if data:
                records.append(ChatRecord.from_dict(data))

        records.sort(key=lambda r: r.timestamp)
        return records

    def get_memory_records(self) -> List[ChatRecord]:
        """获取当前内存中的记录（当前节点运行期间）"""
        return list(self._memory_records)

    def clear_memory_records(self):
        """清空内存记录"""
        self._memory_records.clear()


# ── 全局单例 ──

_chat_history_store: Optional[ChatHistoryStore] = None


def get_chat_history_store(backend=None, thread_id: str = "default") -> ChatHistoryStore:
    """获取 ChatHistoryStore 单例"""
    global _chat_history_store
    if _chat_history_store is None:
        _chat_history_store = ChatHistoryStore(backend=backend, thread_id=thread_id)
    elif backend is not None:
        _chat_history_store.set_backend(backend)
    if thread_id != "default":
        _chat_history_store.set_thread_id(thread_id)
    return _chat_history_store
