"""
三层记忆管理器 (Memory Manager)

Memory 机制 = 上下文管理 (Context) + 向量检索 (RAG) + 自动摘要 (Summarization)

设计目标：
- ContextMemory: 管理当前会话的短期上下文，确保 LLM 看到完整的对话历史
- RAGMemory: 基于向量检索的长期记忆，从历史对话中召回相关信息
- SummarizationMemory: 自动摘要机制，将冗长的历史对话压缩为精炼的上下文

存储方式：
- 所有记忆通过 create_deep_agent 的 backend 和 store 进行持久化
- 向量数据存储在 backend 的 /memories/vector/ 目录
- 摘要数据存储在 backend 的 /memories/summary/ 目录
- 上下文数据存储在 backend 的 /memories/context/ 目录

参考: https://docs.langchain.com/oss/python/deepagents/backends#storebackend-langgraph-store
"""

import json
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable


# ── 1. 上下文记忆 (Context Memory) ──

class ContextMemory:
    """
    短期上下文记忆

    维护当前工作流的完整上下文窗口，包括：
    - 各节点的输入/输出状态
    - 人工反馈历史
    - 当前会话的完整消息记录

    作用：让 AI 每次对话都能“看到”完整的上下文，不会“失忆”。
    """

    def __init__(self, backend=None, thread_id: str = "default"):
        self._backend = backend
        self._thread_id = thread_id
        self._context: Dict[str, Any] = {}
        self._message_buffer: List[Dict] = []

    # ── 状态上下文 ──

    def set_context(self, key: str, value: Any):
        """设置上下文键值"""
        self._context[key] = {
            "value": value,
            "timestamp": time.time(),
        }
        self._persist_context()

    def get_context(self, key: str, default=None) -> Any:
        """获取上下文值"""
        if key in self._context:
            return self._context[key]["value"]
        # 尝试从 backend 加载
        loaded = self._load_context_key(key)
        if loaded is not None:
            self._context[key] = loaded
            return loaded["value"]
        return default

    def get_all_context(self) -> Dict[str, Any]:
        """获取完整上下文（返回纯值字典）"""
        self._refresh_context()
        return {k: v["value"] for k, v in self._context.items()}

    def remove_context(self, key: str):
        """移除上下文键"""
        self._context.pop(key, None)
        self._persist_context()

    def clear_context(self):
        """清空上下文"""
        self._context.clear()
        self._persist_context()

    # ── 消息缓冲区 ──

    def append_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """追加消息到缓冲区"""
        self._message_buffer.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        })

    def get_messages(self, limit: Optional[int] = None) -> List[Dict]:
        """获取消息历史"""
        msgs = list(self._message_buffer)
        if limit and len(msgs) > limit:
            msgs = msgs[-limit:]
        return msgs

    def get_messages_as_text(self, limit: Optional[int] = None) -> str:
        """将消息格式化为文本（用于 prompt 注入）"""
        msgs = self.get_messages(limit)
        lines = []
        for m in msgs:
            role_emoji = {"user": "👤", "assistant": "🤖", "system": "⚙️", "tool": "🔧"}.get(m["role"], "📝")
            lines.append(f"{role_emoji} [{m['role']}] {m['content'][:300]}")
        return "\n\n".join(lines)

    def clear_messages(self):
        """清空消息缓冲区"""
        self._message_buffer.clear()

    # ── 持久化 ──

    def _persist_context(self):
        """持久化上下文到 backend"""
        key = f"context/{self._thread_id}/state.json"
        data = {
            "thread_id": self._thread_id,
            "context": self._context,
            "message_count": len(self._message_buffer),
            "updated_at": time.time(),
        }
        self._write(key, data)

    def _load_context_key(self, key: str) -> Optional[Dict]:
        """从 backend 加载单个上下文键"""
        # 先加载完整上下文
        full_key = f"context/{self._thread_id}/state.json"
        data = self._read(full_key)
        if data and "context" in data and key in data["context"]:
            return data["context"][key]
        return None

    def _refresh_context(self):
        """从 backend 刷新完整上下文"""
        key = f"context/{self._thread_id}/state.json"
        data = self._read(key)
        if data and "context" in data:
            self._context = data["context"]

    # ── Backend I/O ──

    def _write(self, key: str, data: Dict):
        """写入 backend"""
        try:
            if self._backend is not None:
                self._backend.write_file(key, json.dumps(data, ensure_ascii=False, indent=2))
                return
        except Exception as e:
            print(f"  ⚠️ Context backend write failed: {e}")
        # Fallback
        self._write_local(key, data)

    def _read(self, key: str) -> Optional[Dict]:
        """读取 backend"""
        try:
            if self._backend is not None:
                content = self._backend.read_file(key)
                return json.loads(content)
        except Exception:
            pass
        return self._read_local(key)

    def _write_local(self, key: str, data: Dict):
        """本地文件系统 fallback"""
        try:
            from config import MEMORY_DIR
            path = Path(MEMORY_DIR) / key
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ❌ Context local write failed: {e}")

    def _read_local(self, key: str) -> Optional[Dict]:
        """本地文件系统 fallback 读取"""
        try:
            from config import MEMORY_DIR
            path = Path(MEMORY_DIR) / key
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None


