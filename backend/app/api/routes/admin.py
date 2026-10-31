from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import AppSettings, CurrentAdmin, DbSession
from app.db.base import utcnow
from app.db.models import (
    HandoffTicket,
    KnowledgeChunk,
    KnowledgeDocument,
    Message,
    Order,
    Product,
)
from app.schemas.admin import (
    Capability,
    DashboardResponse,
    MetricSet,
    OrderListItem,
    OrderListResponse,
    RecentOrder,
)

router = APIRouter()


def _count(db: DbSession, model: type) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


@router.get("/overview", response_model=DashboardResponse)
def overview(
    _: CurrentAdmin,
    db: DbSession,
    settings: AppSettings,
) -> DashboardResponse:
    indexed_chunks = int(
        db.scalar(
            select(func.count())
            .select_from(KnowledgeChunk)
            .where(KnowledgeChunk.vector_status == "indexed")
        )
        or 0
    )
    metrics = MetricSet(
        products=_count(db, Product),
        orders=_count(db, Order),
        knowledge_documents=_count(db, KnowledgeDocument),
        knowledge_chunks=_count(db, KnowledgeChunk),
        indexed_chunks=indexed_chunks,
        open_tickets=int(
            db.scalar(
                select(func.count())
                .select_from(HandoffTicket)
                .where(HandoffTicket.status == "open")
            )
            or 0
        ),
        messages=_count(db, Message),
    )

    ingestion_ready = indexed_chunks > 0
    retrieval_ready = ingestion_ready and settings.has_siliconflow_key

    recent_orders = db.scalars(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.shipment))
        .order_by(Order.placed_at.desc(), Order.id.desc())
        .limit(5)
    ).all()

    capabilities = [
        Capability(
            key="database",
            label="MySQL 数据层",
            status="ready",
            description="订单、知识切片、会话和工单的数据模型已建立。",
        ),
        Capability(
            key="admin_auth",
            label="运营认证",
            status="ready",
            description="管理员账号、密码哈希和数据库会话已启用。",
        ),
        Capability(
            key="rag_ingestion",
            label="知识库入库",
            status="ready" if ingestion_ready else "pending",
            description=(
                f"{indexed_chunks}/{metrics.knowledge_chunks} 个切片已写入 Chroma。"
                if ingestion_ready
                else "上传文档并建立向量索引后可用。"
            ),
        ),
        Capability(
            key="retrieval",
            label="语义检索",
            status="ready" if retrieval_ready else "pending",
            description=(
                "可在知识库页运行 Top-K 语义检索并查看引用片段。"
                if retrieval_ready
                else "配置 SiliconFlow Key 并完成索引后可用。"
            ),
        ),
        Capability(
            key="ai_chat",
            label="RAG 问答",
            status=(
                "ready"
                if retrieval_ready and settings.has_deepseek_key
                else "pending"
            ),
            description=(
                "DeepSeek 流式回答、引用与拒答已接入。"
                if retrieval_ready and settings.has_deepseek_key
                else "需要完成知识索引并配置 DeepSeek Key。"
            ),
        ),
        Capability(
            key="agent_tools",
            label="Agent 业务工具",
            status="ready",
            description="订单、物流、售后条件判断与人工工单已接入。",
        ),
        Capability(
            key="operations",
            label="运营闭环",
            status="ready",
            description="会话、工单、反馈与运营洞察已接入。",
        ),
        Capability(
            key="evaluation",
            label="评测与优化",
            status="ready",
            description="50 条评测集、Reranker 与 Prompt 对比已接入。",
        ),
    ]

    return DashboardResponse(
        metrics=metrics,
        recent_orders=[
            RecentOrder(
                order_no=order.order_no,
                customer_name=order.customer_name,
                status=order.status,
                placed_at=order.placed_at,
                total_cents=order.total_cents,
                item_count=sum(item.quantity for item in order.items),
                shipment_status=order.shipment.status if order.shipment else None,
            )
            for order in recent_orders
        ],
        capabilities=capabilities,
        generated_at=utcnow(),
    )


@router.get("/orders", response_model=OrderListResponse)
def list_orders(
    _: CurrentAdmin,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> OrderListResponse:
    total = int(db.scalar(select(func.count()).select_from(Order)) or 0)
    orders = db.scalars(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.shipment))
        .order_by(Order.placed_at.desc(), Order.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return OrderListResponse(
        items=[
            OrderListItem(
                order_no=order.order_no,
                customer_name=order.customer_name,
                customer_phone=order.customer_phone,
                status=order.status,
                total_cents=order.total_cents,
                item_count=sum(item.quantity for item in order.items),
                shipment_status=order.shipment.status if order.shipment else None,
                placed_at=order.placed_at,
                delivered_at=order.delivered_at,
            )
            for order in orders
        ],
        total=total,
    )
