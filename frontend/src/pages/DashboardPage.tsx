import {
  ArrowRight,
  BookOpenText,
  Boxes,
  CheckCircle2,
  CircleDashed,
  Clock3,
  Database,
  Package,
  RefreshCw,
  TicketCheck,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { api, type DashboardResponse } from "../lib/api";
import { formatDateTime, formatMoney } from "../lib/format";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 11) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

const capabilityLabels = {
  ready: "已完成",
  pending: "下一步",
  planned: "计划中",
};

export function DashboardPage() {
  const { admin } = useAuth();
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      setData(await api.dashboard());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "无法加载运营数据");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const dateLabel = new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(new Date());

  if (loading && !data) {
    return (
      <div className="admin-page">
        <div className="page-loader">
          <span className="screen-loader__pulse" />
          <p>正在汇总店铺数据…</p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="admin-page">
        <div className="error-panel">
          <h2>运营数据暂时不可用</h2>
          <p>{error}</p>
          <button className="button button--primary" type="button" onClick={() => void load()}>
            重新加载
          </button>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const readyCount = data.capabilities.filter((item) => item.status === "ready").length;

  return (
    <div className="admin-page">
      <header className="admin-page__header">
        <div>
          <span className="eyebrow">OPERATIONS OVERVIEW · {dateLabel}</span>
          <h1>
            {greeting()}，{admin?.display_name}
          </h1>
          <p>这里是青禾生活的售后运营入口。M1 数据底座已经就绪。</p>
        </div>
        <button
          className="button button--ghost button--small"
          type="button"
          onClick={() => void load(true)}
          disabled={refreshing}
        >
          <RefreshCw size={15} className={refreshing ? "is-spinning" : ""} />
          {refreshing ? "刷新中" : "刷新数据"}
        </button>
      </header>

      {error && (
        <p className="inline-alert" role="alert">
          {error}。当前展示的是上一次成功加载的数据。
        </p>
      )}

      <section className="metric-grid" aria-label="店铺指标">
        <article className="metric-card metric-card--forest">
          <div className="metric-card__top">
            <span>订单总数</span>
            <Package size={19} />
          </div>
          <strong>{data.metrics.orders}</strong>
          <p>已写入 MySQL 的虚构订单</p>
        </article>
        <article className="metric-card">
          <div className="metric-card__top">
            <span>在售商品</span>
            <Boxes size={19} />
          </div>
          <strong>{data.metrics.products}</strong>
          <p>当前演示店铺的商品档案</p>
        </article>
        <article className="metric-card">
          <div className="metric-card__top">
            <span>知识切片</span>
            <BookOpenText size={19} />
          </div>
          <strong>{data.metrics.knowledge_chunks}</strong>
          <p>{data.metrics.knowledge_documents} 份售后文档等待向量化</p>
        </article>
        <article className="metric-card">
          <div className="metric-card__top">
            <span>待处理工单</span>
            <TicketCheck size={19} />
          </div>
          <strong>{data.metrics.open_tickets}</strong>
          <p>人工转接将在 M4 接入</p>
        </article>
      </section>

      <div className="dashboard-columns">
        <div className="dashboard-column dashboard-column--wide">
          <section className="panel">
            <div className="panel__header">
              <div>
                <span className="eyebrow">SYSTEM READINESS</span>
                <h2>能力进度</h2>
              </div>
              <span className="panel__counter">
                {readyCount}/{data.capabilities.length} 已就绪
              </span>
            </div>
            <div className="capability-grid">
              {data.capabilities.map((item) => {
                const StatusIcon =
                  item.status === "ready"
                    ? CheckCircle2
                    : item.status === "pending"
                      ? Clock3
                      : CircleDashed;
                return (
                  <article className={`capability-card capability-card--${item.status}`} key={item.key}>
                    <div className="capability-card__heading">
                      <StatusIcon size={17} />
                      <span>{capabilityLabels[item.status]}</span>
                    </div>
                    <h3>{item.label}</h3>
                    <p>{item.description}</p>
                  </article>
                );
              })}
            </div>
          </section>

          <section className="panel">
            <div className="panel__header">
              <div>
                <span className="eyebrow">RECENT ORDERS</span>
                <h2>最近订单</h2>
              </div>
              <Link className="text-link" to="/admin/orders">
                查看全部
                <ArrowRight size={14} />
              </Link>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>订单</th>
                    <th>客户</th>
                    <th>状态</th>
                    <th>商品</th>
                    <th>金额</th>
                    <th>下单时间</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_orders.map((order) => (
                    <tr key={order.order_no}>
                      <td>
                        <span className="order-number">{order.order_no}</span>
                      </td>
                      <td>{order.customer_name}</td>
                      <td>
                        <StatusBadge status={order.status} />
                      </td>
                      <td>{order.item_count} 件</td>
                      <td className="money-cell">{formatMoney(order.total_cents)}</td>
                      <td className="muted-cell">{formatDateTime(order.placed_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <aside className="dashboard-column dashboard-column--narrow">
          <section className="sprint-card">
            <div className="sprint-card__top">
              <span className="eyebrow eyebrow--light">MILESTONE 01</span>
              <span className="sprint-card__badge">进行中</span>
            </div>
            <h2>工程骨架与数据底座</h2>
            <p>让后续 RAG、Agent 和运营后台有一块足够稳定的地基。</p>
            <ul>
              <li>
                <CheckCircle2 size={15} />
                Python 3.12 虚拟环境
              </li>
              <li>
                <CheckCircle2 size={15} />
                MySQL 表结构与迁移
              </li>
              <li>
                <CheckCircle2 size={15} />
                管理员登录与会话
              </li>
              <li>
                <CheckCircle2 size={15} />
                虚构商品、订单与知识种子
              </li>
            </ul>
            <Link className="button button--light button--full" to="/admin/orders">
              查看订单台账
              <ArrowRight size={15} />
            </Link>
          </section>

          <section className="next-card">
            <div className="next-card__icon">
              <Database size={19} />
            </div>
            <span className="eyebrow">UP NEXT · M2</span>
            <h2>知识库与向量检索</h2>
            <p>调用硅基流动 BGE-M3 生成向量，写入本地 Chroma，并建立检索调试页。</p>
            <div className="next-card__meta">
              <span>Embedding API</span>
              <span>Chroma</span>
              <span>文档切片</span>
            </div>
          </section>

          <section className="quiet-panel">
            <span className="eyebrow">DATA NOTE</span>
            <h3>全部为虚构演示数据</h3>
            <p>客户姓名、手机号、地址和订单均为合成数据，不包含真实个人信息。</p>
            <p className="quiet-panel__timestamp">
              最近刷新 {formatDateTime(data.generated_at)}
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
