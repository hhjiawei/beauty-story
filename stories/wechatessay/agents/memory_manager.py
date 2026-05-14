"""
wechatessay.agents.memory_manager

双层记忆系统管理器：
- 短期记忆：当前对话消息列表，使用 OrderedDict 实现 FIFO 淘汰
- 长期记忆：用户偏好、项目事实持久化到本地 JSON，支持混合检索（BM25 + 语义相似度）
- RAG 模块：通过 Ollama/远程 API 向量化，存入 SQLite，检索时混合打分
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from rank_bm25 import BM25Okapi

from wechatessay.config import MEMORY_CONFIG, RAG_CONFIG, MEMORY_DIR

# ── 全局锁 ──
_lt_lock = threading.Lock()
_vec_lock = threading.Lock()


# ═══════════════════════════════════════════════
# 短期记忆（FIFO OrderedDict）
# ═══════════════════════════════════════════════

class ShortTermMemory:
    """
    短期记忆：线程安全的 FIFO 消息缓存。

    使用 OrderedDict 模拟 LinkedHashMap 的访问顺序维护：
    - 当容量满时，淘汰最旧的消息（FIFO）
    - 支持按 key 快速查询
    """

    def __init__(self, capacity: int = None):
        self.capacity = capacity or MEMORY_CONFIG["short_term_capacity"]
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def put(self, key: str, value: Dict[str, Any]) -> None:
        """存入消息，若超出容量则淘汰最旧条目。"""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            while len(self._cache) > self.capacity:
                self._cache.popitem(last=False)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """获取单条消息并移至队尾（LRU 语义）。"""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def get_all(self) -> List[Dict[str, Any]]:
        """按插入顺序返回所有消息。"""
        with self._lock:
            return list(self._cache.values())

    def get_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """获取最近 n 条消息。"""
        with self._lock:
            return list(self._cache.values())[-n:]

    def clear(self) -> None:
        """清空缓存。"""
        with self._lock:
            self._cache.clear()

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._cache.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)


# ═══════════════════════════════════════════════
# 向量数据库（SQLite）
# ═══════════════════════════════════════════════

class VectorStore:
    """
    基于 SQLite 的简单向量存储。
    使用 numpy 数组存储向量，支持余弦相似度检索。
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or RAG_CONFIG["vector_db_path"]
        self.dimension = RAG_CONFIG["vector_dimension"]
        self._init_db()

    def _init_db(self) -> None:
        """初始化向量表。"""
        with _vec_lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    vector BLOB NOT NULL,
                    meta TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vectors_created 
                ON vectors(created_at)
            """)
            conn.commit()
            conn.close()

    def add(self, content: str, vector: List[float], meta: Dict = None) -> int:
        """添加向量记录，返回 id。"""
        vec_bytes = np.array(vector, dtype=np.float32).tobytes()
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
        with _vec_lock:
            conn = sqlite3.connect(self.db_path)
            cur = conn.execute(
                "INSERT INTO vectors (content, vector, meta) VALUES (?, ?, ?)",
                (content, vec_bytes, meta_json),
            )
            conn.commit()
            vid = cur.lastrowid
            conn.close()
            return vid

    def search(
        self,
        query_vector: List[float],
        top_k: int = None,
        threshold: float = None,
    ) -> List[Dict[str, Any]]:
        """向量相似度检索，返回 top_k 条结果。"""
        top_k = top_k or RAG_CONFIG["retrieve_top_k"]
        threshold = threshold or MEMORY_CONFIG["memory_threshold"]
        qvec = np.array(query_vector, dtype=np.float32)

        with _vec_lock:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT id, content, vector, meta FROM vectors ORDER BY created_at DESC"
            ).fetchall()
            conn.close()

        results = []
        for vid, content, vec_bytes, meta_json in rows:
            vec = np.frombuffer(vec_bytes, dtype=np.float32)
            # 余弦相似度
            sim = float(np.dot(qvec, vec) / (np.linalg.norm(qvec) * np.linalg.norm(vec) + 1e-8))
            if sim >= threshold:
                results.append({
                    "id": vid,
                    "content": content,
                    "similarity": sim,
                    "meta": json.loads(meta_json or "{}"),
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def delete(self, vid: int) -> None:
        with _vec_lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM vectors WHERE id = ?", (vid,))
            conn.commit()
            conn.close()

    def clear(self) -> None:
        with _vec_lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM vectors")
            conn.commit()
            conn.close()


# ═══════════════════════════════════════════════
# 长期记忆（JSON 文件 + 混合检索）
# ═══════════════════════════════════════════════

class LongTermMemory:
    """
    长期记忆管理器。

    持久化存储用户偏好、项目事实等信息到本地 JSON 文件。
    检索时采用混合打分：
        score = w_bm25 * bm25_score + w_sem * semantic_score + w_type * type_weight + dual_hit_bonus
    """

    def __init__(self, file_path: str = None):
        self.file_path = Path(file_path or MEMORY_CONFIG["long_term_file"])
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._memories: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """从 JSON 文件加载记忆。"""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._memories = data if isinstance(data, list) else []
            except Exception:
                self._memories = []
        else:
            self._memories = []

    def _save(self) -> None:
        """保存记忆到 JSON 文件。"""
        with _lt_lock:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._memories, f, ensure_ascii=False, indent=2)

    def add(
        self,
        content: str,
        mtype: str = "general",
        tags: List[str] = None,
        weight: float = 1.0,
    ) -> None:
        """
        添加一条长期记忆。

        Args:
            content: 记忆内容
            mtype: 记忆类型（user_preference, project_fact, style_guide, etc.）
            tags: 标签列表
            weight: 权重（用于 type_weight 打分）
        """
        entry = {
            "id": len(self._memories) + 1,
            "content": content,
            "type": mtype,
            "tags": tags or [],
            "weight": weight,
            "created_at": datetime.now().isoformat(),
            "access_count": 0,
        }
        with _lt_lock:
            self._memories.append(entry)
        self._save()

    def retrieve(
        self,
        query: str,
        query_vector: Optional[List[float]] = None,
        top_k: int = None,
    ) -> List[Dict[str, Any]]:
        """
        混合检索长期记忆。

        打分公式：
            final_score = bm25_w * norm_bm25 + sem_w * norm_semantic + type_w * norm_type + dual_bonus

        Args:
            query: 文本查询
            query_vector: 查询向量（可选，若提供则计算语义相似度）
            top_k: 返回条数

        Returns:
            按得分降序排列的记忆列表
        """
        top_k = top_k or MEMORY_CONFIG["max_injected_memories"]
        if not self._memories:
            return []

        # ── BM25 打分 ──
        tokenized_corpus = [m["content"].split() for m in self._memories]
        bm25 = BM25Okapi(tokenized_corpus)
        bm25_scores = bm25.get_scores(query.split())
        max_bm25 = bm25_scores.max() if bm25_scores.max() > 0 else 1.0
        norm_bm25 = bm25_scores / max_bm25

        # ── 语义相似度打分 ──
        if query_vector is not None:
            # 简化的语义相似度：使用 dot product 近似
            qvec = np.array(query_vector, dtype=np.float32)
            sem_scores = np.zeros(len(self._memories))
            for i, m in enumerate(self._memories):
                # 这里使用 content 的 hash 作为简单向量近似
                # 实际应调用 embedding API
                mvec = self._simple_hash_vector(m["content"])
                sim = float(np.dot(qvec, mvec) / (np.linalg.norm(qvec) * np.linalg.norm(mvec) + 1e-8))
                sem_scores[i] = sim
            max_sem = sem_scores.max() if sem_scores.max() > 0 else 1.0
            norm_sem = sem_scores / max_sem
        else:
            norm_sem = np.zeros(len(self._memories))

        # ── 类型权重打分 ──
        type_weights = np.array([
            MEMORY_CONFIG.get("type_weights", {}).get(m["type"], 1.0)
            for m in self._memories
        ])
        max_tw = type_weights.max() if type_weights.max() > 0 else 1.0
        norm_type = type_weights / max_tw

        # ── 双命中奖励 ──
        dual_bonus = np.where(
            (norm_bm25 > 0.5) & (norm_sem > 0.5),
            MEMORY_CONFIG["dual_hit_bonus"],
            0.0,
        )

        # ── 综合打分 ──
        w_bm25 = MEMORY_CONFIG["bm25_weight"]
        w_sem = MEMORY_CONFIG["semantic_weight"]
        w_type = MEMORY_CONFIG["type_weight"]

        final_scores = (
            w_bm25 * norm_bm25
            + w_sem * norm_sem
            + w_type * norm_type
            + dual_bonus
        )

        # ── 排序返回 ──
        indexed = list(enumerate(final_scores))
        indexed.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed[:top_k]:
            mem = self._memories[idx].copy()
            mem["retrieval_score"] = round(float(score), 4)
            results.append(mem)

        return results

    @staticmethod
    def _simple_hash_vector(text: str, dim: int = None) -> np.ndarray:
        """基于 hash 的简单向量表示（ fallback 用）。"""
        dim = dim or RAG_CONFIG["vector_dimension"]
        vec = np.zeros(dim, dtype=np.float32)
        for i, ch in enumerate(text):
            vec[i % dim] += ord(ch) % 100
        norm = np.linalg.norm(vec)
        return vec / (norm + 1e-8)

    def update_access(self, mem_id: int) -> None:
        """更新访问计数。"""
        with _lt_lock:
            for m in self._memories:
                if m["id"] == mem_id:
                    m["access_count"] = m.get("access_count", 0) + 1
                    break
        self._save()

    def delete(self, mem_id: int) -> None:
        with _lt_lock:
            self._memories = [m for m in self._memories if m["id"] != mem_id]
        self._save()

    def list_all(self) -> List[Dict[str, Any]]:
        return self._memories.copy()


# ═══════════════════════════════════════════════
# 统一记忆管理器
# ═══════════════════════════════════════════════

class MemoryManager:
    """
    统一记忆入口：短期记忆 + 长期记忆 + RAG 向量存储。

    使用单例模式避免重复初始化。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.vector_store = VectorStore()

    # ── 短期记忆接口 ──
    def add_short_term(self, key: str, value: Dict[str, Any]) -> None:
        self.short_term.put(key, value)

    def get_short_term(self, key: str) -> Optional[Dict[str, Any]]:
        return self.short_term.get(key)

    def get_recent_context(self, n: int = 10) -> List[Dict[str, Any]]:
        return self.short_term.get_recent(n)

    # ── 长期记忆接口 ──
    def add_long_term(
        self,
        content: str,
        mtype: str = "general",
        tags: List[str] = None,
        weight: float = 1.0,
    ) -> None:
        self.long_term.add(content, mtype, tags, weight)

    def retrieve_long_term(
        self,
        query: str,
        query_vector: Optional[List[float]] = None,
        top_k: int = None,
    ) -> List[Dict[str, Any]]:
        return self.long_term.retrieve(query, query_vector, top_k)

    # ── RAG 向量接口 ──
    def add_to_vector_store(
        self, content: str, vector: List[float], meta: Dict = None
    ) -> int:
        return self.vector_store.add(content, vector, meta)

    def vector_search(
        self, query_vector: List[float], top_k: int = None
    ) -> List[Dict[str, Any]]:
        return self.vector_store.search(query_vector, top_k)

    # ── 混合检索：注入系统提示词用 ──
    def build_memory_context(self, query: str, query_vector: List[float] = None) -> str:
        """
        构建记忆上下文字符串，用于注入 Agent 的系统提示词。
        优先使用长期记忆混合检索结果。
        """
        memories = self.retrieve_long_term(query, query_vector)
        if not memories:
            return ""

        lines = ["## 相关记忆与偏好", ""]
        for m in memories:
            lines.append(f"- [{m['type']}] {m['content']}")
        return "\n".join(lines)

    # ── 持久化接口 ──
    def save_all(self) -> None:
        self.long_term._save()

    def clear_all(self) -> None:
        self.short_term.clear()
        self.long_term._memories.clear()
        self.long_term._save()
        self.vector_store.clear()


# ── 全局获取函数 ──

def get_memory_manager() -> MemoryManager:
    """获取全局唯一的记忆管理器实例。"""
    return MemoryManager()
