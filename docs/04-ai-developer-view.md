# AI 应用开发视角：工程实现与取舍

> 同一个项目，从开发视角关注的是系统边界、数据一致性、失败处理、可观测性、评测和可维护性，而不是只关注模型调用。

## 1. 当前架构

```text
React / Vite
   │ REST + Cookie Session
   ▼
FastAPI
   ├─ 认证依赖：读取 HttpOnly Cookie → 查数据库会话
   ├─ 管理接口：概览 / 订单 / 知识库
   ├─ Knowledge Service
   │    ├─ 文档解析与切片
   │    ├─ SiliconFlow BGE-M3 Embedding API
   │    └─ Chroma PersistentClient（cosine）
   ├─ Chat Service
   │    ├─ 历史裁剪与 Prompt 组装
   │    ├─ 相似度阈值与拒答
   │    ├─ DeepSeek SSE 流式生成
   │    └─ 消息、引用、工具轨迹、token、延迟持久化
   ├─ Agent Service（LangGraph）
   │    ├─ 规则意图路由
   │    ├─ 订单 / 物流 / 售后 / 工单节点
   │    └─ 工具审计与调用上限
   ├─ Operations Service
   │    ├─ 会话列表 / 详情
   │    ├─ 工单状态与备注
   │    ├─ 反馈与知识缺口
   │    └─ Token / 延迟 / 成本聚合
   ├─ 数据层：SQLAlchemy
   └─ MySQL 5.7
        ├─ 商品、订单、物流
        ├─ 知识文档、切片正文、索引状态
        └─ 会话、消息、工具日志、工单、反馈
```

M5 运营工作台已落地：

```text
运营控制台
   ├─ 会话详情与工具轨迹
   ├─ 工单队列与处理备注
   ├─ 反馈与知识缺口
   └─ Token / 延迟 / 成本洞察
```

## 2. 关键代码地图

| 模块 | 路径 | 责任 |
|---|---|---|
| 配置 | `backend/app/core/config.py` | 环境变量、API Key、数据库 URL |
| 安全 | `backend/app/core/security.py` | scrypt 密码哈希、会话令牌哈希 |
| 数据模型 | `backend/app/db/models.py` | 13 张表及关系 |
| 数据库连接 | `backend/app/db/session.py` | Engine、Session、SQLite 测试兼容 |
| 种子 | `backend/app/db/seed.py` | 幂等合成数据 |
| 认证接口 | `backend/app/api/routes/auth.py` | 登录、登出、当前用户 |
| 运营接口 | `backend/app/api/routes/admin.py` | 概览、订单、能力状态 |
| 知识接口 | `backend/app/api/routes/knowledge.py` | 文档、索引、检索 |
| 聊天接口 | `backend/app/api/routes/chat.py` | SSE、会话历史、Agent 调用与流式编排 |
| Agent 工作流 | `backend/app/services/agent.py` | LangGraph 路由、节点、上下文组合 |
| 业务工具 | `backend/app/services/tools.py` | 订单、物流、售后判断、工单、审计 |
| 运营接口 | `backend/app/api/routes/operations.py` | 会话、工单、反馈与洞察 |
| 聊天反馈 | `backend/app/api/routes/chat.py` | 反馈写入和会话反馈返回 |
| Embedding | `backend/app/services/embedding.py` | BGE-M3 批量调用与重试 |
| 向量库 | `backend/app/services/vector_store.py` | Chroma 持久化、余弦 Top-K |
| 知识编排 | `backend/app/services/knowledge.py` | 解析、切片、索引状态、检索 |
| 聊天编排 | `backend/app/services/chat.py` | Prompt、历史、引用、工具上下文、持久化 |
| LLM | `backend/app/services/llm.py` | DeepSeek 流式客户端与 usage |
| 前端 API | `frontend/src/lib/api.ts` | 统一 fetch、错误处理、类型定义 |
| SSE 客户端 | `frontend/src/lib/chatStream.ts` | ReadableStream 解析与事件分发 |
| 聊天 UI | `frontend/src/pages/ChatPage.tsx` | 流式对话、工具轨迹、来源、反馈 |
| 会话中心 | `frontend/src/pages/AdminConversationsPage.tsx` | 会话列表与筛选 |
| 会话详情 | `frontend/src/pages/AdminConversationDetailPage.tsx` | 消息、引用、轨迹和工单 |
| 工单队列 | `frontend/src/pages/AdminTicketsPage.tsx` | 工单状态、优先级、备注 |
| 运营洞察 | `frontend/src/pages/AdminInsightsPage.tsx` | 反馈、缺口、工具与成本 |
| 登录状态 | `frontend/src/auth/AuthContext.tsx` | loading/authenticated/anonymous |
| 路由保护 | `frontend/src/components/RequireAuth.tsx` | 未登录重定向 |
| 后台布局 | `frontend/src/components/AdminLayout.tsx` | 导航、管理员信息、退出 |
| 知识库 UI | `frontend/src/pages/KnowledgePage.tsx` | 上传、索引状态、检索调试 |

