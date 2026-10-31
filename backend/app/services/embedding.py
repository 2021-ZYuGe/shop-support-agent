from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from functools import lru_cache

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    """External embedding API failed."""


class EmbeddingNotConfiguredError(EmbeddingError):
    """The embedding API key is missing."""


class SiliconFlowEmbeddingClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.endpoint = f"{settings.siliconflow_base_url.rstrip('/')}/embeddings"

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.settings.has_siliconflow_key:
            raise EmbeddingNotConfiguredError(
                "尚未配置 SILICONFLOW_API_KEY，无法生成向量。"
            )

        batch_size = max(1, self.settings.embedding_batch_size)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = [text for text in texts[start : start + batch_size]]
            body = self._request_batch(batch)
            items = body.get("data") or []
            if len(items) != len(batch):
                raise EmbeddingError("Embedding API 返回的向量数量与输入不一致。")

            ordered = sorted(items, key=lambda item: int(item.get("index", 0)))
            for item in ordered:
                vector = item.get("embedding") or []
                if not isinstance(vector, list) or not vector:
                    raise EmbeddingError("Embedding API 返回了空向量。")
                vectors.append([float(value) for value in vector])

            usage = body.get("usage") or {}
            logger.info(
                "Embedding batch indexed: inputs=%s tokens=%s",
                len(batch),
                usage.get("total_tokens", "unknown"),
            )

        if not vectors:
            raise EmbeddingError("Embedding API 没有返回向量。")
        dimension = len(vectors[0])
        if any(len(vector) != dimension for vector in vectors):
            raise EmbeddingError("Embedding API 返回了不一致的向量维度。")
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def _request_batch(self, batch: list[str]) -> dict:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = httpx.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.settings.siliconflow_api_key}"
                    },
                    json={
                        "model": self.settings.embedding_model,
                        "input": batch,
                    },
                    timeout=self.settings.embedding_timeout_seconds,
                )
                if response.status_code == 200:
                    return response.json()

                if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue

                logger.warning(
                    "Embedding API failed: status=%s body=%s",
                    response.status_code,
                    response.text[:300],
                )
                raise EmbeddingError(
                    f"Embedding API 调用失败（HTTP {response.status_code}）。"
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise EmbeddingError("Embedding API 网络请求失败，请稍后重试。") from exc

        raise EmbeddingError("Embedding API 请求失败，请稍后重试。") from last_error


@lru_cache
def get_embedding_client() -> SiliconFlowEmbeddingClient:
    return SiliconFlowEmbeddingClient(get_settings())
