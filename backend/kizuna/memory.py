# -*- coding: utf-8 -*-
"""
长期记忆检索层
两层：
  1. 向量检索：把重要记忆向量化后用 ChromaDB 做相似搜索（语义近）
  2. 结构化过滤：用户画像/纪念日直接按标签和 pinned 挑出

所有功能都走 MemoryStore 类，应用层不用知道底层。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

try:
    import chromadb
    from chromadb.utils import embedding_functions
except Exception:   # pragma: no cover
    chromadb = None
    embedding_functions = None

from sqlalchemy.ext.asyncio import AsyncSession
from .db import MemoryEntry, MEMORY_CATEGORIES


CHROMA_COLLECTION_NAME = "kizuna_memories"
DEFAULT_EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"   # 支持中英文，模型不大


@dataclass
class RetrievedMemory:
    """检索返回的记忆"""
    id: int
    category: str
    title: str
    content: str
    score: float    # 0~1，越高越相关
    pinned: bool
    tags: str


class MemoryStore:
    """长期记忆：SQLite 主存 + ChromaDB 向量检索"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self._chroma_client = None
        self._collection = None
        self._init_chroma()

    # ------------ Chroma 初始化（尽量优雅降级）------------
    def _init_chroma(self):
        if chromadb is None:
            print("[KIZUNA] 未安装 chromadb，仅使用关键词检索。pip install chromadb sentence-transformers 可启用语义搜索")
            return
        try:
            self._chroma_client = chromadb.PersistentClient(
                path=os.path.join(self.data_dir, "chroma_db")
            )
            # 用 sentence-transformers 做中文向量（离线）；没装就用 Chroma 默认（英文的，效果差但能用）
            try:
                ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=DEFAULT_EMBED_MODEL
                )
            except Exception as e:
                print(f"[KIZUNA] sentence-transformers 不可用({e})，回退到默认嵌入")
                ef = None
            self._collection = self._chroma_client.get_or_create_collection(
                CHROMA_COLLECTION_NAME,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            print(f"[KIZUNA] 向量库初始化失败，只用关键词检索: {e}")
            self._chroma_client = None

    # ------------ 写入 ------------
    async def add(
        self,
        session: AsyncSession,
        *,
        category: str,
        title: str,
        content: str,
        tags: str = "",
        weight: float = 1.0,
        pinned: bool = False,
    ) -> MemoryEntry:
        """新增一条记忆"""
        entry = MemoryEntry(
            category=category, title=title, content=content,
            tags=tags, weight=weight, pinned=pinned,
        )
        session.add(entry)
        await session.flush()
        # 同步到向量库
        self._upsert_vector(entry.id, title, content, tags, category)
        return entry

    def _upsert_vector(self, mid: int, title: str, content: str, tags: str, category: str):
        if not self._collection:
            return
        text = f"[{MEMORY_CATEGORIES.get(category, category)}] {title}\n{content}\n标签: {tags}"
        try:
            self._collection.upsert(
                ids=[str(mid)],
                documents=[text],
                metadatas=[{
                    "category": category,
                    "title": title,
                    "tags": tags,
                }],
            )
        except Exception as e:
            print(f"[KIZUNA] 写向量失败(id={mid}): {e}")

    async def delete(self, session: AsyncSession, memory_id: int):
        m = await session.get(MemoryEntry, memory_id)
        if m:
            await session.delete(m)
            if self._collection:
                try:
                    self._collection.delete(ids=[str(memory_id)])
                except Exception:
                    pass

    # ------------ 检索 ------------
    async def search(
        self,
        session: AsyncSession,
        query_text: str,
        *,
        top_k: int = 8,
        category: Optional[str] = None,
    ) -> List[RetrievedMemory]:
        """根据一段文本召回相关记忆（召回率最重要，宁多勿少）"""
        results: List[RetrievedMemory] = []
        seen = set()

        # 1. 向量相似召回
        if self._collection:
            try:
                where = {"category": category} if category else None
                raw = self._collection.query(
                    query_texts=[query_text],
                    n_results=max(top_k, 12),
                    where=where,
                )
                ids = raw["ids"][0] if raw["ids"] else []
                dists = raw["distances"][0] if raw["distances"] else [1.0] * len(ids)
                docs = raw["documents"][0] if raw["documents"] else [""] * len(ids)
                for mid_s, dist, doc in zip(ids, dists, docs):
                    try:
                        mid = int(mid_s)
                        if mid in seen:
                            continue
                        seen.add(mid)
                        # cosine distance 0~2 → 0~1 分
                        score = max(0.0, 1.0 - float(dist) / 2.0)
                        entry = await session.get(MemoryEntry, mid)
                        if not entry:
                            continue
                        # 更新访问计数
                        entry.last_accessed_at = datetime.now()
                        entry.access_count += 1
                        results.append(RetrievedMemory(
                            id=entry.id, category=entry.category, title=entry.title,
                            content=entry.content, score=score,
                            pinned=entry.pinned, tags=entry.tags,
                        ))
                    except Exception:
                        continue
            except Exception as e:
                print(f"[KIZUNA] 向量搜索失败: {e}")

        # 2. 关键词兜底：pinned + 用户画像 + 纪念日 一定出现
        from sqlalchemy import select, or_, func
        keywords = [w for w in re.split(r"\s+|，|。|、|,|\.", query_text) if len(w) >= 2]

        q = select(MemoryEntry)
        if category:
            q = q.where(MemoryEntry.category == category)
        else:
            q = q.where(or_(
                MemoryEntry.pinned == True,
                MemoryEntry.category == "user_profile",
                MemoryEntry.category == "anniversary",
            ))
        q = q.order_by(MemoryEntry.weight.desc(), MemoryEntry.access_count.desc()).limit(top_k * 2)
        rows = (await session.execute(q)).scalars().all()
        for entry in rows:
            if entry.id in seen:
                continue
            seen.add(entry.id)
            # 关键词命中加分
            hit = 0
            if keywords:
                blob = f"{entry.title}\n{entry.content}\n{entry.tags}"
                hit = sum(1 for kw in keywords if kw in blob)
            score = 0.6 if entry.pinned else 0.4
            score += min(0.4, hit * 0.15)
            entry.last_accessed_at = datetime.now()
            entry.access_count += 1
            results.append(RetrievedMemory(
                id=entry.id, category=entry.category, title=entry.title,
                content=entry.content, score=score,
                pinned=entry.pinned, tags=entry.tags,
            ))

        # 排序：pinned 优先 + score 第二
        results.sort(key=lambda r: (0 if r.pinned else 1, -r.score))
        return results[:top_k]

    # ------------ 简单列出 ------------
    async def list_all(
        self,
        session: AsyncSession,
        *,
        category: Optional[str] = None,
        limit: int = 500,
    ) -> List[MemoryEntry]:
        from sqlalchemy import select
        q = select(MemoryEntry)
        if category:
            q = q.where(MemoryEntry.category == category)
        q = q.order_by(MemoryEntry.pinned.desc(), MemoryEntry.weight.desc(), MemoryEntry.created_at.desc()).limit(limit)
        return list((await session.execute(q)).scalars().all())

    async def format_for_prompt(self, mems: Iterable[RetrievedMemory]) -> str:
        """把检索到的记忆拼到 system prompt 里"""
        lines = ["【你记得的关于主人的一切（按相关度排序）】"]
        any = False
        for m in mems:
            any = True
            cat = MEMORY_CATEGORIES.get(m.category, m.category)
            tag = f"🏷 {m.tags}" if m.tags else ""
            pin = "⭐重要" if m.pinned else ""
            lines.append(f"- [{cat}{pin}] {m.title}：{m.content} {tag}".rstrip())
        if not any:
            lines.append("- （你还没有记住任何关于主人的事，先从聊天开始吧～）")
        lines.append("——— 以上是你记得的事，对话中可以自然提起 ———\n")
        return "\n".join(lines)