## 3. 技术取舍

### 3.1 服务端会话而不是 JWT

优点：

- 可以立即撤销；
- 不把用户信息暴露给前端；
- 适合单后台。

代价：

- 每次请求查询数据库；
- 需要清理过期会话。

对于这个规模，数据库查询不是瓶颈，安全与可控性更重要。

### 3.2 数据库分层：事实源与索引分离

`KnowledgeDocument` 和 `KnowledgeChunk` 是事实源。  
Chroma 中只保存 `chunk_id`、向量和检索过滤元数据。

这种设计保证：

- Chroma 损坏不丢知识；
- 可以换 Embedding 模型后重新灌库；
- 可以在 MySQL 中做文档版本管理。

### 3.3 Vite 代理而非直接打开 CORS

开发时统一使用相对 `/api`，Vite 转发到 FastAPI。  
这让浏览器把请求视为同源，Cookie 行为更接近最终部署，同时减少前端环境变量泄漏。

### 3.4 测试库与开发库分离

- 开发目标：MySQL 5.7；
- 自动化测试：内存 SQLite，追求快速反馈；
- 验收测试：真实 MySQL、真实浏览器与 API。

测试通过只能说明逻辑正确，不能替代真实 MySQL 的字符集、索引和权限验证。  
M1 已完成开发库/测试库迁移、开发库种子、接口和浏览器登录验收；M3 的真实聊天验收也使用这套 MySQL 开发库。

## 4. 数据模型里的工程细节

- `order_items` 保存商品名称、SKU 与价格快照，避免商品更新影响历史订单；
- `knowledge_chunks` 有 `document_id + chunk_index` 唯一约束；
- `chroma_id` 唯一，方便索引重建与对账；
- `vector_status` 与 `index_error` 让失败可观察、可重试；
- `messages` 已用于保存 citations、tool_trace、token、latency 和模型名；
- `tool_call_logs` 记录工具参数、结果摘要、状态和耗时；
- `handoff_tickets` 保存真实人工工单、状态、优先级和 resolution_note；
- 时间统一用 UTC 存储，API 输出带时区。

## 5. 失败与边界设计

M1/M2/M3 已处理的边界：

- 管理员密码错误返回统一 401；
- 未登录访问后台 API 返回 401；
- 前端加载态避免登录页闪屏；
- API 数据库不可用时健康检查返回 503；
- 前端请求错误统一解析后端 detail；
- 环境变量和种子数据分离；
- 上传文件类型、大小、空文档和重复内容校验；
- 缺少 Embedding Key 时返回 503，不静默失败；
- 切片失败时记录 `failed` 与 `index_error`，支持重试；
- Chroma 显式接收向量，不使用默认本地 Embedding；
- 低于相似度阈值不调用模型，返回确定性拒答；
- Prompt 禁止编造政策、订单状态、退款承诺和引用来源；
- SSE 出错、用户中止时保留已生成内容并给出错误提示；
- 工具参数由服务端意图路由控制，不让模型自由调用任意后端；
- 订单/物流只读，运单号脱敏，不返回手机号和地址；
- MySQL SELECT 设置查询超时，单轮工具调用有上限；
- 工具错误记录为失败轨迹，不伪造成功结果；
- 工单创建对已有 open 工单幂等；
- 反馈同时校验会话 public ID、消息 ID 和 assistant 角色；
- 工单更新在管理员鉴权后进行，并自动分配给当前管理员。

