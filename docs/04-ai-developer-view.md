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
   ├─ 数据层：SQLAlchemy
   └─ MySQL 5.7
        ├─ 商品、订单、物流
        ├─ 知识文档、切片正文、索引状态
        └─ 会话、消息、工具日志、工单、反馈
```

M3/M4 后增加：

```text
FastAPI
   ├─ DeepSeek（OpenAI 兼容接口）
   ├─ LangGraph 状态图
   └─ 订单/物流/售后工具
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
| Embedding | `backend/app/services/embedding.py` | BGE-M3 批量调用与重试 |
| 向量库 | `backend/app/services/vector_store.py` | Chroma 持久化、余弦 Top-K |
| 知识编排 | `backend/app/services/knowledge.py` | 解析、切片、索引状态、检索 |
| 前端 API | `frontend/src/lib/api.ts` | 统一 fetch、错误处理、类型定义 |
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
M1 已完成开发库/测试库迁移、开发库种子、接口和浏览器登录验收。

## 4. 数据模型里的工程细节

- `order_items` 保存商品名称、SKU 与价格快照，避免商品更新影响历史订单；
- `knowledge_chunks` 有 `document_id + chunk_index` 唯一约束；
- `chroma_id` 唯一，方便索引重建与对账；
- `vector_status` 与 `index_error` 让失败可观察、可重试；
- `messages` 预留 citations、token、latency，M3 可直接记录；
- `tool_call_logs` 预留参数与结果摘要，M4 记录工具链；
- `handoff_tickets` 与 `conversations` 解耦，支持一次会话多次转接；
- 时间统一用 UTC 存储，API 输出带时区。

## 5. 失败与边界设计

M1/M2 已处理的边界：

- 管理员密码错误返回统一 401；
- 未登录访问后台 API 返回 401；
- 前端加载态避免登录页闪屏；
- API 数据库不可用时健康检查返回 503；
- 前端请求错误统一解析后端 detail；
- 环境变量和种子数据分离；
- 上传文件类型、大小、空文档和重复内容校验；
- 缺少 Embedding Key 时返回 503，不静默失败；
- 切片失败时记录 `failed` 与 `index_error`，支持重试；
- Chroma 显式接收向量，不使用默认本地 Embedding。

后续必须补充：

- 工具参数校验与白名单；
- 工具超时与最多调用次数；
- 人工工单创建失败时的回退；
- Prompt 注入和知识文档注入防护；
- 日志中的手机号、地址脱敏；
- 文档删除、版本管理和索引重建策略。

## 6. 测试策略

当前：

- pytest + FastAPI TestClient；
- 内存 SQLite；
- 认证、权限、数据接口、时间序列化；
- 切片长度、标题归属、文档列表、上传、索引/检索 Key 缺失；
- 前端 `tsc` 构建；
- 浏览器端到端手工验收；
- 真实 SiliconFlow + Chroma + MySQL 验收。

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

## 8. 面试表达

重点不是“我会调 API”，而是：

> “我把静态知识、实时订单和高风险动作拆成了三条不同链路。知识用 RAG，订单用只读工具，退款和争议转人工。数据库是事实源，Chroma 是可重建索引。评测时分别看检索、引用、工具调用和转人工触发，而不是只看一句回答像不像人话。”

同时要能主动说出限制：

- 已完成 MySQL 5.7 开发/测试库迁移与接口验收，但还没有真实业务流量；
- Chroma 和硅基流动 Embedding 已接入，DeepSeek 对话与 Agent 尚未接入；
- 没有真实业务指标，当前检索评测来自合成数据；
- 多 Agent 不是默认选择，当前场景确定性更重要。

## 9. 下一阶段的技术验收

M3 要继续验证：

- 检索片段是否能正确拼入 Prompt；
- DeepSeek 是否只使用给定知识回答；
- 回答中的引用是否对应真实命中片段；
- 无依据或低相关时是否能拒答/转人工；
- SSE 流式输出是否完整、可中断、可保存；
- token、延迟和成本是否被记录；
- 20 条初版评测样本能否稳定复现。
