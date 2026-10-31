from __future__ import annotations

import hashlib
import io
import logging
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from docx import Document as DocxDocument
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.models import KnowledgeChunk, KnowledgeDocument
from app.services import embedding, vector_store

logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES = {".md", ".markdown", ".txt", ".pdf", ".docx"}
MAX_CHUNKS_PER_DOCUMENT = 200
_INDEX_LOCK = threading.Lock()


class KnowledgeError(RuntimeError):
    """Base class for knowledge ingestion failures."""


class DocumentParseError(KnowledgeError):
    """The uploaded document could not be parsed."""


class DuplicateDocumentError(KnowledgeError):
    """The same document content has already been uploaded."""


class DocumentNotFoundError(KnowledgeError):
    """The requested document does not exist."""


@dataclass(frozen=True)
class IndexOutcome:
    total: int
    indexed: int
    pending: int
    failed: int
    status: str


def index_status(total: int, indexed: int, pending: int, failed: int) -> str:
    if total == 0:
        return "empty"
    if failed and indexed:
        return "partial"
    if failed:
        return "failed"
    if indexed == total:
        return "indexed"
    return "pending"


def get_chunk_counts(db: Session, document_id: int) -> dict[str, int]:
    rows = db.execute(
        select(KnowledgeChunk.vector_status, func.count())
        .where(KnowledgeChunk.document_id == document_id)
        .group_by(KnowledgeChunk.vector_status)
    ).all()
    counts = {status: int(count) for status, count in rows}
    indexed = counts.get("indexed", 0)
    failed = counts.get("failed", 0)
    total = sum(counts.values())
    pending = total - indexed - failed
    return {
        "total": total,
        "indexed": indexed,
        "pending": pending,
        "failed": failed,
    }


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _decode_plain_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocumentParseError("无法识别文本编码，请使用 UTF-8 或 GB18030。")


def _extract_pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise DocumentParseError("PDF 解析失败，请确认文件未损坏。") from exc
    text = "\n\n".join(page for page in pages if page)
    if not text.strip():
        raise DocumentParseError(
            "PDF 中没有可提取的文本。当前版本不支持扫描件 OCR。"
        )
    return text


def _extract_docx(data: bytes) -> str:
    try:
        document = DocxDocument(io.BytesIO(data))
    except Exception as exc:
        raise DocumentParseError("DOCX 解析失败，请确认文件未损坏。") from exc

    parts = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n\n".join(parts)


def extract_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise DocumentParseError("仅支持 Markdown、TXT、PDF 和 DOCX 文档。")

    if suffix == ".pdf":
        text = _extract_pdf(data)
    elif suffix == ".docx":
        text = _extract_docx(data)
    else:
        text = _decode_plain_text(data)

    text = _normalize_text(text)
    if len(text) < 10:
        raise DocumentParseError("文档内容过短，至少需要 10 个字符。")
    return text


def _sections(text: str) -> list[tuple[str | None, str]]:
    heading_re = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$")
    sections: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append((current_heading, body))
        buffer.clear()

    for line in text.split("\n"):
        match = heading_re.match(line)
        if match:
            flush()
            current_heading = match.group(1).strip()
        else:
            buffer.append(line)
    flush()

    if not sections and text.strip():
        return [(None, text.strip())]
    return sections


def _hard_split(segment: str, max_chars: int) -> list[str]:
    return [segment[index : index + max_chars] for index in range(0, len(segment), max_chars)]


def _segments(paragraph: str, max_chars: int) -> list[str]:
    cleaned = re.sub(r"[ \t]+", " ", paragraph).strip()
    if not cleaned:
        return []
    raw_segments = re.split(r"\n+|(?<=[。！？!?；;])", cleaned)
    output: list[str] = []
    for raw in raw_segments:
        raw = raw.strip()
        if not raw:
            continue
        if len(raw) > max_chars:
            output.extend(_hard_split(raw, max_chars))
        else:
            output.append(raw)
    return output


