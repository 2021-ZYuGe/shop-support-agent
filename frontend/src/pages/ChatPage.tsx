import {
  AlertCircle,
  ArrowLeft,
  BookOpenText,
  Bot,
  CheckCircle2,
  Loader2,
  RotateCcw,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  ThumbsDown,
  ThumbsUp,
  Wrench,
} from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { Link } from "react-router-dom";

import { Brand } from "../components/Brand";
import {
  api,
  ApiError,
  type ChatConversation,
  type ChatFeedback,
  type ChatSource,
  type ChatToolTrace,
} from "../lib/api";
import { streamChat, type ChatMode } from "../lib/chatStream";

const CONVERSATION_KEY = "qinghe_chat_conversation";
const MAX_MESSAGE = 1000;

interface UiMessage {
  key: string;
  role: "user" | "assistant";
  content: string;
  sources: ChatSource[];
  toolTrace: ChatToolTrace[];
  mode?: ChatMode;
  streaming?: boolean;
  serverId?: number;
  feedback?: ChatFeedback | null;
}

const suggestions = [
  "七天无理由退货怎么申请？",
  "质量问题可以换货吗？",
  "查一下订单 QH20261028003 到哪了？",
  "会员积分怎么抵扣？",
];

const modeTags: Record<string, { label: string; tone: string }> = {
  fallback: { label: "知识库未命中", tone: "rose" },
  handoff: { label: "已转人工", tone: "green" },
  clarify: { label: "需要补充信息", tone: "amber" },
  agent: { label: "工具辅助", tone: "blue" },
};

function historyMode(
  model: string | null,
  tools: ChatToolTrace[],
): ChatMode {
  if (model === "policy_fallback") return "fallback";
  if (model === "handoff_workflow") return "handoff";
  if (model === "workflow_clarify") return "clarify";
  return tools.length > 0 ? "agent" : "rag";
}

function mapConversation(conversation: ChatConversation): UiMessage[] {
  return conversation.messages.map((message) => {
    const tools = message.tool_trace ?? [];
    return {
      key: `server-${message.id}`,
      role: message.role === "user" ? "user" : "assistant",
      content: message.content,
      sources: message.citations ?? [],
      toolTrace: tools,
      mode:
        message.role === "assistant"
          ? historyMode(message.model, tools)
          : undefined,
      streaming: false,
      serverId: message.id,
      feedback: message.feedback,
    };
  });
}

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|\[\d+\])/g;
  let lastIndex = 0;
  let index = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("**")) {
      parts.push(<strong key={`${keyPrefix}-b-${index}`}>{token.slice(2, -2)}</strong>);
    } else {
      parts.push(
        <span className="inline-citation" key={`${keyPrefix}-c-${index}`}>
          {token}
        </span>,
      );
    }
    lastIndex = regex.lastIndex;
    index += 1;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}

