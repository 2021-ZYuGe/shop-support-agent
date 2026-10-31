const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (!response.ok) {
    let message = "请求失败，请稍后重试";
    try {
      const body = (await response.json()) as { detail?: string };
      if (typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // Keep the generic message when the server does not return JSON.
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export interface Admin {
  id: number;
  email: string;
  display_name: string;
}

export interface LoginResponse {
  admin: Admin;
  expires_at: string;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  database: "connected" | "unavailable";
  app: string;
  version: string;
  environment: string;
  integrations: {
    deepseek: boolean;
    siliconflow: boolean;
  };
  timestamp: string;
}

export interface Metrics {
  products: number;
  orders: number;
  knowledge_documents: number;
  knowledge_chunks: number;
  open_tickets: number;
  messages: number;
}

export interface RecentOrder {
  order_no: string;
  customer_name: string;
  status: string;
  placed_at: string;
  total_cents: number;
  item_count: number;
  shipment_status: string | null;
}

export interface Capability {
  key: string;
  label: string;
  status: "ready" | "pending" | "planned";
  description: string;
}

export interface DashboardResponse {
  metrics: Metrics;
  recent_orders: RecentOrder[];
  capabilities: Capability[];
  generated_at: string;
}

export interface OrderListItem {
  order_no: string;
  customer_name: string;
  customer_phone: string;
  status: string;
  total_cents: number;
  item_count: number;
  shipment_status: string | null;
  placed_at: string;
  delivered_at: string | null;
}

export interface OrderListResponse {
  items: OrderListItem[];
  total: number;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  login: (email: string, password: string) =>
    request<LoginResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ message: string }>("/api/auth/logout", { method: "POST" }),
  me: () => request<Admin>("/api/auth/me"),
  dashboard: () => request<DashboardResponse>("/api/admin/overview"),
  orders: (limit = 50) => request<OrderListResponse>(`/api/admin/orders?limit=${limit}`),
};
