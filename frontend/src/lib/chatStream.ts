import { API_BASE, ApiError, type ChatSource, type ChatToolTrace } from "./api";

export type ChatMode = "rag" | "agent" | "fallback" | "handoff" | "clarify";

export interface ChatStreamMeta {
  conversation_id: string;
  mode: ChatMode;
  sources: ChatSource[];
  tools: ChatToolTrace[];
}

export interface ChatStreamDone {
  conversation_id: string;
  message_id: number | null;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  mode: ChatMode;
  tools: ChatToolTrace[];
}

interface ChatStreamHandlers {
  onMeta: (meta: ChatStreamMeta) => void;
  onDelta: (text: string) => void;
  onDone: (done: ChatStreamDone) => void;
  onError: (message: string) => void;
}

export async function streamChat(
  message: string,
  conversationId: string | null,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
    signal,
  });

  if (!response.ok) {
    let detail = "无法连接客服助手，请稍后再试。";
    try {
      const body = (await response.json()) as { detail?: string };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Keep the generic message for non-JSON failures.
    }
    throw new ApiError(response.status, detail);
  }

  if (!response.body) {
    throw new ApiError(500, "浏览器没有收到流式响应。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawDone = false;
  let sawError = false;

  const dispatch = (block: string) => {
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }
    if (dataLines.length === 0) return;

    let data: unknown;
    try {
      data = JSON.parse(dataLines.join("\n"));
    } catch {
      return;
    }

    if (eventName === "meta") {
      handlers.onMeta(data as ChatStreamMeta);
    } else if (eventName === "delta") {
      handlers.onDelta((data as { text: string }).text);
    } else if (eventName === "done") {
      sawDone = true;
      handlers.onDone(data as ChatStreamDone);
    } else if (eventName === "error") {
      sawError = true;
      handlers.onError((data as { message?: string }).message ?? "回答生成失败");
    }
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        if (block.trim()) dispatch(block);
        boundary = buffer.indexOf("\n\n");
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) dispatch(buffer);
  } finally {
    reader.releaseLock();
  }

  if (!sawDone && !sawError) {
    throw new ApiError(502, "回答连接意外中断，请稍后重试。");
  }
}
