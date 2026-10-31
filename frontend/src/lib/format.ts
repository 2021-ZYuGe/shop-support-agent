export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatMoney(cents: number): string {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 2,
  }).format(cents / 100);
}

export const orderStatus: Record<string, { label: string; tone: string }> = {
  paid: { label: "待发货", tone: "amber" },
  shipped: { label: "运输中", tone: "blue" },
  delivered: { label: "已签收", tone: "green" },
  completed: { label: "已完成", tone: "neutral" },
  cancelled: { label: "已取消", tone: "muted" },
  refunding: { label: "售后中", tone: "rose" },
};

export const shipmentStatus: Record<string, string> = {
  in_transit: "在途",
  delivered: "已签收",
  pending: "待揽收",
};

export function statusLabel(status: string): string {
  return orderStatus[status]?.label ?? status;
}

export function statusTone(status: string): string {
  return orderStatus[status]?.tone ?? "neutral";
}
