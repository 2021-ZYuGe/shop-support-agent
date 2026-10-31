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

export interface ChatToolTrace {
  tool: string;
  label: string;
  status: string;
  summary: string;
  duration_ms: number;
}

export interface ChatFeedback {
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  role: string;
  content: string;
  citations: ChatSource[] | null;
  tool_trace: ChatToolTrace[] | null;
  feedback: ChatFeedback | null;
  model: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  created_at: string;
}

export interface AdminConversationSummary {
  public_id: string;
  status: string;
  channel: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_preview: string | null;
  open_ticket_count: number;
  positive_feedback: number;
  negative_feedback: number;
}

export interface AdminConversationList {
  items: AdminConversationSummary[];
  total: number;
  status_counts: Record<string, number>;
}

export interface AdminTicketSummary {
  id: number;
  conversation_public_id: string;
  reason: string;
  summary: string;
  status: string;
  priority: string;
  assigned_admin_id: number | null;
  assigned_admin_name: string | null;
  resolution_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminConversationDetail {
  public_id: string;
  status: string;
  channel: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
  tickets: AdminTicketSummary[];
}

export interface AdminTicketList {
  items: AdminTicketSummary[];
  total: number;
  status_counts: Record<string, number>;
}

export interface AdminTicketUpdate {
  status?: string;
  priority?: string;
  resolution_note?: string;
  assign_to_me?: boolean;
}

export interface InsightMetrics {
  conversations_total: number;
  conversations_active: number;
  conversations_handed_off: number;
  tickets_open: number;
  tickets_in_progress: number;
  tickets_resolved: number;
  messages_total: number;
  assistant_messages: number;
  feedback_positive: number;
  feedback_negative: number;
  fallback_messages: number;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_cost_cny: number;
  avg_latency_ms: number;
}

export interface ToolUsageItem {
  tool_name: string;
  label: string;
  count: number;
  avg_duration_ms: number;
}

export interface LowFeedbackItem {
  feedback_id: number;
  conversation_public_id: string;
  message_id: number;
  assistant_preview: string;
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface KnowledgeGapItem {
  conversation_public_id: string;
  question: string;
  assistant_preview: string;
  created_at: string;
}

export interface InsightsResponse {
  metrics: InsightMetrics;
  tools: ToolUsageItem[];
  low_feedback: LowFeedbackItem[];
  knowledge_gaps: KnowledgeGapItem[];
  generated_at: string;
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
  submitFeedback: (
    publicId: string,
    messageId: number,
    rating: 1 | -1,
    comment?: string,
  ) =>
    request<ChatFeedback>(
      `/api/chat/conversations/${encodeURIComponent(publicId)}/messages/${messageId}/feedback`,
      {
        method: "POST",
        body: JSON.stringify({ rating, comment: comment || null }),
      },
    ),
  adminConversations: (status?: string) =>
    request<AdminConversationList>(
      `/api/admin/conversations${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),
  adminConversation: (publicId: string) =>
    request<AdminConversationDetail>(
      `/api/admin/conversations/${encodeURIComponent(publicId)}`,
    ),
  adminTickets: (status?: string) =>
    request<AdminTicketList>(
      `/api/admin/tickets${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),
  updateTicket: (ticketId: number, payload: AdminTicketUpdate) =>
    request<AdminTicketSummary>(`/api/admin/tickets/${ticketId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  adminInsights: () => request<InsightsResponse>("/api/admin/insights"),
};
