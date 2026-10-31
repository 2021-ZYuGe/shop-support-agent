from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.base import UtcSerializationModel


class MetricSet(BaseModel):
    products: int
    orders: int
    knowledge_documents: int
    knowledge_chunks: int
    open_tickets: int
    messages: int


class RecentOrder(UtcSerializationModel):
    order_no: str
    customer_name: str
    status: str
    placed_at: datetime
    total_cents: int
    item_count: int
    shipment_status: str | None


class Capability(BaseModel):
    key: str
    label: str
    status: Literal["ready", "pending", "planned"]
    description: str


class DashboardResponse(UtcSerializationModel):
    metrics: MetricSet
    recent_orders: list[RecentOrder]
    capabilities: list[Capability]
    generated_at: datetime


class OrderListItem(UtcSerializationModel):
    order_no: str
    customer_name: str
    customer_phone: str
    status: str
    total_cents: int
    item_count: int
    shipment_status: str | None
    placed_at: datetime
    delivered_at: datetime | None


class OrderListResponse(BaseModel):
    items: list[OrderListItem]
    total: int