function MessageContent({ text }: { text: string }) {
  const nodes: ReactNode[] = [];
  let bullets: string[] = [];
  let blockIndex = 0;

  const flushBullets = () => {
    if (bullets.length === 0) return;
    nodes.push(
      <ul key={`list-${blockIndex++}`}>
        {bullets.map((item, index) => (
          <li key={`li-${blockIndex}-${index}`}>
            {renderInline(item, `li-${blockIndex}-${index}`)}
          </li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (!line) {
      flushBullets();
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      bullets.push(line.replace(/^[-*]\s+/, ""));
      continue;
    }
    flushBullets();
    if (/^#{1,6}\s+/.test(line)) {
      nodes.push(
        <strong className="message-heading" key={`h-${blockIndex++}`}>
          {renderInline(line.replace(/^#{1,6}\s+/, ""), `h-${blockIndex}`)}
        </strong>,
      );
    } else {
      nodes.push(
        <p key={`p-${blockIndex++}`}>{renderInline(line, `p-${blockIndex}`)}</p>,
      );
    }
  }
  flushBullets();
  return <div className="message-rich">{nodes}</div>;
}

function sourceList(message: UiMessage): Array<{ source: ChatSource; number: number }> {
  const all = message.sources.map((source, index) => ({ source, number: index + 1 }));
  const referenced = new Set<number>();
  for (const match of message.content.matchAll(/\[(\d+)\]/g)) {
    referenced.add(Number(match[1]));
  }
  if (referenced.size === 0) return all;
  const filtered = all.filter((item) => referenced.has(item.number));
  return filtered.length > 0 ? filtered : all;
}

function ToolTrace({ message }: { message: UiMessage }) {
  if (message.toolTrace.length === 0) return null;

  return (
    <details className="chat-tools">
      <summary>
        <Wrench size={14} />
        工具调用 · {message.toolTrace.length} 项
      </summary>
      <div className="chat-tools__list">
        {message.toolTrace.map((tool, index) => (
          <article
            className={`chat-tool chat-tool--${tool.status}`}
            key={`${message.key}-${tool.tool}-${index}`}
          >
            <span className="chat-tool__status">
              {tool.status === "success" ? (
                <CheckCircle2 size={14} />
              ) : (
                <AlertCircle size={14} />
              )}
            </span>
            <div>
              <strong>{tool.label}</strong>
              <p>{tool.summary}</p>
            </div>
            <em>{tool.duration_ms}ms</em>
          </article>
        ))}
      </div>
    </details>
  );
}

function SourceCards({ message }: { message: UiMessage }) {
  const sources = sourceList(message);
  if (sources.length === 0) return null;

  return (
    <details className="chat-sources">
      <summary>
        <BookOpenText size={14} />
        引用资料 · {sources.length} 条
      </summary>
      <div className="chat-sources__list">
        {sources.map(({ source, number }) => (
          <article className="chat-source" key={`${message.key}-${source.chunk_id}`}>
            <span className="chat-source__number">{number}</span>
            <div>
              <strong>{source.title}</strong>
              <span>
                {source.heading || "未命名章节"} · {Math.round(source.similarity * 100)}%
              </span>
              <p>{source.content}</p>
            </div>
          </article>
        ))}
      </div>
    </details>
  );
}

function TypingState({ mode }: { mode?: ChatMode }) {
  return (
    <div className="typing-state">
      <span className="typing-dots">
        <i />
        <i />
        <i />
      </span>
      <span>{mode === "fallback" ? "正在整理回复…" : "正在查阅售后资料…"}</span>
    </div>
  );
}

export function ChatPage() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [feedbackPending, setFeedbackPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const localKey = useRef(0);

  const nextKey = (prefix: string) => `${prefix}-${Date.now()}-${localKey.current++}`;

  useEffect(() => {
    const stored = sessionStorage.getItem(CONVERSATION_KEY);
    if (!stored) {
      setRestoring(false);
      return;
    }

    let active = true;
    api
      .chatConversation(stored)
      .then((conversation) => {
        if (!active) return;
        setConversationId(conversation.public_id);
        setMessages(mapConversation(conversation));
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        sessionStorage.removeItem(CONVERSATION_KEY);
        if (!(loadError instanceof ApiError) || loadError.status !== 404) {
          setError("无法恢复上一次对话，已为你开启新的会话。");
        }
      })
      .finally(() => {
        if (active) setRestoring(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  }, [messages, isStreaming]);

  const handleNewConversation = () => {
    if (isStreaming) return;
    sessionStorage.removeItem(CONVERSATION_KEY);
    setConversationId(null);
    setMessages([]);
    setInput("");
    setError(null);
    textareaRef.current?.focus();
  };

  const handleFeedback = async (
    messageKey: string,
    rating: 1 | -1,
  ) => {
    const message = messages.find((item) => item.key === messageKey);
    if (!message?.serverId || !conversationId || feedbackPending) return;

    setFeedbackPending(messageKey);
    try {
      const feedback = await api.submitFeedback(
        conversationId,
        message.serverId,
        rating,
      );
      setMessages((current) =>
        current.map((item) =>
          item.key === messageKey ? { ...item, feedback } : item,
        ),
      );
    } catch (feedbackError) {
      setError(
        feedbackError instanceof Error ? feedbackError.message : "反馈提交失败",
      );
    } finally {
      setFeedbackPending(null);
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const sendMessage = async (rawText: string) => {
    const text = rawText.trim();
    if (!text || isStreaming || restoring) return;

    const userKey = nextKey("user");
    const assistantKey = nextKey("assistant");
    setMessages((current) => [
      ...current,
      { key: userKey, role: "user", content: text, sources: [], toolTrace: [] },
      {
        key: assistantKey,
        role: "assistant",
        content: "",
        sources: [],
        toolTrace: [],
        streaming: true,
      },
    ]);
    setInput("");
    setError(null);
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;
    let generated = "";

    try {
      await streamChat(
        text,
        conversationId,
        {
          onMeta: (meta) => {
            setConversationId(meta.conversation_id);
            sessionStorage.setItem(CONVERSATION_KEY, meta.conversation_id);
            setMessages((current) =>
              current.map((message) =>
                message.key === assistantKey
                  ? {
                      ...message,
                      sources: meta.sources,
                      toolTrace: meta.tools,
                      mode: meta.mode,
                    }
                  : message,
              ),
            );
          },
          onDelta: (delta) => {
            generated += delta;
            setMessages((current) =>
              current.map((message) =>
                message.key === assistantKey
                  ? { ...message, content: generated }
                  : message,
              ),
            );
          },
          onDone: (done) => {
            setMessages((current) =>
              current.map((message) =>
                message.key === assistantKey
                  ? {
                      ...message,
                      streaming: false,
                      serverId: done.message_id ?? undefined,
                    }
                  : message,
              ),
            );
          },
          onError: (message) => {
            setError(message);
            if (!generated) {
              setMessages((current) =>
                current.filter((item) => item.key !== assistantKey),
              );
            } else {
              setMessages((current) =>
                current.map((item) =>
                  item.key === assistantKey ? { ...item, streaming: false } : item,
                ),
              );
            }
          },
        },
        controller.signal,
      );
    } catch (sendError) {
      if (sendError instanceof DOMException && sendError.name === "AbortError") {
        setError("已停止生成。");
      } else {
        setError(
          sendError instanceof Error
            ? sendError.message
            : "消息发送失败，请稍后再试。",
        );
      }
      if (!generated) {
        setMessages((current) => current.filter((item) => item.key !== assistantKey));
      } else {
        setMessages((current) =>
          current.map((item) =>
            item.key === assistantKey ? { ...item, streaming: false } : item,
          ),
        );
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void sendMessage(input);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isStreaming) void sendMessage(input);
    }
  };

  const handleSuggestion = (suggestion: string) => {
    setInput(suggestion);
    textareaRef.current?.focus();
  };

  return (
    <div className="chat-page">
      <header className="chat-nav">
        <Brand />
        <nav className="chat-nav__links">
          <Link to="/">
            <ArrowLeft size={15} />
            返回首页
          </Link>
          <Link to="/admin/login">运营后台</Link>
        </nav>
      </header>

      <main className="chat-shell">
        <aside className="chat-aside">
          <div>
            <span className="eyebrow eyebrow--light">AI AFTER-SALES ASSISTANT</span>
            <h1>售后问题，先问青禾。</h1>
            <p>
              基于店铺售后知识、订单工具与 DeepSeek，先查资料和业务事实，
              再组织回答。每个结论都尽量留下可核对的来源。
            </p>
          </div>

          <div className="chat-aside__card">
            <span className="eyebrow">HOW IT WORKS</span>
            <div className="chat-flow">
              <span><b>01</b> 理解问题</span>
              <i />
              <span><b>02</b> 检索 / 调工具</span>
              <i />
              <span><b>03</b> 生成回答</span>
            </div>
            <p>系统会先判断需要知识还是业务数据；不知道时会明确说明，而不是继续编造。</p>
          </div>

          <div className="chat-aside__scope">
            <ShieldCheck size={18} />
            <div>
              <strong>边界说明</strong>
              <p>可查询演示订单与物流，也可创建人工工单；真实退款、改地址和赔付不会自动执行。</p>
            </div>
          </div>

          <div className="chat-aside__note">
            <Sparkles size={15} />
            <span>回答由 AI 生成，请以引用资料和人工客服确认为准。</span>
          </div>
        </aside>

        <section className="chat-panel" aria-label="AI 售后客服">
          <header className="chat-panel__header">
            <div className="chat-panel__identity">
              <div className="chat-panel__avatar">
                <Bot size={21} />
              </div>
              <div>
                <strong>青禾售后助理</strong>
                <span>
                  <i className="online-dot" />
                  DeepSeek + 知识库 + 业务工具
                </span>
              </div>
            </div>
            <button
              className="chat-new-button"
              type="button"
              onClick={handleNewConversation}
              disabled={isStreaming || restoring}
              title="开始新对话"
            >
              <RotateCcw size={15} />
              新对话
            </button>
          </header>

          <div className="chat-messages" ref={scrollRef}>
            {restoring ? (
              <div className="chat-restoring">
                <Loader2 size={20} className="is-spinning" />
                正在恢复上次对话…
              </div>
            ) : messages.length === 0 ? (
              <div className="chat-welcome">
                <div className="chat-welcome__icon">
                  <Sparkles size={21} />
                </div>
                <span className="eyebrow">WELCOME TO QINGHE CARE</span>
                <h2>你好，我是青禾售后助理。</h2>
                <p>
                  可以问我售后政策，也可以查询演示订单和物流、判断售后条件，
                  需要时还能创建人工工单。我会先检索知识与业务数据，再给出带依据的回答。
                </p>
                <div className="chat-suggestions">
                  {suggestions.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => handleSuggestion(suggestion)}
                    >
                      <span>{suggestion}</span>
                      <Send size={13} />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message) =>
                message.role === "user" ? (
                  <div className="chat-message chat-message--user" key={message.key}>
                    <div className="chat-bubble chat-bubble--user">{message.content}</div>
                  </div>
                ) : (
                  <div
                    className={`chat-message chat-message--assistant ${
                      message.mode === "fallback" ? "is-fallback" : ""
                    }`}
                    key={message.key}
                  >
                    <div className="chat-message__avatar">
                      <Bot size={16} />
                    </div>
                    <div className="chat-message__body">
                      {message.mode && modeTags[message.mode] && (
                        <span
                          className={`chat-mode-tag chat-mode-tag--${modeTags[message.mode].tone}`}
                        >
                          {modeTags[message.mode].label}
                        </span>
                      )}
                      <div className="chat-bubble chat-bubble--assistant">
                        {message.streaming && !message.content ? (
                          <TypingState mode={message.mode} />
                        ) : (
                          <>
                            <MessageContent text={message.content} />
                            {message.streaming && <span className="stream-caret" />}
                          </>
                        )}
                      </div>
                      <ToolTrace message={message} />
                      <SourceCards message={message} />
                      {!message.streaming && message.serverId && (
                        <div className="chat-feedback">
                          <span>这条回答有帮助吗？</span>
                          <div className="chat-feedback__buttons">
                            <button
                              className={`feedback-button ${
                                message.feedback?.rating === 1 ? "is-active" : ""
                              }`}
                              type="button"
                              onClick={() => void handleFeedback(message.key, 1)}
                              disabled={feedbackPending === message.key}
                              aria-label="有帮助"
                              title="有帮助"
                            >
                              <ThumbsUp size={14} />
                            </button>
                            <button
                              className={`feedback-button ${
                                message.feedback?.rating === -1 ? "is-active" : ""
                              }`}
                              type="button"
                              onClick={() => void handleFeedback(message.key, -1)}
                              disabled={feedbackPending === message.key}
                              aria-label="没帮助"
                              title="没帮助"
                            >
                              <ThumbsDown size={14} />
                            </button>
                          </div>
                          {message.feedback && (
                            <em>{feedbackPending === message.key ? "提交中…" : "已记录"}</em>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ),
              )
            )}
            <div />
          </div>

          {error && (
            <div className="chat-error" role="alert">
              <span>{error}</span>
              <button type="button" onClick={() => setError(null)} aria-label="关闭提示">
                ×
              </button>
            </div>
          )}

          <form className="chat-composer" onSubmit={handleSubmit}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(event) => setInput(event.target.value.slice(0, MAX_MESSAGE))}
              onKeyDown={handleKeyDown}
              placeholder="输入你的售后问题，例如：质量问题可以换货吗？"
              aria-label="输入售后问题"
              rows={2}
              disabled={restoring}
            />
            <div className="chat-composer__bottom">
              <span>{input.length}/{MAX_MESSAGE} · Enter 发送，Shift + Enter 换行</span>
              {isStreaming ? (
                <button
                  className="chat-stop-button"
                  type="button"
                  onClick={handleStop}
                  title="停止生成"
                >
                  <Square size={13} />
                  停止
                </button>
              ) : (
                <button
                  className="chat-send-button"
                  type="submit"
                  disabled={!input.trim() || restoring}
                  title="发送问题"
                >
                  <Send size={16} />
                </button>
              )}
            </div>
          </form>
        </section>
      </main>
    </div>
  );
}
