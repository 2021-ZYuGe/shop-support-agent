import {
  ArrowLeft,
  BookOpenText,
  Bot,
  Clock3,
  MessageSquareText,
  ThumbsDown,
  ThumbsUp,
  TicketCheck,
  UserRound,
  Wrench,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ConversationStatusBadge, TicketStatusBadge } from "../components/OperationsBadges";
import { api, type AdminConversationDetail, type ChatMessage } from "../lib/api";
import { formatDateTime } from "../lib/format";

function MessageRecord({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <article className={`admin-message admin-message--${isUser ? "user" : "assistant"}`}>
      <div className="admin-message__avatar">
        {isUser ? <UserRound size={15} /> : <Bot size={15} />}
      </div>
      <div className="admin-message__body">
        <div className="admin-message__head">
          <strong>{isUser ? "顾客" : "AI 客服"}</strong>
          <span>{formatDateTime(message.created_at)}</span>
          {!isUser && message.model && <em>{message.model}</em>}
        </div>
        <div className="admin-message__content">{message.content}</div>
        {!isUser && (
          <div className="admin-message__metrics">
            <span>prompt {message.prompt_tokens}</span>
            <span>completion {message.completion_tokens}</span>
            <span>{message.latency_ms}ms</span>
          </div>
        )}
        {message.tool_trace && message.tool_trace.length > 0 && (
          <details className="admin-message__details">
            <summary>
              <Wrench size={13} /> 工具轨迹 · {message.tool_trace.length} 项
            </summary>
            {message.tool_trace.map((tool, index) => (
              <div className="admin-tool-row" key={`${tool.tool}-${index}`}>
                <span className={`admin-tool-row__status admin-tool-row__status--${tool.status}`}>
                  {tool.status === "success" ? <TicketCheck size={13} /> : <Clock3 size={13} />}
                </span>
                <div>
                  <strong>{tool.label}</strong>
                  <p>{tool.summary}</p>
                </div>
                <em>{tool.duration_ms}ms</em>
              </div>
            ))}
          </details>
        )}
        {message.citations && message.citations.length > 0 && (
          <details className="admin-message__details">
            <summary>
              <BookOpenText size={13} /> 知识引用 · {message.citations.length} 条
            </summary>
            {message.citations.map((source) => (
              <div className="admin-citation" key={`${message.id}-${source.chunk_id}`}>
                <strong>{source.title}</strong>
                <span>
                  {source.heading || "未命名章节"} · {Math.round(source.similarity * 100)}%
                </span>
                <p>{source.content}</p>
              </div>
            ))}
          </details>
        )}
        {message.feedback && (
          <div className="admin-feedback-note">
            {message.feedback.rating === 1 ? <ThumbsUp size={13} /> : <ThumbsDown size={13} />}
            <span>{message.feedback.rating === 1 ? "顾客反馈有帮助" : "顾客反馈没帮助"}</span>
            {message.feedback.comment && <em>“{message.feedback.comment}”</em>}
          </div>
        )}
      </div>
    </article>
  );
}

export function AdminConversationDetailPage() {
  const { publicId = "" } = useParams();
  const [data, setData] = useState<AdminConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.adminConversation(publicId));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "无法加载会话");
    } finally {
      setLoading(false);
    }
  }, [publicId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="admin-page">
        <div className="page-loader">
          <span className="screen-loader__pulse" />
          <p>读取会话详情…</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="admin-page">
        <div className="error-panel">
          <h2>会话无法打开</h2>
          <p>{error ?? "会话不存在"}</p>
          <Link className="button button--primary" to="/admin/conversations">
            返回会话中心
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <header className="admin-page__header">
        <div>
          <Link className="back-link back-link--dark" to="/admin/conversations">
            <ArrowLeft size={15} />
            返回会话中心
          </Link>
          <span className="eyebrow" style={{ marginTop: 14 }}>
            CONVERSATION · {data.channel.toUpperCase()}
          </span>
          <h1>会话 {data.public_id.slice(0, 12)}…</h1>
          <p>创建于 {formatDateTime(data.created_at)} · 最近更新 {formatDateTime(data.updated_at)}</p>
        </div>
        <ConversationStatusBadge status={data.status} />
      </header>

      <div className="conversation-detail">
        <section className="panel conversation-transcript">
          <div className="panel__header">
            <div>
              <span className="eyebrow">TRANSCRIPT</span>
              <h2>完整对话</h2>
            </div>
            <span className="panel__counter">{data.messages.length} 条消息</span>
          </div>
          {data.messages.length > 0 ? (
            <div className="transcript-list">
              {data.messages.map((message) => (
                <MessageRecord message={message} key={message.id} />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <MessageSquareText size={26} />
              <h3>还没有消息</h3>
            </div>
          )}
        </section>

        <aside className="conversation-side">
          <section className="panel">
            <div className="panel__header">
              <div>
                <span className="eyebrow">HANDOFF</span>
                <h2>人工工单</h2>
              </div>
              <span className="panel__counter">{data.tickets.length}</span>
            </div>
            {data.tickets.length > 0 ? (
              <div className="conversation-ticket-list">
                {data.tickets.map((ticket) => (
                  <article className="conversation-ticket" key={ticket.id}>
                    <div>
                      <strong>工单 #{ticket.id}</strong>
                      <TicketStatusBadge status={ticket.status} />
                    </div>
                    <p>{ticket.reason}</p>
                    <span>
                      负责人：{ticket.assigned_admin_name || "未分配"} · 更新{" "}
                      {formatDateTime(ticket.updated_at)}
                    </span>
                    {ticket.resolution_note && <em>{ticket.resolution_note}</em>}
                  </article>
                ))}
                <Link className="text-link" to="/admin/tickets">
                  进入工单队列
                </Link>
              </div>
            ) : (
              <p className="quiet-copy">这个会话没有人工工单。</p>
            )}
          </section>

          <section className="quiet-panel">
            <span className="eyebrow">SESSION NOTE</span>
            <h3>匿名会话</h3>
            <p>消费者无需登录。会话使用随机 public ID，不展示个人信息。</p>
          </section>
        </aside>
      </div>
    </div>
  );
}
