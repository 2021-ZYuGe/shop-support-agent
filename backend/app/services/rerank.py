from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class RerankError(RuntimeError):
    """The SiliconFlow rerank API failed."""


class RerankNotConfiguredError(RerankError):
    """The SiliconFlow API key is missing."""


@dataclass(frozen=True)
class RerankHit:
    index: int
    score: float


class SiliconFlowRerankClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.endpoint = f"{settings.siliconflow_base_url.rstrip('/')}/rerank"

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> list[RerankHit]:
        if not documents:
            return []
        if not self.settings.has_siliconflow_key:
            raise RerankNotConfiguredError(
                "尚未配置 SILICONFLOW_API_KEY，无法执行 Reranker。"
            )

        try:
            response = httpx.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.settings.siliconflow_api_key}"
                },
                json={
                    "model": self.settings.rerank_model,
                    "query": query,
                    "documents": documents,
                    "top_n": min(top_n, len(documents)),
                },
                timeout=self.settings.embedding_timeout_seconds,
            )
            if response.status_code != 200:
                logger.warning(
                    "Rerank API failed: status=%s body=%s",
                    response.status_code,
                    response.text[:300],
                )
                raise RerankError(
                    f"Rerank API 调用失败（HTTP {response.status_code}）。"
                )
            hits = [
                RerankHit(
                    index=int(item.get("index", 0)),
                    score=float(item.get("relevance_score", 0.0)),
                )
                for item in (response.json().get("results") or [])
            ]
            hits.sort(key=lambda item: item.score, reverse=True)
            return hits
        except httpx.HTTPError as exc:
            raise RerankError("Rerank API 网络请求失败，请稍后重试。") from exc


@lru_cache
def get_rerank_client() -> SiliconFlowRerankClient:
    return SiliconFlowRerankClient(get_settings())