def chunk_document(
    text: str,
    max_chars: int = 600,
    overlap: int = 80,
) -> list[tuple[str | None, str]]:
    """Split text into heading-aware chunks at sentence boundaries.

    The returned heading is stored separately; the raw content excludes it.
    Embedding text can add the heading back for better retrieval context.
    """

    normalized = _normalize_text(text)
    if not normalized:
        return []

    chunks: list[tuple[str | None, str]] = []
    seen_hashes: set[str] = set()

    def append_chunk(heading: str | None, content: str) -> None:
        content = content.strip()
        if not content:
            return
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if digest in seen_hashes:
            return
        seen_hashes.add(digest)
        chunks.append((heading, content))

    for heading, body in _sections(normalized):
        current: list[str] = []
        current_len = 0

        for paragraph in re.split(r"\n\s*\n", body):
            for segment in _segments(paragraph, max_chars):
                separator_length = 1 if current else 0
                if current and current_len + separator_length + len(segment) > max_chars:
                    content = "\n".join(current).strip()
                    append_chunk(heading, content)
                    tail = content[-overlap:].strip() if overlap > 0 else ""
                    if tail and len(tail) + 1 + len(segment) <= max_chars:
                        current = [tail]
                        current_len = len(tail)
                    else:
                        current = []
                        current_len = 0

                if current:
                    current_len += 1
                current.append(segment)
                current_len += len(segment)

        append_chunk(heading, "\n".join(current))

    if len(chunks) > MAX_CHUNKS_PER_DOCUMENT:
        raise DocumentParseError(
            f"文档切片超过 {MAX_CHUNKS_PER_DOCUMENT} 个，请拆分后再上传。"
        )
    return chunks


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def create_document(
    db: Session,
    *,
    title: str,
    doc_type: str,
    version: str,
    effective_date: date | None,
    original_filename: str,
    data: bytes,
) -> KnowledgeDocument:
    settings = get_settings()
    if not data:
        raise DocumentParseError("上传文件为空。")
    if len(data) > settings.max_upload_size_mb * 1024 * 1024:
        raise DocumentParseError(
            f"文件超过 {settings.max_upload_size_mb}MB 限制。"
        )

    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise DocumentParseError("仅支持 Markdown、TXT、PDF 和 DOCX 文档。")

    checksum = hashlib.sha256(data).hexdigest()
    existing = db.scalar(
        select(KnowledgeDocument).where(KnowledgeDocument.checksum == checksum)
    )
    if existing is not None:
        raise DuplicateDocumentError(
            f"相同内容的文档已存在：{existing.title}"
        )

    text = extract_text(original_filename, data)
    chunks = chunk_document(text)
    if not chunks:
        raise DocumentParseError("文档没有生成有效切片。")

    upload_dir = settings.resolved_upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / f"{uuid.uuid4().hex}{suffix}"

    title = (title or Path(original_filename).stem).strip()[:200]
    doc_type = (doc_type or "faq").strip()[:32]
    version = (version or "1.0").strip()[:32]
    source_name = Path(original_filename).name[:255]

    try:
        stored_path.write_bytes(data)
        document = KnowledgeDocument(
            title=title,
            doc_type=doc_type,
            version=version,
            status="active",
            source_name=source_name,
            checksum=checksum,
            effective_date=effective_date,
            chunks=[
                KnowledgeChunk(
                    chunk_index=index,
                    heading=heading,
                    content=content,
                    vector_status="pending",
                    content_hash=_content_hash(content),
                )
                for index, (heading, content) in enumerate(chunks)
            ],
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        logger.info(
            "Document ingested: id=%s title=%s chunks=%s",
            document.id,
            document.title,
            len(chunks),
        )
        return document
    except Exception:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise


def _mark_failed(chunks: list[KnowledgeChunk], error: Exception, db: Session) -> None:
    message = str(error)[:2000] or error.__class__.__name__
    for chunk in chunks:
        chunk.vector_status = "failed"
        chunk.index_error = message
    db.commit()


def index_document(db: Session, document_id: int) -> IndexOutcome:
    settings = get_settings()
    with _INDEX_LOCK:
        document = db.get(KnowledgeDocument, document_id)
        if document is None:
            raise DocumentNotFoundError("知识文档不存在。")

        target_chunks = [
            chunk
            for chunk in sorted(document.chunks, key=lambda item: item.chunk_index)
            if chunk.vector_status in {"pending", "failed"}
        ]
        if not target_chunks:
            counts = get_chunk_counts(db, document.id)
            return IndexOutcome(
                **counts,
                status=index_status(
                    counts["total"],
                    counts["indexed"],
                    counts["pending"],
                    counts["failed"],
                ),
            )

        if not settings.has_siliconflow_key:
            raise embedding.EmbeddingNotConfiguredError(
                "尚未配置 SILICONFLOW_API_KEY，无法建立向量索引。"
            )

        texts = [
            f"{chunk.heading}\n{chunk.content}" if chunk.heading else chunk.content
            for chunk in target_chunks
        ]

        try:
            vectors = embedding.get_embedding_client().embed_texts(texts)
            records = []
            for chunk, vector in zip(target_chunks, vectors):
                metadata: dict[str, Any] = {
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "title": document.title,
                    "doc_type": document.doc_type,
                    "version": document.version,
                    "chunk_index": chunk.chunk_index,
                    "source_name": document.source_name,
                    "embedding_model": settings.embedding_model,
                }
                if chunk.heading:
                    metadata["heading"] = chunk.heading
                if document.effective_date:
                    metadata["effective_date"] = document.effective_date.isoformat()
                records.append((chunk.id, vector, metadata))

            vector_store.get_vector_store().upsert(records)
        except (
            embedding.EmbeddingNotConfiguredError,
            embedding.EmbeddingError,
            vector_store.VectorStoreError,
        ) as exc:
            _mark_failed(target_chunks, exc, db)
            raise
        except Exception as exc:
            _mark_failed(target_chunks, exc, db)
            raise KnowledgeError("建立向量索引时发生未知错误。") from exc

        for chunk in target_chunks:
            chunk.vector_status = "indexed"
            chunk.embedding_model = settings.embedding_model
            chunk.chroma_id = f"chunk-{chunk.id}"
            chunk.index_error = None
        document.updated_at = utcnow()
        db.commit()

        counts = get_chunk_counts(db, document.id)
        logger.info(
            "Document indexed: id=%s chunks=%s status=%s",
            document.id,
            len(target_chunks),
            index_status(
                counts["total"],
                counts["indexed"],
                counts["pending"],
                counts["failed"],
            ),
        )
        return IndexOutcome(
            **counts,
            status=index_status(
                counts["total"],
                counts["indexed"],
                counts["pending"],
                counts["failed"],
            ),
        )


def search_knowledge(
    db: Session,
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    settings = get_settings()
    query = query.strip()
    if not query:
        raise KnowledgeError("检索内容不能为空。")
    if not settings.has_siliconflow_key:
        raise embedding.EmbeddingNotConfiguredError(
            "尚未配置 SILICONFLOW_API_KEY，无法执行语义检索。"
        )

    query_vector = embedding.get_embedding_client().embed_query(query)
    hits = vector_store.get_vector_store().query(query_vector, top_k)
    if not hits:
        return []

    chunk_ids = [hit.chunk_id for hit in hits]
    rows = db.scalars(
        select(KnowledgeChunk)
        .options(joinedload(KnowledgeChunk.document))
        .where(KnowledgeChunk.id.in_(chunk_ids))
    ).all()
    by_id = {row.id: row for row in rows}

    results: list[dict[str, Any]] = []
    for hit in hits:
        chunk = by_id.get(hit.chunk_id)
        if chunk is None:
            continue
        results.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document.id,
                "title": chunk.document.title,
                "doc_type": chunk.document.doc_type,
                "version": chunk.document.version,
                "heading": chunk.heading,
                "content": chunk.content,
                "source_name": chunk.document.source_name,
                "similarity": hit.similarity,
            }
        )
    return results
