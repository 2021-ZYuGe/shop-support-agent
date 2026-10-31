from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.core import guardrails
from app.core.config import get_settings
from app.db.models import Conversation
from app.services import chat as chat_service
from app.services import knowledge
from app.services.tools import (
    ORDER_NO_RE,
    OrderToolkit,
    ToolError,
    extract_order_no,
    is_quality_issue,
)

logger = logging.getLogger(__name__)

HANDOFF_TERMS = ("转人工", "人工客服", "找人工", "真人客服", "人工处理", "投诉")
AFTER_SALES_TERMS = (
    "退货",
    "换货",
    "退款",
    "退换",
    "能退",
    "可以退",
    "质量问题",
    "坏了",
    "破损",
    "色差",
    "故障",
    "保修",
    "维修",
)
LOGISTICS_TERMS = (
    "物流",
    "快递",
    "包裹",
    "到哪",
    "运单",
    "签收",
    "配送",
    "运输",
    "什么时候到",
    "发货",
)
ORDER_TERMS = ("订单", "购买", "买的", "下单", "买了")

MISSING_ORDER_ANSWER = (
    "请提供订单号（例如 QH20261031007），我再帮你查询订单或物流状态。"
)

PRIORITY_LABELS = {"high": "高", "normal": "普通"}


@dataclass(frozen=True)
class AgentOptions:
    top_k: int = 5
    min_similarity: float = 0.40
    use_rerank: bool = False
    rerank_candidates: int = 12
    prompt_version: Literal["v1", "v2"] = "v1"

    @classmethod
    def from_settings(cls) -> AgentOptions:
        settings = get_settings()
        return cls(
            top_k=settings.rag_top_k,
            min_similarity=settings.rag_min_similarity,
            use_rerank=settings.rag_use_rerank,
            rerank_candidates=settings.rag_rerank_candidates,
            prompt_version=(
                "v2" if settings.chat_prompt_version.lower() == "v2" else "v1"
            ),
        )


class AgentState(TypedDict, total=False):
    query: str
    history: list[dict[str, str]]
    options: AgentOptions
    toolkit: Any
    intent: str
    order_no: str | None
    issue_type: str
    order_data: dict[str, Any] | None
    shipment_data: dict[str, Any] | None
    eligibility: dict[str, Any] | None
    handoff: dict[str, Any] | None
    sources: list[dict[str, Any]]
    tool_error: str | None
    mode: str
    direct_answer: str | None
    llm_messages: list[dict[str, str]] | None


@dataclass(frozen=True)
class AgentOutcome:
    intent: str
    mode: str
    sources: list[dict[str, Any]]
    tool_trace: list[dict[str, Any]]
    llm_messages: list[dict[str, str]] | None
    direct_answer: str | None


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _history_user_text(history: list[dict[str, str]]) -> str:
    return "\n".join(
        message["content"] for message in history if message.get("role") == "user"
    )


def _looks_like_order_only(query: str) -> bool:
    stripped = ORDER_NO_RE.sub("", query)
    stripped = stripped.strip(" \t\r\n，。！？!?,.、")
    return len(stripped) <= 2


def classify_intent(
    query: str,
    history: list[dict[str, str]],
) -> tuple[str, str | None, str]:
    current = query.lower()
    prior = _history_user_text(history).lower()
    order_no = extract_order_no(query, prior)
    issue_type = "quality" if is_quality_issue(f"{query} {prior}") else "no_reason"

    if _has_any(current, HANDOFF_TERMS):
        return "handoff", order_no, issue_type
    if _has_any(current, AFTER_SALES_TERMS):
        return "after_sales", order_no, issue_type

    current_logistics = _has_any(current, LOGISTICS_TERMS)
    current_order = _has_any(current, ORDER_TERMS)
    prior_after = _has_any(prior, AFTER_SALES_TERMS)
    prior_logistics = _has_any(prior, LOGISTICS_TERMS)

    if order_no:
        if current_logistics:
            return "logistics", order_no, issue_type
        if _looks_like_order_only(query):
            if prior_after:
                return "after_sales", order_no, issue_type
            if prior_logistics:
                return "logistics", order_no, issue_type
            return "order", order_no, issue_type
        if current_order:
            return "order", order_no, issue_type
        if prior_after:
            return "after_sales", order_no, issue_type
        if prior_logistics:
            return "logistics", order_no, issue_type
        return "order", order_no, issue_type

    if current_logistics or current_order:
        return "missing_order", None, issue_type

    return "knowledge", None, issue_type


def _route_intent(state: AgentState) -> dict[str, Any]:
    if guardrails.looks_like_prompt_injection(state["query"]):
        logger.info("Agent blocked a prompt-injection attempt")
        return {"intent": "guard", "order_no": None, "issue_type": "no_reason"}

    intent, order_no, issue_type = classify_intent(
        state["query"],
        state.get("history", []),
    )
    logger.info("Agent intent routed: intent=%s order_no=%s", intent, order_no)
    return {
        "intent": intent,
        "order_no": order_no,
        "issue_type": issue_type,
    }


