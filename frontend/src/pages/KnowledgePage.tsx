import {
  AlertCircle,
  BookOpenCheck,
  CheckCircle2,
  Clock3,
  FileText,
  Layers3,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";

import { api, type KnowledgeDocument, type KnowledgeDocumentList, type KnowledgeSearchItem } from "../lib/api";
import { formatDateTime } from "../lib/format";

const docTypeLabels: Record<string, string> = {
  policy: "售后政策",
  logistics: "物流说明",
  faq: "常见问题",
  product: "商品资料",
  other: "其他",
};

const indexStatusMeta: Record<string, { label: string; tone: string }> = {
  indexed: { label: "已建立索引", tone: "green" },
  pending: { label: "待建立索引", tone: "amber" },
  partial: { label: "部分索引", tone: "rose" },
  failed: { label: "索引失败", tone: "rose" },
  empty: { label: "无切片", tone: "muted" },
};

type Feedback = { type: "success" | "error" | "info"; text: string } | null;

function FeedbackBanner({ feedback }: { feedback: Feedback }) {
  if (!feedback) return null;
  const Icon = feedback.type === "success" ? CheckCircle2 : AlertCircle;
  return (
    <div className={`feedback-banner feedback-banner--${feedback.type}`} role="status">
      <Icon size={16} />
      <span>{feedback.text}</span>
    </div>
  );
}

export function KnowledgePage() {
  const [data, setData] = useState<KnowledgeDocumentList | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("faq");
  const [version, setVersion] = useState("1.0");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [uploading, setUploading] = useState(false);
  const [indexingId, setIndexingId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(3);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<KnowledgeSearchItem[] | null>(null);

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setLoadError(null);
    try {
      setData(await api.knowledgeDocuments());
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "无法加载知识库");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null;
    setFile(selected);
    setFeedback(null);
    if (selected && !title.trim()) {
      setTitle(selected.name.replace(/\.[^.]+$/, ""));
    }
  };

  const resetUpload = () => {
    setFile(null);
    setTitle("");
    setVersion("1.0");
    setEffectiveDate("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setFeedback({ type: "error", text: "请先选择一个 Markdown、TXT、PDF 或 DOCX 文件。" });
      return;
    }

    setUploading(true);
    setFeedback({ type: "info", text: "文档已提交，正在解析、切片并调用 BGE-M3…" });
    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", title.trim() || file.name.replace(/\.[^.]+$/, ""));
    formData.append("doc_type", docType);
    formData.append("version", version.trim() || "1.0");
    if (effectiveDate) formData.append("effective_date", effectiveDate);

    try {
      const document = await api.uploadKnowledgeDocument(formData);
      try {
        const indexed = await api.indexKnowledgeDocument(document.id);
        setFeedback({ type: "success", text: indexed.message });
      } catch (error) {
        const message = error instanceof Error ? error.message : "向量索引失败";
        setFeedback({
          type: "error",
          text: `文档已上传，但索引未完成：${message}。可以在文档列表点击“建立索引”重试。`,
        });
      }
      resetUpload();
      await load(true);
    } catch (error) {
      setFeedback({
        type: "error",
        text: error instanceof Error ? error.message : "文档上传失败",
      });
    } finally {
      setUploading(false);
    }
  };

  const handleIndex = async (document: KnowledgeDocument) => {
    setIndexingId(document.id);
    setFeedback({ type: "info", text: `正在为《${document.title}》建立向量索引…` });
    try {
      const result = await api.indexKnowledgeDocument(document.id);
      setFeedback({ type: "success", text: result.message });
      await load(true);
    } catch (error) {
      setFeedback({
        type: "error",
        text: error instanceof Error ? error.message : "索引失败",
      });
    } finally {
      setIndexingId(null);
    }
  };

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setSearchError(null);
    try {
      const response = await api.searchKnowledge(query.trim(), topK);
      setSearchResults(response.results);
    } catch (error) {
      setSearchError(error instanceof Error ? error.message : "检索失败");
      setSearchResults(null);
    } finally {
      setSearching(false);
    }
  };

  const summary = data?.summary;
  const indexableDocs = data?.items.filter((document) => document.index_status !== "indexed") ?? [];

  return (
    <div className="admin-page knowledge-page">
      <header className="admin-page__header">
        <div>
          <span className="eyebrow">KNOWLEDGE STUDIO · M2</span>
          <h1>知识库与检索</h1>
          <p>上传售后资料，调用硅基流动 BGE-M3 生成向量，再用 Chroma 做语义检索。</p>
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

      <FeedbackBanner feedback={feedback} />

      {!data && loading && (
        <div className="page-loader">
          <span className="screen-loader__pulse" />
          <p>正在读取知识库状态…</p>
        </div>
      )}

      {loadError && (
        <div className="error-panel">
          <h2>知识库暂时不可用</h2>
          <p>{loadError}</p>
          <button className="button button--primary" type="button" onClick={() => void load()}>
            重新加载
          </button>
        </div>
      )}

      {data && (
        <>
          <section className="knowledge-stats" aria-label="知识库统计">
            <article className="knowledge-stat">
              <BookOpenCheck size={18} />
              <span>文档</span>
              <strong>{summary?.documents ?? 0}</strong>
              <small>份售后资料</small>
            </article>
            <article className="knowledge-stat">
              <Layers3 size={18} />
              <span>切片</span>
              <strong>{summary?.chunks ?? 0}</strong>
              <small>个可检索片段</small>
            </article>
            <article className="knowledge-stat knowledge-stat--ready">
              <CheckCircle2 size={18} />
              <span>已索引</span>
              <strong>{summary?.indexed_chunks ?? 0}</strong>
              <small>已写入 Chroma</small>
            </article>
            <article className="knowledge-stat">
              <Clock3 size={18} />
              <span>待处理</span>
              <strong>{(summary?.pending_chunks ?? 0) + (summary?.failed_chunks ?? 0)}</strong>
              <small>待索引或需重试</small>
            </article>
          </section>

          <div className="knowledge-workspace">
            <section className="panel knowledge-editor">
              <div className="panel__header">
                <div>
                  <span className="eyebrow">INGEST DOCUMENT</span>
                  <h2>上传知识文档</h2>
                </div>
                <span className="panel__counter">M2</span>
              </div>
              <form className="upload-form" onSubmit={handleUpload}>
                <label className={`file-drop ${file ? "has-file" : ""}`}>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".md,.markdown,.txt,.pdf,.docx"
                    onChange={handleFileChange}
                  />
                  <span className="file-drop__icon">
                    {file ? <FileText size={20} /> : <UploadCloud size={20} />}
                  </span>
                  <span className="file-drop__copy">
                    <strong>{file ? file.name : "选择售后 FAQ、政策或物流文档"}</strong>
                    <small>
                      {file
                        ? `${(file.size / 1024).toFixed(1)} KB · 上传后自动建立索引`
                        : "支持 .md / .txt / .pdf / .docx，最大 10MB"}
                    </small>
                  </span>
                </label>

                <div className="knowledge-form-grid">
                  <label className="field">
                    <span>文档标题</span>
                    <input
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      placeholder="例如：冬季发货时效说明"
                      maxLength={200}
                    />
                  </label>
                  <label className="field">
                    <span>文档类型</span>
                    <select value={docType} onChange={(event) => setDocType(event.target.value)}>
                      <option value="faq">常见问题</option>
                      <option value="policy">售后政策</option>
                      <option value="logistics">物流说明</option>
                      <option value="product">商品资料</option>
                      <option value="other">其他</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>版本</span>
                    <input
                      value={version}
                      onChange={(event) => setVersion(event.target.value)}
                      placeholder="1.0"
                      maxLength={32}
                    />
                  </label>
                  <label className="field">
                    <span>生效日期（可选）</span>
                    <input
                      type="date"
                      value={effectiveDate}
                      onChange={(event) => setEffectiveDate(event.target.value)}
                    />
                  </label>
                </div>

                <button className="button button--primary button--full" type="submit" disabled={uploading}>
                  {uploading ? <Loader2 size={16} className="is-spinning" /> : <UploadCloud size={16} />}
                  {uploading ? "上传并建立索引中…" : "上传文档并建立索引"}
                </button>
                <p className="knowledge-note">
                  上传后会先写入 MySQL，再调用 BGE-M3 生成向量并写入 Chroma。扫描版 PDF
                  暂不支持 OCR。
                </p>
              </form>
              <div className="ingest-flow" aria-label="知识入库流程">
                <span>
                  <em>01</em>解析切片
                </span>
                <i>→</i>
                <span>
                  <em>02</em>BGE-M3
                </span>
                <i>→</i>
                <span>
                  <em>03</em>Chroma
                </span>
              </div>
            </section>

            <section className="panel knowledge-search-panel">
              <div className="panel__header">
                <div>
                  <span className="eyebrow">RETRIEVAL DEBUGGER</span>
                  <h2>语义检索调试</h2>
                </div>
                <Search size={18} />
              </div>
              <form className="search-form" onSubmit={handleSearch}>
                <div className="search-input-wrap">
                  <Search size={16} />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="例如：质量问题可以换货吗？"
                    maxLength={500}
                    aria-label="检索问题"
                  />
                </div>
                <div className="search-options">
                  <label>
                    Top K
                    <select value={topK} onChange={(event) => setTopK(Number(event.target.value))}>
                      <option value={3}>3</option>
                      <option value={5}>5</option>
                      <option value={10}>10</option>
                    </select>
                  </label>
                  <button className="button button--primary button--small" type="submit" disabled={searching}>
                    {searching ? <Loader2 size={14} className="is-spinning" /> : <Sparkles size={14} />}
                    {searching ? "检索中" : "检索"}
                  </button>
                </div>
              </form>

              {searchError && (
                <p className="inline-alert" role="alert">
                  {searchError}
                </p>
              )}

              <div className="knowledge-results">
                {searchResults === null && !searching && (
                  <div className="knowledge-empty">
                    <Search size={24} />
                    <h3>检索一次试试</h3>
                    <p>问题会先向量化，再从 Chroma 中召回最相近的政策片段。</p>
                  </div>
                )}
                {searchResults !== null && searchResults.length === 0 && (
                  <div className="knowledge-empty">
                    <Search size={24} />
                    <h3>没有命中</h3>
                    <p>知识库中没有足够接近的片段，可以换一种问法。</p>
                  </div>
                )}
                {searchResults?.map((result, index) => (
                  <article className="knowledge-result" key={result.chunk_id}>
                    <div className="knowledge-result__top">
                      <span className="knowledge-result__rank">{String(index + 1).padStart(2, "0")}</span>
                      <div>
                        <strong>{result.title}</strong>
                        <span>
                          {result.heading || docTypeLabels[result.doc_type] || result.doc_type}
                          {" · "}v{result.version}
                        </span>
                      </div>
                      <span className="similarity-pill">
                        {(result.similarity * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="similarity-track">
                      <span style={{ width: `${Math.max(4, result.similarity * 100)}%` }} />
                    </div>
                    <p className="knowledge-result__content">{result.content}</p>
                    <span className="knowledge-result__source">
                      chunk #{result.chunk_id} · {result.source_name}
                    </span>
                  </article>
                ))}
              </div>
            </section>
          </div>

          <section className="panel knowledge-docs-panel">
            <div className="panel__header">
              <div>
                <span className="eyebrow">DOCUMENT REGISTRY</span>
                <h2>知识文档</h2>
              </div>
              <span className="panel__counter">
                {summary?.indexed_chunks ?? 0}/{summary?.chunks ?? 0} 切片已索引
              </span>
            </div>

            {indexableDocs.length > 0 && (
              <p className="knowledge-hint">
                还有 {indexableDocs.length} 份文档没有完成索引。可以在下方逐份重试，失败切片会保留错误状态。
              </p>
            )}

            {loading ? (
              <div className="page-loader page-loader--compact">
                <span className="screen-loader__pulse" />
                <p>读取知识文档…</p>
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data-table knowledge-table">
                  <thead>
                    <tr>
                      <th>文档</th>
                      <th>类型 / 版本</th>
                      <th>切片</th>
                      <th>索引状态</th>
                      <th>最近更新</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((document) => {
                      const meta = indexStatusMeta[document.index_status] ?? indexStatusMeta.pending;
                      return (
                        <tr key={document.id}>
                          <td>
                            <div className="document-cell">
                              <FileText size={16} />
                              <div>
                                <strong>{document.title}</strong>
                                <span>{document.source_name}</span>
                              </div>
                            </div>
                          </td>
                          <td>
                            <span className="doc-type-label">
                              {docTypeLabels[document.doc_type] ?? document.doc_type}
                            </span>
                            <span className="muted-cell">v{document.version}</span>
                          </td>
                          <td>
                            {document.indexed_count}/{document.chunk_count}
                            <span className="muted-cell">
                              {document.failed_count > 0 ? ` · ${document.failed_count} 失败` : ""}
                            </span>
                          </td>
                          <td>
                            <span className={`index-state index-state--${meta.tone}`}>
                              <span />
                              {meta.label}
                            </span>
                          </td>
                          <td className="muted-cell">{formatDateTime(document.updated_at)}</td>
                          <td>
                            {document.index_status === "indexed" ? (
                              <span className="indexed-note">
                                <CheckCircle2 size={14} />
                                可检索
                              </span>
                            ) : (
                              <button
                                className="text-button"
                                type="button"
                                onClick={() => void handleIndex(document)}
                                disabled={indexingId !== null || uploading}
                              >
                                {indexingId === document.id ? "索引中…" : "建立索引"}
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