后续必须补充：

- 消费者会话的正式鉴权与请求限流；
- 工具的正式单元/契约测试扩展到真实 MySQL；
- 工具结果的二次确认和更细粒度权限；
- Prompt 注入和知识文档注入防护；
- 日志中的手机号、地址脱敏；
- 文档删除、版本管理和索引重建策略。

## 6. 测试策略

当前：

- pytest + FastAPI TestClient；
- 内存 SQLite；
- 认证、权限、数据接口、时间序列化；
- 切片长度、标题归属、文档列表、上传、索引/检索 Key 缺失；
- SSE meta/delta/done、拒答、RAG 回答、引用持久化、历史恢复、404；
- 订单/物流/售后/工单工具、错误轨迹、工单幂等；
- Agent SSE 工具路径、工具结果与知识引用组合；
- 反馈提交/更新、会话详情、工单更新和洞察统计；
- 前端 `tsc` 构建；
- 浏览器只读页面验收；
- 真实 SiliconFlow + DeepSeek + Chroma + MySQL 验收。

后续：

- 使用独立 MySQL 测试库补充集成测试；
- Embedding 和 DeepSeek 客户端采用 mock，避免测试依赖外部 API；
- RAG 评测使用固定问题集，记录检索与回答指标；
- 高风险工具调用增加安全测试；
- M7 做完整回归和成本记录。

## 7. M2 实现结果

已完成：

1. Chroma 1.5.9 安装到 `.venv`；
2. 显式传入硅基流动向量，避免 Chroma 默认本地 Embedding；
3. `PersistentClient` 数据目录位于项目 `data/chroma_dev`；
4. Collection 使用 cosine 距离；
5. 支持 Markdown/TXT/PDF/DOCX 解析；
6. 标题感知切片，约 600 字符、80 字符重叠、单文档最多 200 片；
7. 批量 Embedding（默认 8 条/批），429/5xx 有限重试；
8. MySQL 保存正文、索引状态和错误；Chroma 保存向量与过滤元数据；
9. 索引只处理 pending/failed 切片，重复执行不重复消耗成功切片；
10. 检索接口返回 chunk、相似度、标题、版本和来源；
11. 前端支持上传、自动索引、状态展示、手动重试和语义检索；
12. 真实 API 验收通过，后端测试 12 个全部通过。

M2 没有做文档删除和版本回滚，这是下一阶段之前明确保留的空白。

## 7.1 M3 实现结果

已完成：

1. 匿名会话：随机 `public_id`，首次提问创建，浏览器用 `sessionStorage` 恢复；
2. 会话历史从 MySQL 读取，最近 6 条进入 Prompt，单条历史做长度裁剪；
3. Top-5 检索结果经过 0.40 相似度阈值；
4. 参考资料带编号拼入 Prompt，系统提示词严格限制回答边界；
5. DeepSeek `deepseek-flash` 通过 OpenAI 兼容 API 流式生成；
6. SSE 事件：`meta`、`delta`、`done`、`error`；
7. 回答、引用、模型名、token 和延迟写入 `messages`；
8. 低相关不调用模型，直接返回确定性拒答；
9. 前端使用 `ReadableStream` 解析 SSE，不引入额外 SSE 依赖；
10. 引用展示只保留回答实际使用的来源；
11. 支持停止生成、刷新恢复、新会话和错误提示；
12. 后端测试 16 个全部通过，真实 API 与浏览器验收通过。

这里最关键的技术认知是：