def _lookup_order(state: AgentState) -> dict[str, Any]:
    toolkit: OrderToolkit = state["toolkit"]
    try:
        return {"order_data": toolkit.lookup_order(state["order_no"] or "")}
    except ToolError as exc:
        return {"tool_error": str(exc)}


def _lookup_shipment(state: AgentState) -> dict[str, Any]:
    toolkit: OrderToolkit = state["toolkit"]
    try:
        return {"shipment_data": toolkit.lookup_shipment(state["order_no"] or "")}
    except ToolError as exc:
        return {"tool_error": str(exc)}


def _check_after_sales(state: AgentState) -> dict[str, Any]:
    order_no = state.get("order_no")
    if not order_no:
        return {}
    toolkit: OrderToolkit = state["toolkit"]
    try:
        return {
            "eligibility": toolkit.check_after_sales(
                order_no,
                state.get("issue_type", "no_reason"),
            )
        }
    except ToolError as exc:
        return {"tool_error": str(exc)}


def _create_handoff(state: AgentState) -> dict[str, Any]:
    toolkit: OrderToolkit = state["toolkit"]
    query = state["query"]
    order_no = state.get("order_no")
    summary = f"用户请求人工协助。\n问题：{query}"
    if order_no:
        summary += f"\n关联订单：{order_no}"
    try:
        handoff = toolkit.create_handoff(
            reason=query[:255],
            summary=summary,
            order_no=order_no,
        )
        return {"handoff": handoff}
    except ToolError as exc:
        return {"tool_error": str(exc)}


def _retrieve_knowledge(state: AgentState) -> dict[str, Any]:
    toolkit: OrderToolkit = state["toolkit"]
    options = state.get("options") or AgentOptions.from_settings()
    sources = knowledge.search_knowledge(
        toolkit.db,
        state["query"],
        top_k=options.top_k,
        min_similarity=options.min_similarity,
        use_rerank=options.use_rerank,
        candidate_k=options.rerank_candidates,
    )
    return {"sources": sources}


def _format_tool_context(state: AgentState) -> str:
    lines: list[str] = []
    order = state.get("order_data")
    if order:
        items = "、".join(
            f"{item['name']}×{item['quantity']}" for item in order.get("items", [])
        )
        lines.append(
            f"订单 {order['order_no']}：状态 {order['status_label']}；"
            f"商品 {items or '无'}；下单时间 {order.get('placed_at') or '未知'}；"
            f"签收时间 {order.get('delivered_at') or '未签收'}。"
        )
        shipment = order.get("shipment")
        if shipment:
            lines.append(
                f"物流：{shipment['status_label']}，最新动态：{shipment['latest_event']}"
            )
        else:
            lines.append("物流：暂无物流信息。")

    shipment_data = state.get("shipment_data")
    if shipment_data:
        shipment = shipment_data.get("shipment")
        if shipment:
            lines.append(
                f"订单 {shipment_data['order_no']} 物流：{shipment['carrier']}，"
                f"运单号 {shipment['tracking_no']}，状态 {shipment['status_label']}，"
                f"最新动态：{shipment['latest_event']}，预计送达："
                f"{shipment.get('estimated_delivery_date') or '未提供'}。"
            )
        else:
            lines.append(
                f"订单 {shipment_data['order_no']} 暂无物流信息，"
                f"订单状态：{shipment_data.get('order_status_label', '未知')}。"
            )

    eligibility = state.get("eligibility")
    if eligibility:
        lines.append(
            f"售后条件判断：{'符合申请条件' if eligibility['eligible'] else '暂不符合条件'}；"
            f"{eligibility['reason']}；{eligibility.get('note', '')}"
        )

    if state.get("tool_error"):
        lines.append(f"工具错误：{state['tool_error']}")

    return "\n".join(lines)


