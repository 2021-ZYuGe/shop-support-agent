export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

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
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
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
  indexed_chunks: number;
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

export type IndexStatus = "empty" | "pending" | "partial" | "indexed" | "failed";

export interface KnowledgeSummary {
  documents: number;
  chunks: number;
  indexed_chunks: number;
  pending_chunks: number;
  failed_chunks: number;
}

export interface KnowledgeDocument {
  id: number;
  title: string;
  doc_type: string;
  version: string;
  status: string;
  source_name: string;
  effective_date: string | null;
  created_at: string;
  updated_at: string;
  chunk_count: number;
  indexed_count: number;
  pending_count: number;
  failed_count: number;
  index_status: IndexStatus;
}

export interface KnowledgeDocumentList {
  items: KnowledgeDocument[];
  summary: KnowledgeSummary;
}

export interface KnowledgeIndexResponse {
  document: KnowledgeDocument;
  message: string;
}

export interface KnowledgeSearchItem {
  chunk_id: number;
  document_id: number;
  title: string;
  doc_type: string;
  version: string;
  heading: string | null;
  content: string;
  source_name: string;
  similarity: number;
}

export interface KnowledgeSearchResponse {
  query: string;
  top_k: number;
  total: number;
  results: KnowledgeSearchItem[];
}

export interface ChatSource {
  chunk_id: number;
  document_id: number;
  title: string;
  doc_type: string;
  version: string;
  heading: string | null;
  content: string;
  source_name: string;
  similarity: number;
}

export interface ChatMessage {
  id: number;
  role: string;
  content: string;
  citations: ChatSource[] | null;
  model: string | null;
  created_at: string;
}

export interface ChatConversation {
  public_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
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
  knowledgeDocuments: () =>
    request<KnowledgeDocumentList>("/api/admin/knowledge/documents"),
  uploadKnowledgeDocument: (formData: FormData) =>
    request<KnowledgeDocument>("/api/admin/knowledge/documents", {
      method: "POST",
      body: formData,
    }),
  indexKnowledgeDocument: (documentId: number) =>
    request<KnowledgeIndexResponse>(`/api/admin/knowledge/documents/${documentId}/index`, {
      method: "POST",
    }),
  searchKnowledge: (query: string, topK = 5) =>
    request<KnowledgeSearchResponse>(
      `/api/admin/knowledge/search?q=${encodeURIComponent(query)}&top_k=${topK}`,
    ),
  chatConversation: (publicId: string) =>
    request<ChatConversation>(`/api/chat/conversations/${encodeURIComponent(publicId)}`),
};