> 流式输出只是传输方式；真正决定产品质量的是检索边界、Prompt 约束、拒答策略和可追溯引用。

## 7.2 M4 实现结果

已完成：

1. LangGraph 状态图：路由、订单、物流、售后、工单、检索、组合节点；
2. 规则优先的意图识别，支持从历史消息补全订单号；
3. 订单与物流工具读取 MySQL，输出脱敏结果；
4. 售后条件规则：取消/未签收/七天无理由/十五天质量问题；
5. 人工工单写入 `handoff_tickets`，同一会话 open 工单幂等；
6. 工具调用写入 `tool_call_logs`，消息写入 `tool_trace`；
7. MySQL SELECT 设置 `max_execution_time`，单轮调用有上限；
8. SSE meta/done 返回工具轨迹，前端展示工具结果和模式标签；
9. 直接回答模式不调用模型：缺失订单号、订单不存在、转人工成功；
10. 工具结果与知识来源组合，用于售后条件回答；
11. 后端测试 26 个全部通过，真实浏览器场景通过。

M4 的核心技术判断：

> 售后 Agent 的价值不在于“模型能自由调用多少接口”，而在于系统能明确哪些数据可以查、哪些动作不能做、什么时候必须交给人。

## 7.3 M5 实现结果

已完成：

1. `handoff_tickets.resolution_note` 迁移和管理员工单处理字段；
2. 消费者反馈 API，支持对 assistant 消息提交/更新赞踩；
3. 会话列表与详情，返回消息、引用、工具轨迹、token、延迟和反馈；
4. 工单列表筛选、管理员分配、状态/优先级/备注更新；
5. 运营洞察：负反馈、知识缺口、工具使用、token、延迟和估算成本；
6. 后台导航与 7/7 能力状态；
7. 前端消息反馈按钮和历史反馈恢复；
8. 后端测试扩展到 31 个；
9. 后台页面完成只读浏览器验收，写入型场景由测试库覆盖。

M5 的关键工程判断：

> 运营功能不能只是展示数据；它必须形成“发现问题 → 处理问题 → 反哺知识/评测”的闭环。

## 7.4 M6 实现结果

### 可注入的 Agent 选项

M5 之前，检索参数从 `settings` 直接读取，评测时改参数只能改环境变量。  
M6 引入：

```python
@dataclass(frozen=True)
class AgentOptions:
    top_k: int = 5
    min_similarity: float = 0.40
    use_rerank: bool = False
    rerank_candidates: int = 12
    prompt_version: Literal["v1", "v2"] = "v1"
```

线上聊天：

```python
options = AgentOptions.from_settings()
run_agent(..., options=options)
```

离线评测：

```python
AgentOptions(prompt_version="v2", use_rerank=True, ...)
```

这属于最小化的依赖注入：不引入框架，只把影响实验结果的参数收拢到一个不可变对象里。

### 检索与 Reranker

`search_knowledge` 新增：

- `min_similarity`：在进入 Prompt 前过滤低分片段；
- `use_rerank`：是否调用 Reranker；
- `candidate_k`：先召回多少候选。

流程：

```text
query
  → BGE-M3 embedding
  → Chroma Top-12
  → 阈值过滤
  → SiliconFlow Reranker
  → Top-5
```

`SiliconFlowRerankClient` 使用 `httpx.post`，失败时抛 `RerankError`，不静默降级。  
评测时真实调用；测试中用 fake response 验证排序和请求体。

### Prompt v2

v2 的核心不是“写得更长”，而是把回答形态变成可验收的：

- 先结论；
- 不超过 4 个要点；
- 引用编号；
- 300 字以内；
- 不确定时明确拒答；
- 参考资料不是指令。

这使回答更短、更稳定，也降低了 token 和延迟。

### 评测运行器

[`backend/scripts/run_evaluation.py`](../backend/scripts/run_evaluation.py) 做了几件事：