def _compose_answer(state: AgentState) -> dict[str, Any]:
    toolkit: OrderToolkit = state["toolkit"]
    trace = toolkit.trace
    intent = state.get("intent", "knowledge")
    sources = state.get("sources", [])
    history = state.get("history", [])
    query = state["query"]
    options = state.get("options") or AgentOptions.from_settings()

    if intent == "guard":
        return {"mode": "fallback", "direct_answer": guardrails.GUARD_ANSWER}

    if intent == "handoff":
        handoff = state.get("handoff")
        if handoff:
            if handoff.get("existing"):
                message = (
                    f"这个会话已经有一个待处理的人工工单 #{handoff['ticket_id']}，"
                    "客服会在服务时间内接手。你也可以继续补充订单号或问题细节。"
                )
            else:
                priority = PRIORITY_LABELS.get(handoff.get("priority"), "普通")
                message = (
                    f"已为你创建人工工单 #{handoff['ticket_id']}，"
                    f"当前状态：待处理，优先级：{priority}。"
                    "客服会在服务时间内接手，你也可以继续补充问题细节。"
                )
            return {
                "mode": "handoff",
                "direct_answer": message,
            }
        return {
            "mode": "clarify",
            "direct_answer": state.get("tool_error")
            or "人工工单暂时无法创建，请稍后再试。",
        }

    if intent == "missing_order":
        return {
            "mode": "clarify",
            "direct_answer": MISSING_ORDER_ANSWER,
        }

    if state.get("tool_error"):
        return {
            "mode": "clarify",
            "direct_answer": (
                state["tool_error"]
                + " 如果你确认订单号无误，也可以转人工客服进一步核实。"
            ),
        }

    if intent in {"order", "logistics"}:
        tool_context = _format_tool_context(state)
        if not tool_context:
            return {"mode": "fallback", "direct_answer": chat_service.FALLBACK_ANSWER}
        messages = chat_service.build_llm_messages(
            history,
            [],
            query,
            tool_context=tool_context,
            instruction=(
                "请基于业务系统查询结果回答，不要编造未提供的订单或物流数据。"
                "涉及退款、修改地址或赔付时只能说明边界，并建议转人工。"
            ),
            prompt_version=options.prompt_version,
        )
        return {"mode": "agent", "llm_messages": messages}

    if intent == "after_sales":
        if state.get("eligibility"):
            tool_context = _format_tool_context(state)
            messages = chat_service.build_llm_messages(
                history,
                sources,
                query,
                tool_context=tool_context,
                instruction=(
                    "请结合售后政策与条件判断结果回答。明确这是辅助判断，不执行真实退款；"
                    "如需实际退货或争议处理，建议用户转人工工单。"
                ),
                prompt_version=options.prompt_version,
            )
            return {"mode": "agent", "llm_messages": messages}
        if sources:
            messages = chat_service.build_llm_messages(
                history,
                sources,
                query,
                instruction=(
                    "用户尚未提供订单号，无法做具体订单的售后资格判断。"
                    "请解释通用售后政策，并请用户提供订单号以便进一步核实。"
                ),
                prompt_version=options.prompt_version,
            )
            return {"mode": "rag", "llm_messages": messages}
        return {"mode": "fallback", "direct_answer": chat_service.FALLBACK_ANSWER}

    if sources:
        messages = chat_service.build_llm_messages(
            history,
            sources,
            query,
            prompt_version=options.prompt_version,
        )
        return {"mode": "rag", "llm_messages": messages}

    return {"mode": "fallback", "direct_answer": chat_service.FALLBACK_ANSWER}


def _next_node(state: AgentState) -> str:
    return {
        "order": "order_lookup",
        "logistics": "logistics_lookup",
        "after_sales": "after_sales_lookup",
        "handoff": "handoff",
        "guard": "compose",
        "missing_order": "compose",
        "knowledge": "retrieve",
    }.get(state.get("intent", "knowledge"), "retrieve")


def _build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("router", _route_intent)
    builder.add_node("order_lookup", _lookup_order)
    builder.add_node("logistics_lookup", _lookup_shipment)
    builder.add_node("after_sales_lookup", _check_after_sales)
    builder.add_node("handoff", _create_handoff)
    builder.add_node("retrieve", _retrieve_knowledge)
    builder.add_node("compose", _compose_answer)

    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        _next_node,
        {
            "order_lookup": "order_lookup",
            "logistics_lookup": "logistics_lookup",
            "after_sales_lookup": "after_sales_lookup",
            "handoff": "handoff",
            "compose": "compose",
            "retrieve": "retrieve",
        },
    )
    builder.add_edge("order_lookup", "compose")
    builder.add_edge("logistics_lookup", "compose")
    builder.add_edge("after_sales_lookup", "retrieve")
    builder.add_edge("retrieve", "compose")
    builder.add_edge("handoff", "compose")
    builder.add_edge("compose", END)
    return builder.compile()


agent_graph = _build_graph()


def run_agent(
    db: Session,
    conversation: Conversation,
    history: list[dict[str, str]],
    query: str,
    options: AgentOptions | None = None,
    persist: bool = True,
) -> AgentOutcome:
    toolkit = OrderToolkit(db, conversation)
    resolved_options = options or AgentOptions.from_settings()
    initial_state: AgentState = {
        "query": query,
        "history": history,
        "options": resolved_options,
        "toolkit": toolkit,
        "sources": [],
    }

    try:
        result = agent_graph.invoke(initial_state)
        outcome = AgentOutcome(
            intent=result.get("intent", "knowledge"),
            mode=result.get("mode", "fallback"),
            sources=result.get("sources", []),
            tool_trace=list(result.get("toolkit", toolkit).trace),
            llm_messages=result.get("llm_messages"),
            direct_answer=result.get("direct_answer"),
        )
        if persist:
            db.commit()
        else:
            db.rollback()
        return outcome
    except Exception:
        db.rollback()
        raise