# ── 2. 向量检索记忆 (RAG Memory) ──

class RAGMemory:
    """
    长期向量检索记忆

    将历史对话、用户反馈、工作流产出向量化存储，
    在后续节点中基于语义相似度召回相关记忆。

    存储结构:
        /memories/vector/{thread_id}/documents.json  - 原始文档
        /memories/vector/{thread_id}/index.json      - 向量索引
    """

    def __init__(self, backend=None, thread_id: str = "default"):
        self._backend = backend
        self._thread_id = thread_id
        self._documents: List[Dict] = []
        self._index_built = False

    def add_document(self, content: str, metadata: Optional[Dict] = None, doc_id: Optional[str] = None):
        """
        添加文档到向量库

        Args:
            content: 文档内容
            metadata: 附加元数据（如节点名、时间戳等）
            doc_id: 自定义文档 ID
        """
        if not doc_id:
            doc_id = hashlib.md5(f"{content}_{time.time()}".encode()).hexdigest()[:12]

        doc = {
            "id": doc_id,
            "content": content,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }

        # 生成简单向量（基于词袋模型，生产环境应使用 Embedding 模型）
        doc["vector"] = self._simple_vectorize(content)

        self._documents.append(doc)
        self._index_built = False
        self._persist_documents()

    def add_messages(self, messages: List[Dict], node_name: str = ""):
        """批量添加消息记录"""
        for i, msg in enumerate(messages):
            content = f"[{msg.get('role', '?')}] {msg.get('content', '')}"
            self.add_document(
                content=content,
                metadata={"type": "message", "node": node_name, "index": i},
            )

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        向量相似度搜索

        Args:
            query: 查询文本
            top_k: 返回最相似的 k 条结果

        Returns:
            按相似度排序的文档列表，包含 content, metadata, score 字段
        """
        if not self._documents:
            self._load_documents()

        if not self._documents:
            return []

        query_vec = self._simple_vectorize(query)

        # 计算余弦相似度
        results = []
        for doc in self._documents:
            score = self._cosine_similarity(query_vec, doc.get("vector", []))
            results.append({
                "content": doc["content"],
                "metadata": doc.get("metadata", {}),
                "score": score,
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_all_documents(self) -> List[Dict]:
        """获取所有文档"""
        if not self._documents:
            self._load_documents()
        return list(self._documents)

    def clear(self):
        """清空向量库"""
        self._documents.clear()
        self._index_built = False
        self._persist_documents()

    # ── 向量化方法（简单实现，生产环境用 Embedding 模型替换） ──

    def _simple_vectorize(self, text: str, dim: int = 128) -> List[float]:
        """
        简单向量表示（基于字符哈希）

        生产环境建议替换为：
        - OpenAI Embedding API
        - 本地 Sentence Transformer 模型
        """
        import hashlib
        import struct

        vec = [0.0] * dim
        words = text.lower().split()
        for word in words:
            h = hashlib.md5(word.encode()).digest()
            for i in range(min(dim // 4, len(h) // 4)):
                val = struct.unpack("f", h[i*4:(i+1)*4])[0]
                idx = (i + ord(word[0]) if word else i) % dim
                vec[idx] += val

        # 归一化
        import math
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        import math
        if len(a) != len(b) or len(a) == 0:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        return max(0.0, min(1.0, dot))

    # ── 持久化 ──

    def _persist_documents(self):
        """持久化文档"""
        key = f"vector/{self._thread_id}/documents.json"
        data = {
            "thread_id": self._thread_id,
            "documents": self._documents,
            "count": len(self._documents),
            "updated_at": time.time(),
        }
        self._write(key, data)

    def _load_documents(self):
        """加载文档"""
        key = f"vector/{self._thread_id}/documents.json"
        data = self._read(key)
        if data and "documents" in data:
            self._documents = data["documents"]

    def _write(self, key: str, data: Dict):
        """写入 backend"""
        try:
            if self._backend is not None:
                self._backend.write_file(key, json.dumps(data, ensure_ascii=False, indent=2))
                return
        except Exception as e:
            print(f"  ⚠️ RAG backend write failed: {e}")
        self._write_local(key, data)

    def _read(self, key: str) -> Optional[Dict]:
        try:
            if self._backend is not None:
                content = self._backend.read_file(key)
                return json.loads(content)
        except Exception:
            pass
        return self._read_local(key)

    def _write_local(self, key: str, data: Dict):
        try:
            from config import MEMORY_DIR
            path = Path(MEMORY_DIR) / key
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ❌ RAG local write failed: {e}")

    def _read_local(self, key: str) -> Optional[Dict]:
        try:
            from config import MEMORY_DIR
            path = Path(MEMORY_DIR) / key
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None


# ── 3. 自动摘要记忆 (Summarization Memory) ──

class SummarizationMemory:
    """
    自动摘要记忆

    将冗长的对话历史、节点产出自动摘要，生成精炼的上下文，
    避免 LLM 的上下文窗口溢出，同时保留关键信息。

    摘要触发条件:
    1. 消息数量超过阈值 (默认 20 条)
    2. 单个节点运行超过 N 轮迭代
    3. 显式调用 summarize()

    存储:
        /memories/summary/{thread_id}/summaries.json
    """

    SUMMARIZE_TRIGGER_MSG_COUNT = 20
    SUMMARIZE_TRIGGER_ITER_COUNT = 10

    def __init__(self, backend=None, thread_id: str = "default", llm_summarizer: Optional[Any] = None):
        self._backend = backend
        self._thread_id = thread_id
        self._llm_summarizer = llm_summarizer  # 用于生成摘要的 LLM
        self._summaries: List[Dict] = []

    def should_summarize(self, message_count: int, iteration_count: int = 0) -> bool:
        """判断是否需要触发摘要"""
        return (
            message_count >= self.SUMMARIZE_TRIGGER_MSG_COUNT
            or iteration_count >= self.SUMMARIZE_TRIGGER_ITER_COUNT
        )

    def summarize(self, messages: List[Dict], context: Optional[Dict] = None) -> str:
        """
        生成摘要

        Args:
            messages: 需要摘要的消息列表
            context: 额外上下文

        Returns:
            摘要文本
        """
        if not messages:
            return ""

        # 使用 LLM 生成摘要
        if self._llm_summarizer:
            try:
                text = "\n".join([f"[{m.get('role', '?')}] {m.get('content', '')[:500]}" for m in messages])
                prompt = f"""请对以下工作流对话进行摘要，保留关键决策、数据、人工反馈和行动项：

