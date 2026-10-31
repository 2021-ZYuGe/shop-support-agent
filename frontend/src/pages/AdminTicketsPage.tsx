import {
  ArrowRight,
  CheckCircle2,
  CircleDot,
  Clock3,
  MessageSquareText,
  RefreshCw,
  Save,
  TicketCheck,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { TicketPriorityBadge, TicketStatusBadge } from "../components/OperationsBadges";
import { api, type AdminTicketList, type AdminTicketSummary } from "../lib/api";
import { formatDateTime } from "../lib/format";

const filters = [
  { key: "all", label: "全部" },
  { key: "open", label: "待处理" },
  { key: "in_progress", label: "处理中" },
  { key: "resolved", label: "已解决" },
  { key: "closed", label: "已关闭" },
];

const statusOptions = [
  { value: "open", label: "待处理" },
  { value: "in_progress", label: "处理中" },
  { value: "resolved", label: "已解决" },
  { value: "closed", label: "已关闭" },
];

const priorityOptions = [
  { value: "low", label: "低" },
  { value: "normal", label: "普通" },
  { value: "high", label: "高" },
];

export function AdminTicketsPage() {
  const [data, setData] = useState<AdminTicketList | null>(null);
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [statusValue, setStatusValue] = useState("open");
  const [priorityValue, setPriorityValue] = useState("normal");
  const [note, setNote] = useState("");

  const selected = data?.items.find((ticket) => ticket.id === selectedId) ?? null;

  const load = useCallback(
    async (refresh = false) => {
      if (refresh) setRefreshing(true);
      else setLoading(true);
      setError(null);
      try {
        setData(await api.adminTickets(filter === "all" ? undefined : filter));
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "无法加载工单");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [filter],
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!data) return;
    if (data.items.length === 0) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !data.items.some((ticket) => ticket.id === selectedId)) {
      setSelectedId(data.items[0].id);
    }
  }, [data, selectedId]);

  useEffect(() => {
    if (!selected) return;
    setStatusValue(selected.status);
    setPriorityValue(selected.priority);
    setNote(selected.resolution_note ?? "");
    setFeedback(null);
  }, [selectedId, selected?.status, selected?.priority, selected?.resolution_note]);

  const selectTicket = (ticket: AdminTicketSummary) => {
    setSelectedId(ticket.id);
    setFeedback(null);
  };

  const saveTicket = async () => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    setFeedback(null);
    try {
      const updated = await api.updateTicket(selected.id, {
        status: statusValue,
        priority: priorityValue,
        resolution_note: note,
        assign_to_me: true,
      });
      setFeedback(`工单 #${updated.id} 已更新为「${statusValue === "resolved" ? "已解决" : statusValue === "closed" ? "已关闭" : statusValue === "in_progress" ? "处理中" : "待处理"}」。`);
      await load(true);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "工单更新失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="admin-page">
      <header className="admin-page__header">
        <div>
          <span className="eyebrow">HANDOFF QUEUE · M5</span>
          <h1>工单队列</h1>
          <p>接手 Agent 无法完整处理的问题，记录处理状态和最终结论。</p>
        </div>
        <button
          className="button button--ghost button--small"
          type="button"
          onClick={() => void load(true)}
          disabled={refreshing}
        >
          <RefreshCw size={15} className={refreshing ? "is-spinning" : ""} />
          {refreshing ? "刷新中" : "刷新"}
        </button>
      </header>

      <section className="ops-stats">
        <article className="ops-stat ops-stat--amber">
          <TicketCheck size={18} />
          <span>待处理</span>
          <strong>{data?.status_counts.open ?? 0}</strong>
        </article>
        <article className="ops-stat">
          <Clock3 size={18} />
          <span>处理中</span>
          <strong>{data?.status_counts.in_progress ?? 0}</strong>
        </article>
        <article className="ops-stat ops-stat--green">
          <CheckCircle2 size={18} />
          <span>已解决</span>
          <strong>{data?.status_counts.resolved ?? 0}</strong>
        </article>
        <article className="ops-stat ops-stat--muted">
          <CircleDot size={18} />
          <span>已关闭</span>
          <strong>{data?.status_counts.closed ?? 0}</strong>
        </article>
      </section>

      <div className="ops-toolbar">
        <div className="filter-tabs">
          {filters.map((item) => (
            <button
              key={item.key}
              type="button"
              className={filter === item.key ? "is-active" : ""}
              onClick={() => setFilter(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <span className="ops-toolbar__hint">点击工单后可在右侧处理</span>
      </div>

      {error && (
        <div className="inline-alert" role="alert">
          {error}
        </div>
      )}
      {feedback && <div className="feedback-banner feedback-banner--success">{feedback}</div>}

      {loading ? (
        <div className="page-loader">
          <span className="screen-loader__pulse" />
          <p>读取工单…</p>
        </div>
      ) : (
        <div className="ticket-workspace">
          <section className="panel ticket-list-panel">
            <div className="panel__header">
              <div>
                <span className="eyebrow">TICKETS</span>
                <h2>待办工单</h2>
              </div>
              <span className="panel__counter">{data?.total ?? 0}</span>
            </div>
            {data && data.items.length > 0 ? (
              <div className="ticket-list">
                {data.items.map((ticket) => (
                  <button
                    type="button"
                    key={ticket.id}
                    className={`ticket-row ${ticket.id === selectedId ? "is-selected" : ""}`}
                    onClick={() => selectTicket(ticket)}
                  >
                    <div className="ticket-row__top">
                      <strong>工单 #{ticket.id}</strong>
                      <TicketStatusBadge status={ticket.status} />
                    </div>
                    <p>{ticket.reason}</p>
                    <div className="ticket-row__meta">
                      <TicketPriorityBadge priority={ticket.priority} />
                      <span>
                        <MessageSquareText size={12} /> 会话 {ticket.conversation_public_id.slice(0, 8)}…
                      </span>
                      <span>{formatDateTime(ticket.updated_at)}</span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <TicketCheck size={28} />
                <h3>当前没有匹配工单</h3>
                <p>Agent 创建人工工单后会出现在这里。</p>
              </div>
            )}
          </section>

          <section className="panel ticket-detail-panel">
            {selected ? (
              <>
                <div className="ticket-detail__heading">
                  <div>
                    <span className="eyebrow">TICKET DETAILS</span>
                    <h2>工单 #{selected.id}</h2>
                  </div>
                  <TicketStatusBadge status={selected.status} />
                </div>
                <p className="ticket-detail__reason">{selected.reason}</p>
                <div className="ticket-detail__summary">
                  <span>会话摘要</span>
                  <p>{selected.summary}</p>
                </div>
                <div className="ticket-detail__meta">
                  <span>负责人：{selected.assigned_admin_name || "未分配"}</span>
                  <span>创建：{formatDateTime(selected.created_at)}</span>
                  <Link
                    className="text-link"
                    to={`/admin/conversations/${selected.conversation_public_id}`}
                  >
                    查看会话
                    <ArrowRight size={14} />
                  </Link>
                </div>

                <div className="ticket-form">
                  <div className="form-grid">
                    <label className="field">
                      <span>工单状态</span>
                      <select value={statusValue} onChange={(event) => setStatusValue(event.target.value)}>
                        {statusOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span>优先级</span>
                      <select
                        value={priorityValue}
                        onChange={(event) => setPriorityValue(event.target.value)}
                      >
                        {priorityOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <label className="field">
                    <span>处理结论 / 备注</span>
                    <textarea
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      placeholder="例如：已联系用户补充照片，进入退货流程。"
                      maxLength={2000}
                      rows={4}
                    />
                  </label>
                  <button
                    className="button button--primary button--full"
                    type="button"
                    onClick={() => void saveTicket()}
                    disabled={saving}
                  >
                    <Save size={15} />
                    {saving ? "保存中…" : "保存处理结果"}
                  </button>
                  <p className="ticket-form__note">
                    保存后工单会分配给当前管理员，状态和备注会写入 MySQL。
                  </p>
                </div>
              </>
            ) : (
              <div className="empty-state">
                <MessageSquareText size={28} />
                <h3>选择一张工单</h3>
                <p>从左侧列表选择工单进行处理。</p>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
