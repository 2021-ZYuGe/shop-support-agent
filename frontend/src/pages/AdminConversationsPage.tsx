import {
  ArrowRight,
  MessageSquareText,
  MessagesSquare,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
  TicketCheck,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ConversationStatusBadge } from "../components/OperationsBadges";
import { api, type AdminConversationList } from "../lib/api";
import { formatDateTime } from "../lib/format";

const filters = [
  { key: "all", label: "全部" },
  { key: "active", label: "AI 对话中" },
  { key: "handed_off", label: "已转人工" },
];

export function AdminConversationsPage() {
  const [data, setData] = useState<AdminConversationList | null>(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (refresh = false) => {
      if (refresh) setRefreshing(true);
      else setLoading(true);
      setError(null);
      try {
        setData(await api.adminConversations(filter === "all" ? undefined : filter));
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "无法加载会话");
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

  const totalNegative =
    data?.items.reduce((sum, item) => sum + item.negative_feedback, 0) ?? 0;
  const totalOpenTickets =
    data?.items.reduce((sum, item) => sum + item.open_ticket_count, 0) ?? 0;

  return (
    <div className="admin-page">
      <header className="admin-page__header">
        <div>
          <span className="eyebrow">CONVERSATION CENTER · M5</span>
          <h1>会话中心</h1>
          <p>查看 AI 与顾客的完整对话、工具轨迹、反馈和人工工单。</p>
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
        <article className="ops-stat">
          <MessagesSquare size={18} />
          <span>会话总数</span>
          <strong>{data?.total ?? 0}</strong>
        </article>
        <article className="ops-stat">
          <MessageSquareText size={18} />
          <span>AI 对话中</span>
          <strong>{data?.status_counts.active ?? 0}</strong>
        </article>
        <article className="ops-stat">
          <TicketCheck size={18} />
          <span>当前页待处理工单</span>
          <strong>{totalOpenTickets}</strong>
        </article>
        <article className="ops-stat ops-stat--rose">
          <ThumbsDown size={18} />
          <span>当前页负反馈</span>
          <strong>{totalNegative}</strong>
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
        <span className="ops-toolbar__hint">匿名会话，按最近更新时间排序</span>
      </div>

      {error && (
        <div className="inline-alert" role="alert">
          {error}
          <button className="text-button" type="button" onClick={() => void load()}>
            重试
          </button>
        </div>
      )}

      <section className="panel">
        {loading ? (
          <div className="page-loader page-loader--compact">
            <span className="screen-loader__pulse" />
            <p>读取会话…</p>
          </div>
        ) : data && data.items.length > 0 ? (
          <div className="table-wrap">
            <table className="data-table ops-table">
              <thead>
                <tr>
                  <th>会话</th>
                  <th>状态</th>
                  <th>消息</th>
                  <th>最近消息</th>
                  <th>工单 / 反馈</th>
                  <th>更新时间</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.items.map((conversation) => (
                  <tr key={conversation.public_id}>
                    <td>
                      <div className="session-cell">
                        <span className="session-cell__mark">CH</span>
                        <div>
                          <strong>{conversation.public_id.slice(0, 12)}…</strong>
                          <span>{conversation.channel}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <ConversationStatusBadge status={conversation.status} />
                    </td>
                    <td>{conversation.message_count}</td>
                    <td>
                      <span className="conversation-preview">
                        {conversation.last_message_preview ?? "暂无消息"}
                      </span>
                    </td>
                    <td>
                      <span className="conversation-meta">
                        <span>
                          <TicketCheck size={13} /> {conversation.open_ticket_count}
                        </span>
                        <span>
                          <ThumbsUp size={13} /> {conversation.positive_feedback}
                        </span>
                        <span>
                          <ThumbsDown size={13} /> {conversation.negative_feedback}
                        </span>
                      </span>
                    </td>
                    <td className="muted-cell">{formatDateTime(conversation.updated_at)}</td>
                    <td>
                      <Link
                        className="text-link"
                        to={`/admin/conversations/${conversation.public_id}`}
                      >
                        查看
                        <ArrowRight size={14} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <MessagesSquare size={28} />
            <h3>还没有会话</h3>
            <p>消费者发起对话后，会话会出现在这里。</p>
          </div>
        )}
      </section>
    </div>
  );
}