{text[:3000]}

请输出一段精炼的摘要（200字以内）："""
                response = self._llm_summarizer.invoke(prompt)
                summary = str(response.content) if hasattr(response, "content") else str(response)
            except Exception as e:
                print(f"  ⚠️ LLM 摘要失败: {e}，使用简单摘要")
                summary = self._simple_summarize(messages)
        else:
            summary = self._simple_summarize(messages)

        # 保存摘要
        summary_record = {
            "id": f"summary_{int(time.time())}",
            "summary": summary,
            "source_count": len(messages),
            "context": context or {},
            "timestamp": time.time(),
        }
        self._summaries.append(summary_record)
        self._persist_summaries()

        return summary

    def _simple_summarize(self, messages: List[Dict]) -> str:
        """简单摘要（提取关键信息）"""
        key_points = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "user" and len(content) > 10:
                key_points.append(f"[需求] {content[:100]}")
            elif role == "assistant" and len(content) > 10:
                # 提取关键句
                sentences = content.split("。")
                for s in sentences[:2]:
                    if len(s.strip()) > 5:
                        key_points.append(f"[产出] {s.strip()[:100]}")

        return "；".join(key_points[:10])

    def get_recent_summaries(self, count: int = 3) -> List[str]:
        """获取最近的摘要"""
        if not self._summaries:
            self._load_summaries()
        return [s["summary"] for s in self._summaries[-count:]]

    def get_summaries_as_text(self, count: int = 3) -> str:
        """获取摘要文本（用于 prompt 注入）"""
        summaries = self.get_recent_summaries(count)
        if not summaries:
            return "（暂无历史摘要）"
        return "\n\n".join([f"[历史摘要 {i+1}] {s}" for i, s in enumerate(summaries)])

    def clear(self):
        """清空摘要"""
        self._summaries.clear()
        self._persist_summaries()

    # ── 持久化 ──

    def _persist_summaries(self):
        key = f"summary/{self._thread_id}/summaries.json"
        data = {
            "thread_id": self._thread_id,
            "summaries": self._summaries,
            "count": len(self._summaries),
            "updated_at": time.time(),
        }
        self._write(key, data)

    def _load_summaries(self):
        key = f"summary/{self._thread_id}/summaries.json"
        data = self._read(key)
        if data and "summaries" in data:
            self._summaries = data["summaries"]

    def _write(self, key: str, data: Dict):
        try:
            if self._backend is not None:
                self._backend.write_file(key, json.dumps(data, ensure_ascii=False, indent=2))
                return
        except Exception as e:
            print(f"  ⚠️ Summary backend write failed: {e}")
        self._write_local(key, data)

    def _read(self, key: str) -> Optional[Dict]:
        try:
            if self._backend is not None:
                content = self._backend.read_file(key)
                return json.loads(content)
        except Exception:
            pass
        return self._read_local(key)

    def _write_local(self, key: str, data: Dict):
        try:
            from config import MEMORY_DIR
            path = Path(MEMORY_DIR) / key
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ❌ Summary local write failed: {e}")

    def _read_local(self, key: str) -> Optional[Dict]:
        try:
            from config import MEMORY_DIR
            path = Path(MEMORY_DIR) / key
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None


# ── 4. 统一 Memory Manager ──

class MemoryManager:
    """
    统一记忆管理器

    整合三层记忆：Context + RAG + Summarization
    对外提供统一的记忆读写接口。
    """

    def __init__(
        self,
        backend=None,
        store=None,
        thread_id: str = "default",
        llm_summarizer=None,
    ):
        self.backend = backend
        self.store = store
        self.thread_id = thread_id

        # 初始化三层记忆
        self.context = ContextMemory(backend=backend, thread_id=thread_id)
        self.rag = RAGMemory(backend=backend, thread_id=thread_id)
        self.summarization = SummarizationMemory(
            backend=backend, thread_id=thread_id, llm_summarizer=llm_summarizer
        )

    def enrich_prompt(self, prompt: str, query: Optional[str] = None, rag_top_k: int = 3) -> str:
        """
        使用三层记忆丰富 prompt

        将相关的历史上下文、RAG 召回结果、摘要注入到 prompt 中，
        让 LLM "记住" 过去发生的事情。

        Args:
            prompt: 原始 prompt
            query: 查询文本（用于 RAG 召回）
            rag_top_k: RAG 召回数量

        Returns:
            注入记忆后的 prompt
        """
        memory_sections = []

        # 1. 上下文记忆
        ctx = self.context.get_all_context()
        if ctx:
            ctx_lines = []
            for k, v in list(ctx.items())[-5:]:  # 最多取最近5条
                v_str = str(v)[:200]
                ctx_lines.append(f"  - {k}: {v_str}")
            if ctx_lines:
                memory_sections.append(f"【工作流上下文】\n" + "\n".join(ctx_lines))

        # 2. RAG 召回
        if query:
            rag_results = self.rag.search(query, top_k=rag_top_k)
            if rag_results:
                rag_lines = []
                for r in rag_results:
                    content = r.get("content", "")[:150]
                    score = r.get("score", 0)
                    rag_lines.append(f"  - [{score:.2f}] {content}")
                memory_sections.append("【相关历史记忆】\n" + "\n".join(rag_lines))

        # 3. 摘要
        summaries_text = self.summarization.get_summaries_as_text(count=2)
        if summaries_text and "暂无" not in summaries_text:
            memory_sections.append(f"【历史摘要】\n{summaries_text}")

        # 组装
        if memory_sections:
            memory_block = "\n\n".join(memory_sections)
            enriched = f"""{prompt}