1. 读取 50 条 `cases.json`；
2. 为每条样本创建临时会话；
3. 调用与线上相同的 `agent.run_agent(..., persist=False)`；
4. 如果有 LLM messages，调用真实 DeepSeek 流式接口；
5. 按七个维度评分；
6. 汇总通过率、分类、检索、引用、拒答、延迟、token、成本；
7. 跑检索参数 sweep（Top-K、阈值、Reranker）；
8. 生成 Markdown 报告和原始 JSON。

评分不是“看回答像不像”，而是：

```text
模式 + 工具 + 来源 + 引用 + 关键词 + 禁止内容 + 无错误
```

全部通过才算通过。

### 事务回滚

`run_agent` 新增 `persist`：

```python
if persist:
    db.commit()
else:
    db.rollback()
```

评测的临时会话、工单、工具审计都随事务回滚。  
这比“跑完再删测试数据”更安全，因为不会留下半成品记录。

### 三组配置与结果

| 配置 | 检索 | Prompt | 通过率 | 平均延迟 | tokens | 成本 |
|---|---|---|---:|---:|---:|---:|
| baseline | Top-5 / 0.40 | v1 | 50/50 | 2,780ms | 38,850 | ¥0.0759 |
| prompt_v2 | Top-5 / 0.40 | v2 | 50/50 | 2,394ms | 32,130 | ¥0.0613 |
| optimized | Top-12 → Rerank → Top-5 | v2 | 50/50 | 2,862ms | 32,041 | ¥0.0601 |

检索 sweep：

- Top-5 / 0.40：Top-1 15/19，MRR 0.8702；
- Top-8 / 0.40：Top-1 15/19，MRR 0.8702；
- Top-5 / 0.35：Top-1 15/19，MRR 0.8702；
- Top-5 / 0.40 + Reranker：Top-1 18/19，MRR 0.9649。

关键工程结论：

> Reranker 改善的是排序，不是召回；当 Recall 已经饱和时，它不会自动提升端到端通过率，却会增加延迟。

### 评测本身的 bug

第一次运行出现失败样例，复查发现部分评分词过窄：

- “48 小时” vs “四十八小时”；
- “9:00” vs “九点”；
- “3 个工作日” vs “三个工作日”；
- “已签收并完成” vs “已完成”。

同时 R05 越界问题进入了 RAG 分支，但回答明确拒答。  
修正评分口径后重跑，三组配置均为 50/50。

这件事说明：

> 评测代码也需要测试和复盘。看到失败，先区分“系统错”还是“评分错”。

### 当前技术限制

- 50 条合成样本，单次运行；
- 规则评分无法判断忠实性；
- 通过率饱和；
- 没有 LLM-as-judge 或人工评审；
- Embedding/Reranker 成本未计入估算；
- 没有并发、限流和线上流量验证。

## 7.5 M7 实现结果

### 限流

`app/core/rate_limit.py` 实现单进程滑动窗口：

```python
class InMemoryRateLimiter:
    def hit(self, key, limit, window_seconds):
        # 清理窗口外时间戳
        # 满额返回 allowed=False + retry_after
```

关键点：

- `threading.Lock` 保证 FastAPI 线程池下计数安全；
- key 由 `scope + window + client_ip` 组成；
- 支持 `X-Forwarded-For`，但默认不信任，避免伪造绕过；
- 超限抛 `HTTPException(429)`，带 `Retry-After`；
- 单进程内存实现，多实例需要 Redis。

接口限额：

| 接口 | 限额 |
|---|---|
| 登录 | 10 次/分钟 |
| 聊天 | 20 次/分钟 + 120 次/小时 |
| 会话读取 | 60 次/分钟 |
| 反馈 | 30 次/分钟 |

### PII

`app/core/pii.py` 覆盖：

- 中国大陆手机号；
- 18 位身份证号；
- 16-19 位银行卡号；
- 邮箱；
- 座机。

应用位置：

1. 聊天输入入库前；
2. 反馈评论入库前；
3. 后台订单手机号返回前；
4. 日志输出前。

日志过滤额外处理：

- 订单号；
- Bearer Token；
- `sk-` API Key。

