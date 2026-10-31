from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class VectorStoreError(RuntimeError):
    """Chroma operation failed."""


@dataclass(frozen=True)
class VectorHit:
    chunk_id: int
    chroma_id: str
    similarity: float


class ChromaVectorStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        try:
            path = settings.resolved_chroma_dir
            path.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=str(path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self.collection = self.client.get_or_create_collection(
                name=settings.chroma_collection,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as exc:
            raise VectorStoreError("无法初始化 Chroma 向量索引。") from exc

    def count(self) -> int:
        try:
            return int(self.collection.count())
        except Exception as exc:
            raise VectorStoreError("无法读取 Chroma 向量数量。") from exc

    def upsert(
        self,
        records: list[tuple[int, list[float], dict[str, Any]]],
    ) -> None:
        if not records:
            return
        try:
            self.collection.upsert(
                ids=[f"chunk-{chunk_id}" for chunk_id, _, _ in records],
                embeddings=[vector for _, vector, _ in records],
                metadatas=[metadata for _, _, metadata in records],
            )
        except Exception as exc:
            raise VectorStoreError("写入 Chroma 向量失败。") from exc

    def query(self, embedding: list[float], top_k: int) -> list[VectorHit]:
        try:
            total = self.count()
            if total == 0:
                return []
            result = self.collection.query(
                query_embeddings=[embedding],
                n_results=min(top_k, total),
                include=["metadatas", "distances"],
            )
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError("Chroma 检索失败。") from exc

        ids = (result.get("ids") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        hits: list[VectorHit] = []
        for chroma_id, metadata, distance in zip(ids, metadatas, distances):
            if not metadata or "chunk_id" not in metadata:
                continue
            similarity = max(0.0, min(1.0, 1.0 - float(distance)))
            hits.append(
                VectorHit(
                    chunk_id=int(metadata["chunk_id"]),
                    chroma_id=str(chroma_id),
                    similarity=similarity,
                )
            )
        return hits


@lru_cache
def get_vector_store() -> ChromaVectorStore:
    return ChromaVectorStore(get_settings())