═══════════════════════════════════════
📚 历史记忆（以下信息来自之前的工作流步骤，请作为参考）：
═══════════════════════════════════════

{memory_block}

═══════════════════════════════════════
"""
            return enriched

        return prompt

    def record_node_io(self, node_name: str, node_input: str, node_output: str):
        """记录节点的输入输出到 RAG 和 Context"""
        # RAG
        self.rag.add_document(
            content=f"节点 {node_name} 的产出：{node_output}",
            metadata={"node": node_name, "type": "output"},
        )

        # Context
        self.context.set_context(f"last_{node_name}_output", node_output)

    def record_human_feedback(self, node_name: str, feedback: str):
        """记录人工反馈"""
        self.rag.add_document(
            content=f"用户对 {node_name} 的反馈：{feedback}",
            metadata={"node": node_name, "type": "human_feedback"},
        )
        self.context.set_context(f"{node_name}_feedback", feedback)

    def check_and_summarize(self, messages: List[Dict]) -> Optional[str]:
        """检查并触发摘要"""
        if self.summarization.should_summarize(len(messages)):
            summary = self.summarization.summarize(messages)
            # 摘要也存入 RAG
            self.rag.add_document(
                content=f"历史摘要：{summary}",
                metadata={"type": "summary"},
            )
            return summary
        return None

    def set_thread_id(self, thread_id: str):
        """切换线程 ID"""
        self.thread_id = thread_id
        self.context._thread_id = thread_id
        self.rag._thread_id = thread_id
        self.summarization._thread_id = thread_id

    def set_backend(self, backend):
        """切换后端"""
        self.backend = backend
        self.context._backend = backend
        self.rag._backend = backend
        self.summarization._backend = backend


# ── 全局单例 ──

_memory_manager: Optional[MemoryManager] = None


def get_memory_manager(
    backend=None,
    store=None,
    thread_id: str = "default",
    llm_summarizer=None,
) -> MemoryManager:
    """获取 MemoryManager 单例"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager(
            backend=backend,
            store=store,
            thread_id=thread_id,
            llm_summarizer=llm_summarizer,
        )
    else:
        if backend is not None:
            _memory_manager.set_backend(backend)
        if thread_id != "default":
            _memory_manager.set_thread_id(thread_id)
        if llm_summarizer is not None:
            _memory_manager.summarization._llm_summarizer = llm_summarizer
    return _memory_manager
