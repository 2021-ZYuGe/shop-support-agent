from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session, object_session, selectinload

from app.core.config import Settings, get_settings
from app.db.base import utcnow
from app.db.models import Conversation, HandoffTicket, Order, ToolCallLog

logger = logging.getLogger(__name__)

ORDER_NO_RE = re.compile(r"\b(QH\d{8,})\b", re.IGNORECASE)

ORDER_STATUS_LABELS = {
    "paid": "待发货",
    "shipped": "运输中",
    "delivered": "已签收",
    "completed": "已完成",
    "cancelled": "已取消",
    "refunding": "售后处理中",
}

SHIPMENT_STATUS_LABELS = {
    "pending": "待揽收",
    "in_transit": "在途",
    "delivered": "已签收",
}

QUALITY_TERMS = ("质量问题", "坏了", "破损", "色差", "故障", "瑕疵", "划痕")
HIGH_PRIORITY_TERMS = ("投诉", "退款", "赔付", "质量问题", "破损")


class ToolError(RuntimeError):
    """A validated business tool failed."""


def extract_order_no(*texts: str) -> str | None:
    for value in reversed(texts):
        matches = ORDER_NO_RE.findall(value or "")
        if matches:
            return matches[-1].upper()
    return None


def is_quality_issue(text: str) -> bool:
    return any(term in text for term in QUALITY_TERMS)


