import { PackageSearch, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { StatusBadge } from "../components/StatusBadge";
import { api, type OrderListResponse } from "../lib/api";
import { formatDateTime, formatMoney, shipmentStatus } from "../lib/format";

export function OrdersPage() {
  const [data, setData] = useState<OrderListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      setData(await api.orders(50));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "无法加载订单");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="admin-page">
      <header className="admin-page__header">
        <div>
          <span className="eyebrow">ORDER LEDGER</span>
          <h1>订单台账</h1>
          <p>用于客服查询与后续 Agent 工具调用的虚构订单基础数据。</p>
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

      <div className="ledger-summary">
        <div>
          <PackageSearch size={18} />
          <span>
            共 <strong>{data?.total ?? "—"}</strong> 个订单
          </span>
        </div>
        <p>客户姓名、电话和地址均为合成数据。</p>
      </div>

      {error && (
        <div className="inline-alert" role="alert">
          {error}
          <button className="text-button" type="button" onClick={() => void load()}>
            重试
          </button>
        </div>
      )}

      <section className="panel ledger-panel">
        {loading ? (
          <div className="page-loader page-loader--compact">
            <span className="screen-loader__pulse" />
            <p>读取订单…</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table data-table--orders">
              <thead>
                <tr>
                  <th>订单号</th>
                  <th>客户</th>
                  <th>订单状态</th>
                  <th>物流</th>
                  <th>商品</th>
                  <th>实付</th>
                  <th>下单时间</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((order) => (
                  <tr key={order.order_no}>
                    <td>
                      <span className="order-number">{order.order_no}</span>
                    </td>
                    <td>
                      <div className="customer-cell">
                        <strong>{order.customer_name}</strong>
                        <span>{order.customer_phone}</span>
                      </div>
                    </td>
                    <td>
                      <StatusBadge status={order.status} />
                    </td>
                    <td>
                      {order.shipment_status ? (
                        <span className="shipment-label">
                          {shipmentStatus[order.shipment_status] ?? order.shipment_status}
                        </span>
                      ) : (
                        <span className="muted-cell">尚未发货</span>
                      )}
                    </td>
                    <td>{order.item_count} 件</td>
                    <td className="money-cell">{formatMoney(order.total_cents)}</td>
                    <td className="muted-cell">{formatDateTime(order.placed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data?.items.length === 0 && (
              <div className="empty-state">
                <PackageSearch size={28} />
                <h3>还没有订单</h3>
                <p>运行种子脚本后，订单会出现在这里。</p>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
