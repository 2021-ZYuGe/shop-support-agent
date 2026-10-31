from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentAdmin, DbSession
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
def overview(_: CurrentAdmin, db: DbSession) -> DashboardResponse:
    metrics = MetricSet(
        products=_count(db, Product),
        orders=_count(db, Order),
        knowledge_documents=_count(db, KnowledgeDocument),
        knowledge_chunks=_count(db, KnowledgeChunk),
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
            status="pending",
            description="M2 将接入硅基流动 BGE-M3 与 Chroma 检索。",
        ),
        Capability(
            key="ai_chat",
            label="RAG 问答",
            status="planned",
            description="M3 将接入 DeepSeek 流式回答与引用。",
        ),
        Capability(
            key="agent_tools",
            label="Agent 业务工具",
            status="planned",
            description="M4 将接入订单、物流、售后判断与人工转接。",
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
