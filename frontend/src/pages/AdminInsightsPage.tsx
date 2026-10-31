import {
  ArrowRight,
  BookX,
  Clock3,
  Coins,
  MessageSquareText,
  MessagesSquare,
  RefreshCw,
  ThumbsDown,
  TicketCheck,
  Wrench,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api, type InsightsResponse } from "../lib/api";
import { formatDateTime } from "../lib/format";

function number(value: number): string {
  return new Intl.NumberFormat("zh-CN").format(value);
}

export function AdminInsightsPage() {
  const [data, setData] = useState<InsightsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      setData(await api.adminInsights());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "无法加载运营洞察");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !data) {
    return (
      <div className="admin-page">
        <div className="page-loader">
          <span className="screen-loader__pulse" />
          <p>汇总运营数据…</p>
        </div>
      </div>
    );
  }

  const metrics = data?.metrics;

  return (
    <div className="admin-page">
      <header className="admin-page__header">
        <div>
          <span className="eyebrow">OPERATIONS INSIGHTS · M5</span>
          <h1>运营洞察</h1>
          <p>把会话、反馈、知识缺口、工具和成本放在同一个视角里。</p>
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

      {error && (
        <div className="inline-alert" role="alert">
          {error}
        </div>
      )}

      {metrics && (
        <>
          <section className="insights-metrics">
            <article className="insight-metric insight-metric--forest">
              <MessagesSquare size={18} />
              <span>总会话</span>
              <strong>{metrics.conversations_total}</strong>
              <small>{metrics.conversations_handed_off} 个已转人工</small>
            </article>
            <article className="insight-metric">
              <MessageSquareText size={18} />
              <span>消息</span>
              <strong>{number(metrics.messages_total)}</strong>
              <small>{number(metrics.assistant_messages)} 条助手消息</small>
            </article>
            <article className="insight-metric">
              <TicketCheck size={18} />
              <span>待处理工单</span>
              <strong>{metrics.tickets_open + metrics.tickets_in_progress}</strong>
              <small>{metrics.tickets_resolved} 个已关闭/解决</small>
            </article>
            <article className="insight-metric insight-metric--rose">
              <ThumbsDown size={18} />
              <span>负反馈</span>
              <strong>{metrics.feedback_negative}</strong>
              <small>{metrics.feedback_positive} 个正反馈</small>
            </article>
            <article className="insight-metric">
              <Coins size={18} />
              <span>估算成本</span>
              <strong>¥{metrics.estimated_cost_cny.toFixed(4)}</strong>
              <small>
                {number(metrics.prompt_tokens + metrics.completion_tokens)} tokens
              </small>
            </article>
            <article className="insight-metric">
              <Clock3 size={18} />
              <span>平均响应</span>
              <strong>{(metrics.avg_latency_ms / 1000).toFixed(2)}s</strong>
              <small>包含模型与工具总耗时</small>
            </article>
            <article className="insight-metric">
              <BookX size={18} />
              <span>知识缺口</span>
              <strong>{metrics.fallback_messages}</strong>
              <small>未命中知识库的回答</small>
            </article>
            <article className="insight-metric">
              <Wrench size={18} />
              <span>工具调用</span>
              <strong>{data?.tools.reduce((sum, tool) => sum + tool.count, 0) ?? 0}</strong>
              <small>{data?.tools.length ?? 0} 种业务工具</small>
            </article>
          </section>

          <div className="insights-grid">
            <section className="panel">
              <div className="panel__header">
                <div>
                  <span className="eyebrow">LOW FEEDBACK</span>
                  <h2>低分反馈</h2>
                </div>
                <Link className="text-link" to="/admin/conversations">
                  查看会话
                  <ArrowRight size={14} />
                </Link>
              </div>
              {data?.low_feedback.length ? (
                <div className="insight-list">
                  {data.low_feedback.map((item) => (
                    <article className="low-feedback" key={item.feedback_id}>
                      <div className="low-feedback__top">
                        <span className="ops-badge ops-badge--rose">没帮助</span>
                        <span className="muted-cell">{formatDateTime(item.created_at)}</span>
                      </div>
                      <p>{item.assistant_preview}</p>
                      {item.comment && <em>“{item.comment}”</em>}
                      <Link
                        className="text-link"
                        to={`/admin/conversations/${item.conversation_public_id}`}
                      >
                        回看会话 {item.conversation_public_id.slice(0, 8)}…
                      </Link>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="quiet-copy">暂时没有点踩反馈。</p>
              )}
            </section>

            <section className="panel">
              <div className="panel__header">
                <div>
                  <span className="eyebrow">TOOL MIX</span>
                  <h2>工具使用</h2>
                </div>
              </div>
              {data?.tools.length ? (
                <div className="tool-usage-list">
                  {data.tools.map((tool) => (
                    <div className="tool-usage" key={tool.tool_name}>
                      <div>
                        <strong>{tool.label}</strong>
                        <span>{tool.tool_name}</span>
                      </div>
                      <div>
                        <em>{tool.count} 次</em>
                        <small>{tool.avg_duration_ms.toFixed(0)}ms 平均</small>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="quiet-copy">还没有工具调用记录。</p>
              )}
            </section>

            <section className="panel insights-grid__wide">
              <div className="panel__header">
                <div>
                  <span className="eyebrow">KNOWLEDGE GAPS</span>
                  <h2>知识缺口</h2>
                </div>
                <Link className="text-link" to="/admin/knowledge">
                  查看知识库
                  <ArrowRight size={14} />
                </Link>
              </div>
              {data?.knowledge_gaps.length ? (
                <div className="gap-list">
                  {data.knowledge_gaps.map((gap, index) => (
                    <article className="gap-item" key={`${gap.conversation_public_id}-${index}`}>
                      <span className="gap-item__index">{String(index + 1).padStart(2, "0")}</span>
                      <div>
                        <strong>{gap.question}</strong>
                        <p>{gap.assistant_preview}</p>
                        <Link
                          className="text-link"
                          to={`/admin/conversations/${gap.conversation_public_id}`}
                        >
                          回看会话
                          <ArrowRight size={13} />
                        </Link>
                      </div>
                      <span className="muted-cell">{formatDateTime(gap.created_at)}</span>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="quiet-copy">暂时没有记录到知识缺口。</p>
              )}
            </section>
          </div>

          <p className="insights-footnote">
            成本按 `.env` 中的模型单价估算，仅用于学习与演示；实际费用以 DeepSeek 控制台为准。
            {data && ` 数据刷新于 ${formatDateTime(data.generated_at)}。`}
          </p>
        </>
      )}
    </div>
  );
}
