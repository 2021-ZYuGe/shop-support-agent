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

export const conversationStatus: Record<string, { label: string; tone: string }> = {
  active: { label: "AI 对话中", tone: "blue" },
  handed_off: { label: "已转人工", tone: "rose" },
};

export const ticketStatus: Record<string, { label: string; tone: string }> = {
  open: { label: "待处理", tone: "amber" },
  in_progress: { label: "处理中", tone: "blue" },
  resolved: { label: "已解决", tone: "green" },
  closed: { label: "已关闭", tone: "muted" },
};

export const ticketPriority: Record<string, { label: string; tone: string }> = {
  high: { label: "高优先级", tone: "rose" },
  normal: { label: "普通", tone: "neutral" },
  low: { label: "低", tone: "muted" },
};

export function conversationStatusMeta(status: string) {
  return conversationStatus[status] ?? { label: status, tone: "neutral" };
}

export function ticketStatusMeta(status: string) {
  return ticketStatus[status] ?? { label: status, tone: "neutral" };
}

export function ticketPriorityMeta(priority: string) {
  return ticketPriority[priority] ?? { label: priority, tone: "neutral" };
}