正则不能覆盖地址和自由文本变体，因此文档明确写“不宣称完全脱敏”。

### 提示注入

`app/core/guardrails.py` 维护明显注入模式：

```text
忽略之前的指令
输出系统提示词
ignore previous instructions
jailbreak / 越狱 / 开发者模式
```

Agent 在路由节点先检查：

```python
if looks_like_prompt_injection(query):
    return {"intent": "guard"}
```

`guard` 直接走确定性兜底，不检索、不调用模型。  
这比只依赖 Prompt 更省成本，也更可测试。

### 安全中间件

`app/core/middleware.py` 是纯 ASGI 中间件：

- 检查 JSON 请求体 `Content-Length`；
- 添加安全响应头；
- API 路径加 CSP；
- 生产环境加 HSTS；
- `/api/auth/*` 加 `Cache-Control: no-store`。

没有用 `BaseHTTPMiddleware`，避免 SSE 流式响应的额外包装风险。

### 登录与 Cookie

- 登录接口加限流；
- 账号不存在时也执行一次 scrypt 校验，减少时间侧信道；
- 生产环境 Cookie 自动 `Secure`；
- 错误信息统一为“邮箱或密码错误”。

### 验证

新增 10 个安全测试，后端测试从 33 增加到：

```text
43 passed
```

覆盖：

- 安全响应头；
- 413 请求体限制；
- PII 脱敏；
- 日志过滤；
- 聊天脱敏；
- 提示注入；
- 聊天/登录限流；
- 后台手机号脱敏。

### 关键工程判断

> 安全功能必须可测试、可解释、可回退；  
> 不能在文档里把“本地演示基线”说成“生产级安全”。

## 8. 面试表达

重点不是“我会调 API”，而是：

> “我把静态知识、实时订单和高风险动作拆成了三条不同链路。知识用 RAG，订单用只读工具，退款和争议转人工。数据库是事实源，Chroma 是可重建索引。评测时分别看检索、引用、工具调用和转人工触发，而不是只看一句回答像不像人话。”

如果对方追问优化结果，可以补：

> “在 50 条固定样本上，Prompt v2 把 tokens 降低约 17%、平均延迟降低约 14%、估算成本降低约 19%，通过率不变；Reranker 把检索 MRR 从 0.87 提升到 0.96，但增加约 20% 延迟，端到端通过率没有提升，所以生产默认没有开启它。”

同时要能主动说出限制：

- 已完成 MySQL 5.7 开发/测试库迁移与接口验收，但还没有真实业务流量；
- Chroma、BGE-M3、DeepSeek 流式问答和 Agent 业务工具已接入；
- 消费者会话使用随机 public ID，不是正式鉴权；虽有单进程限流，但没有账号体系和 CSRF Token；
- 工单处理 UI 已完成，但还没有角色权限、SLA 和评论线程；
- 已有 50 条离线评测，但样本是合成的、规模小、只有单次运行，不能等同于真实业务指标；
- 多 Agent 不是默认选择，当前场景确定性更重要。

## 9. 下一阶段的技术验收

M6 已完成：

- 50 条固定评测集覆盖知识、订单、物流、售后、转人工、拒答和多轮；
- 三组配置各 50 条真实运行；
- 检索 Top-1/MRR、引用、工具、拒答、Token、延迟和成本可复现；
- Prompt v2 设为生产默认，Reranker 保留可选；
- 评测事务回滚，不污染演示库。

M7 已完成：

- 登录/聊天/读取/反馈限流，429 + `Retry-After`；
- PII 入库前脱敏与日志过滤；
- 明显提示注入在路由层拦截；
- 安全响应头、CSP、请求体限制、CORS 收紧和生产 Cookie Secure；
- 43 个后端测试通过；
- 演示指南与最终文档就绪。

后续可选：

- Redis 共享限流，支持多实例；
- 角色权限、CSRF Token、完整审计查询；
- 更难的评测集、人工评审和线上指标；
- HTTPS、域名、隐私合规和渗透测试。