def mask_tracking_no(value: str) -> str:
    if len(value) <= 8:
        return value
    return f"{value[:4]}****{value[-4:]}"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class OrderToolkit:
    """Business tools with validation, audit and per-turn call limits."""

    def __init__(
        self,
        db: Session,
        conversation: Conversation,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        if object_session(conversation) is not db:
            conversation = db.get(Conversation, conversation.id) or conversation
        self.conversation = conversation
        self.settings = settings or get_settings()
        self.calls = 0
        self.trace: list[dict[str, Any]] = []
        self._configure_timeout()

    def _configure_timeout(self) -> None:
        try:
            bind = self.db.get_bind()
            if bind is not None and bind.dialect.name == "mysql":
                # MySQL 5.7 supports max_execution_time for SELECT statements.
                timeout = max(100, int(self.settings.tool_timeout_ms))
                self.db.execute(text(f"SET SESSION max_execution_time = {timeout}"))
        except Exception:
            logger.warning("Could not configure MySQL tool query timeout", exc_info=False)

    def _begin(self, label: str) -> float:
        if self.calls >= self.settings.max_tool_calls_per_turn:
            raise ToolError("本轮工具调用次数已达上限，请简化问题后重试。")
        self.calls += 1
        logger.info("Tool started: %s", label)
        return time.perf_counter()

    def _record(
        self,
        *,
        tool: str,
        label: str,
        arguments: dict[str, Any],
        status: str,
        summary: str,
        started_at: float,
        result_summary: dict[str, Any] | None = None,
    ) -> None:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        self.db.add(
            ToolCallLog(
                conversation_id=self.conversation.id,
                tool_name=tool,
                arguments=arguments,
                result_summary=result_summary or {},
                status=status,
                duration_ms=duration_ms,
            )
        )
        self.trace.append(
            {
                "tool": tool,
                "label": label,
                "status": status,
                "summary": summary[:255],
                "duration_ms": duration_ms,
            }
        )

    @staticmethod
    def _validate_order_no(order_no: str) -> str:
        normalized = order_no.strip().upper()
        if not ORDER_NO_RE.fullmatch(normalized):
            raise ToolError("订单号格式不正确，请提供类似 QH20261031007 的订单号。")
        return normalized

    def _find_order(self, order_no: str) -> Order:
        order = self.db.scalar(
            select(Order)
            .options(selectinload(Order.items), selectinload(Order.shipment))
            .where(Order.order_no == order_no)
        )
        if order is None:
            raise ToolError(f"没有找到订单 {order_no}，请核对后重试。")
        return order

    def lookup_order(self, order_no: str) -> dict[str, Any]:
        started = self._begin("订单查询")
        args = {"order_no": order_no}
        try:
            normalized = self._validate_order_no(order_no)
            order = self._find_order(normalized)
            item_count = sum(item.quantity for item in order.items)
            shipment = order.shipment
            data = {
                "order_no": order.order_no,
                "status": order.status,
                "status_label": ORDER_STATUS_LABELS.get(order.status, order.status),
                "item_count": item_count,
                "items": [
                    {
                        "name": item.product_name_snapshot,
                        "quantity": item.quantity,
                    }
                    for item in order.items
                ],
                "total_yuan": f"{order.total_cents / 100:.2f}",
                "placed_at": _iso(order.placed_at),
                "delivered_at": _iso(order.delivered_at),
                "shipment": (
                    {
                        "status": shipment.status,
                        "status_label": SHIPMENT_STATUS_LABELS.get(
                            shipment.status, shipment.status
                        ),
                        "latest_event": shipment.latest_event,
                    }
                    if shipment
                    else None
                ),
            }
            summary = f"订单 {order.order_no} 当前状态：{data['status_label']}，共 {item_count} 件商品。"
            if shipment:
                summary += f" 物流状态：{data['shipment']['status_label']}。"
            self._record(
                tool="lookup_order",
                label="订单查询",
                arguments=args,
                status="success",
                summary=summary,
                started_at=started,
                result_summary={
                    "order_no": order.order_no,
                    "status": order.status,
                    "item_count": item_count,
                },
            )
            return data
        except ToolError as exc:
            self._record(
                tool="lookup_order",
                label="订单查询",
                arguments=args,
                status="error",
                summary=str(exc),
                started_at=started,
                result_summary={"error": exc.__class__.__name__},
            )
            raise

    def lookup_shipment(self, order_no: str) -> dict[str, Any]:
        started = self._begin("物流查询")
        args = {"order_no": order_no}
        try:
            normalized = self._validate_order_no(order_no)
            order = self._find_order(normalized)
            shipment = order.shipment
            if shipment is None:
                data = {
                    "order_no": order.order_no,
                    "order_status": order.status,
                    "order_status_label": ORDER_STATUS_LABELS.get(
                        order.status, order.status
                    ),
                    "shipment": None,
                }
                summary = (
                    f"订单 {order.order_no} 暂无物流信息，"
                    f"当前订单状态：{data['order_status_label']}。"
                )
            else:
                data = {
                    "order_no": order.order_no,
                    "order_status": order.status,
                    "order_status_label": ORDER_STATUS_LABELS.get(
                        order.status, order.status
                    ),
                    "shipment": {
                        "carrier": shipment.carrier,
                        "tracking_no": mask_tracking_no(shipment.tracking_no),
                        "status": shipment.status,
                        "status_label": SHIPMENT_STATUS_LABELS.get(
                            shipment.status, shipment.status
                        ),
                        "latest_event": shipment.latest_event,
                        "estimated_delivery_date": (
                            shipment.estimated_delivery_date.isoformat()
                            if shipment.estimated_delivery_date
                            else None
                        ),
                    },
                }
                summary = (
                    f"订单 {order.order_no} 当前物流状态："
                    f"{data['shipment']['status_label']}，"
                    f"最新动态：{shipment.latest_event[:120]}。"
                )
            self._record(
                tool="lookup_shipment",
                label="物流查询",
                arguments=args,
                status="success",
                summary=summary,
                started_at=started,
                result_summary={
                    "order_no": order.order_no,
                    "shipment_status": data["shipment"]["status"]
                    if data["shipment"]
                    else None,
                },
            )
            return data
        except ToolError as exc:
            self._record(
                tool="lookup_shipment",
                label="物流查询",
                arguments=args,
                status="error",
                summary=str(exc),
                started_at=started,
                result_summary={"error": exc.__class__.__name__},
            )
            raise

    def check_after_sales(self, order_no: str, issue_type: str) -> dict[str, Any]:
        started = self._begin("售后条件判断")
        args = {"order_no": order_no, "issue_type": issue_type}
        try:
            normalized = self._validate_order_no(order_no)
            order = self._find_order(normalized)
            if order.status == "cancelled":
                data = {
                    "order_no": order.order_no,
                    "eligible": False,
                    "reason_code": "cancelled",
                    "reason": "订单已取消，不能申请退货或换货。",
                    "requires_quality_evidence": False,
                }
            elif order.delivered_at is None or order.status not in {"delivered", "completed"}:
                data = {
                    "order_no": order.order_no,
                    "eligible": False,
                    "reason_code": "not_delivered",
                    "reason": "订单尚未签收，签收后才可以申请退货或换货。",
                    "requires_quality_evidence": issue_type == "quality",
                }
            else:
                days_since_delivery = max(0, (utcnow() - order.delivered_at).days)
                is_quality = issue_type == "quality"
                window_days = 15 if is_quality else 7
                eligible = days_since_delivery <= window_days
                data = {
                    "order_no": order.order_no,
                    "eligible": eligible,
                    "reason_code": "eligible" if eligible else "outside_window",
                    "reason": (
                        f"签收后第 {days_since_delivery} 天，"
                        + (
                            f"在质量问题 {window_days} 天受理范围内。"
                            if is_quality and eligible
                            else f"已超过质量问题 {window_days} 天受理范围。"
                            if is_quality
                            else f"在七天无理由退货范围内，需保持商品完好、不影响二次销售。"
                            if eligible
                            else "已超过签收后七天无理由退货范围。"
                        )
                    ),
                    "days_since_delivery": days_since_delivery,
                    "window_days": window_days,
                    "issue_type": issue_type,
                    "requires_quality_evidence": is_quality,
                    "note": "这只是条件判断，不执行退款或修改订单；需要人工工单处理实际退货。",
                }
            summary = (
                f"订单 {order.order_no} 售后判断："
                f"{'符合' if data['eligible'] else '暂不符合'}申请条件。"
            )
            self._record(
                tool="check_after_sales",
                label="售后条件判断",
                arguments=args,
                status="success",
                summary=summary,
                started_at=started,
                result_summary={
                    "order_no": order.order_no,
                    "eligible": data["eligible"],
                    "reason_code": data["reason_code"],
                },
            )
            return data
        except ToolError as exc:
            self._record(
                tool="check_after_sales",
                label="售后条件判断",
                arguments=args,
                status="error",
                summary=str(exc),
                started_at=started,
                result_summary={"error": exc.__class__.__name__},
            )
            raise

    def create_handoff(
        self,
        *,
        reason: str,
        summary: str,
        order_no: str | None = None,
    ) -> dict[str, Any]:
        started = self._begin("人工工单")
        args = {"order_no": order_no} if order_no else {}
        try:
            existing = self.db.scalar(
                select(HandoffTicket)
                .where(
                    HandoffTicket.conversation_id == self.conversation.id,
                    HandoffTicket.status == "open",
                )
                .order_by(HandoffTicket.id.desc())
                .limit(1)
            )
            if existing is not None:
                self.conversation.status = "handed_off"
                data = {
                    "ticket_id": existing.id,
                    "status": existing.status,
                    "priority": existing.priority,
                    "existing": True,
                }
                result_summary = {
                    "ticket_id": existing.id,
                    "status": existing.status,
                    "priority": existing.priority,
                }
                summary_text = f"该会话已有待处理人工工单 #{existing.id}。"
            else:
                priority = (
                    "high"
                    if any(term in f"{reason} {summary}" for term in HIGH_PRIORITY_TERMS)
                    else "normal"
                )
                ticket = HandoffTicket(
                    conversation_id=self.conversation.id,
                    reason=reason.strip()[:255] or "用户请求人工协助",
                    summary=summary.strip()[:2000] or "用户请求人工客服协助处理。",
                    status="open",
                    priority=priority,
                )
                self.db.add(ticket)
                self.db.flush()
                self.conversation.status = "handed_off"
                data = {
                    "ticket_id": ticket.id,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "existing": False,
                }
                result_summary = {
                    "ticket_id": ticket.id,
                    "status": ticket.status,
                    "priority": ticket.priority,
                }
                summary_text = f"已创建人工工单 #{ticket.id}，优先级：{priority}。"

            self._record(
                tool="create_handoff",
                label="人工工单",
                arguments=args,
                status="success",
                summary=summary_text,
                started_at=started,
                result_summary=result_summary,
            )
            return data
        except Exception as exc:
            self._record(
                tool="create_handoff",
                label="人工工单",
                arguments=args,
                status="error",
                summary="人工工单创建失败。",
                started_at=started,
                result_summary={"error": exc.__class__.__name__},
            )
            raise ToolError("人工工单暂时无法创建，请稍后再试。") from exc
