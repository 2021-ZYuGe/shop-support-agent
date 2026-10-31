from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.base import UtcSerializationModel


class KnowledgeSummary(BaseModel):
    documents: int
    chunks: int
    indexed_chunks: int
    pending_chunks: int
    failed_chunks: int


class KnowledgeDocumentSummary(UtcSerializationModel):
    id: int
    title: str
    doc_type: str
    version: str
    status: str
    source_name: str
    effective_date: date | None
    created_at: datetime
    updated_at: datetime
    chunk_count: int
    indexed_count: int
    pending_count: int
    failed_count: int
    index_status: Literal["empty", "pending", "partial", "indexed", "failed"]


class KnowledgeDocumentList(BaseModel):
    items: list[KnowledgeDocumentSummary]
    summary: KnowledgeSummary


class KnowledgeIndexResponse(BaseModel):
    document: KnowledgeDocumentSummary
    message: str


class KnowledgeSearchItem(BaseModel):
    chunk_id: int
    document_id: int
    title: str
    doc_type: str
    version: str
    heading: str | None
    content: str
    source_name: str
    similarity: float


class KnowledgeSearchResponse(BaseModel):
    query: str
    top_k: int
    total: int
    results: list[KnowledgeSearchItem]
