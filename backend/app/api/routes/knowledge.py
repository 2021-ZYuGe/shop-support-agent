from __future__ import annotations

from datetime import date

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import select

from app.api.deps import AppSettings, CurrentAdmin, DbSession
from app.db.models import KnowledgeDocument
from app.schemas.knowledge import (
    KnowledgeDocumentList,
    KnowledgeDocumentSummary,
    KnowledgeIndexResponse,
    KnowledgeSearchItem,
    KnowledgeSearchResponse,
    KnowledgeSummary,
)
from app.services import embedding, knowledge as knowledge_service, vector_store

router = APIRouter()


def _summary(db: DbSession, document: KnowledgeDocument) -> KnowledgeDocumentSummary:
    counts = knowledge_service.get_chunk_counts(db, document.id)
    return KnowledgeDocumentSummary(
        id=document.id,
        title=document.title,
        doc_type=document.doc_type,
        version=document.version,
        status=document.status,
        source_name=document.source_name,
        effective_date=document.effective_date,
        created_at=document.created_at,
        updated_at=document.updated_at,
        chunk_count=counts["total"],
        indexed_count=counts["indexed"],
        pending_count=counts["pending"],
        failed_count=counts["failed"],
        index_status=knowledge_service.index_status(
            counts["total"],
            counts["indexed"],
            counts["pending"],
            counts["failed"],
        ),
    )


@router.get("/documents", response_model=KnowledgeDocumentList)
def list_documents(_: CurrentAdmin, db: DbSession) -> KnowledgeDocumentList:
    documents = db.scalars(
        select(KnowledgeDocument).order_by(
            KnowledgeDocument.updated_at.desc(),
            KnowledgeDocument.id.desc(),
        )
    ).all()
    items = [_summary(db, document) for document in documents]
    return KnowledgeDocumentList(
        items=items,
        summary=KnowledgeSummary(
            documents=len(items),
            chunks=sum(item.chunk_count for item in items),
            indexed_chunks=sum(item.indexed_count for item in items),
            pending_chunks=sum(item.pending_count for item in items),
            failed_chunks=sum(item.failed_count for item in items),
        ),
    )


@router.post(
    "/documents",
    response_model=KnowledgeDocumentSummary,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    _: CurrentAdmin,
    db: DbSession,
    settings: AppSettings,
    file: UploadFile = File(...),
    title: str = Form(default=""),
    doc_type: str = Form(default="faq"),
    version: str = Form(default="1.0"),
    effective_date: str | None = Form(default=None),
) -> KnowledgeDocumentSummary:
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择要上传的文档。",
        )

    data = await file.read()
    if len(data) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件不能超过 {settings.max_upload_size_mb}MB。",
        )

    parsed_date: date | None = None
    if effective_date and effective_date.strip():
        try:
            parsed_date = date.fromisoformat(effective_date.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="生效日期格式应为 YYYY-MM-DD。",
            ) from exc

    try:
        document = knowledge_service.create_document(
            db,
            title=title,
            doc_type=doc_type,
            version=version,
            effective_date=parsed_date,
            original_filename=filename,
            data=data,
        )
    except knowledge_service.DuplicateDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except knowledge_service.DocumentParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except knowledge_service.KnowledgeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _summary(db, document)


@router.post(
    "/documents/{document_id}/index",
    response_model=KnowledgeIndexResponse,
)
def index_document(
    document_id: int,
    _: CurrentAdmin,
    db: DbSession,
) -> KnowledgeIndexResponse:
    try:
        outcome = knowledge_service.index_document(db, document_id)
    except knowledge_service.DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except embedding.EmbeddingNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except embedding.EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except vector_store.VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except knowledge_service.KnowledgeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识文档不存在。",
        )

    if outcome.failed:
        message = f"索引完成，但有 {outcome.failed} 个切片失败，可以重试。"
    elif outcome.indexed and outcome.indexed == outcome.total:
        message = "知识库索引已就绪。"
    else:
        message = "没有需要建立索引的切片。"

    return KnowledgeIndexResponse(document=_summary(db, document), message=message)


@router.get("/search", response_model=KnowledgeSearchResponse)
def search(
    _: CurrentAdmin,
    db: DbSession,
    q: str = Query(min_length=1, max_length=500),
    top_k: int = Query(default=5, ge=1, le=20),
) -> KnowledgeSearchResponse:
    try:
        raw_results = knowledge_service.search_knowledge(db, q, top_k)
    except embedding.EmbeddingNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except embedding.EmbeddingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except vector_store.VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except knowledge_service.KnowledgeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return KnowledgeSearchResponse(
        query=q,
        top_k=top_k,
        total=len(raw_results),
        results=[KnowledgeSearchItem(**item) for item in raw_results],
    )
