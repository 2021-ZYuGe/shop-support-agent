# AI 应用开发视角：工程实现与取舍

> 同一个项目，从开发视角关注的是系统边界、数据一致性、失败处理、可观测性、评测和可维护性，而不是只关注模型调用。

## 1. 当前架构

```text
React / Vite
   │ REST + Cookie Session
   ▼
FastAPI
   ├─ 认证依赖：读取 HttpOnly Cookie → 查数据库会话
   ├─ 管理接口：概览 / 订单
   ├─ 数据层：SQLAlchemy
   └─ MySQL 5.7
        ├─ 商品、订单、物流
        ├─ 知识文档、切片正文
        └─ 会话、消息、工具日志、工单、反馈
```

M2 后增加：

```text
FastAPI
   ├─ SiliconFlow Embedding API
   ├─ Chroma PersistentClient
   └─ Knowledge Index Service
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
| 运营接口 | `backend/app/api/routes/admin.py` | 概览、订单 |
| 前端 API | `frontend/src/lib/api.ts` | 统一 fetch、错误处理、类型定义 |
| 登录状态 | `frontend/src/auth/AuthContext.tsx` | loading/authenticated/anonymous |
| 路由保护 | `frontend/src/components/RequireAuth.tsx` | 未登录重定向 |
| 后台布局 | `frontend/src/components/AdminLayout.tsx` | 导航、管理员信息、退出 |

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
M2 的 Chroma 中只保存 `chunk_id`、向量和检索过滤元数据。

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
- `messages` 预留 citations、token、latency，M3 可直接记录；
- `tool_call_logs` 预留参数与结果摘要，M4 记录工具链；
- `handoff_tickets` 与 `conversations` 解耦，支持一次会话多次转接；
- 时间统一用 UTC 存储，API 输出带时区。

## 5. 失败与边界设计

M1 已经处理的边界：

- 管理员密码错误返回统一 401；
- 未登录访问后台 API 返回 401；
- 前端加载态避免登录页闪屏；
- API 数据库不可用时健康检查返回 503；
- 前端请求错误统一解析后端 detail；
- 环境变量和种子数据分离。

后续必须补充：

- API Key 缺失时 AI 功能明确降级；
- 工具参数校验与白名单；
- 工具超时与最多调用次数；
- 人工工单创建失败时的回退；
- Prompt 注入和知识文档注入防护；
- 上传文件大小/类型校验；
- 日志中的手机号、地址脱敏。

## 6. 测试策略

当前：

- pytest + FastAPI TestClient；
- 内存 SQLite；
- 认证、权限、数据接口、时间序列化；
- 前端 `tsc` 构建；
- 浏览器端到端手工验收。

后续：

- 使用独立 MySQL 测试库补充集成测试；
- Embedding 和 DeepSeek 客户端采用 mock，避免测试依赖外部 API；
- RAG 评测使用固定问题集，记录检索与回答指标；
- 高风险工具调用增加安全测试；
- M7 做完整回归和成本记录。

## 7. M2 技术计划

1. 安装 Chroma 到 `.venv`；
2. 显式使用硅基流动向量，关闭 Chroma 默认本地 Embedding；
3. 使用 `PersistentClient`，数据目录放在项目 `data/`；
4. Collection 距离度量使用 cosine；
5. 文档解析、切片、批量 Embedding；
6. MySQL 保存正文和状态，Chroma 保存向量；
7. 实现重建索引接口；
8. 检索调试接口返回 chunk、相似度、文档标题和版本；
9. 记录 Embedding 调用量和失败重试。

## 8. 面试表达

重点不是“我会调 API”，而是：

> “我把静态知识、实时订单和高风险动作拆成了三条不同链路。知识用 RAG，订单用只读工具，退款和争议转人工。数据库是事实源，Chroma 是可重建索引。评测时分别看检索、引用、工具调用和转人工触发，而不是只看一句回答像不像人话。”

同时要能主动说出限制：

- 已完成 MySQL 5.7 开发/测试库迁移与接口验收，但还没有真实业务流量；
- 尚未接入 Chroma 和模型 API；
- 没有真实业务指标，当前数据为合成；
- 多 Agent 不是默认选择，当前场景确定性更重要。

## 9. 下一阶段的技术验收

M2 不只验收“能搜到”：

- Chroma 是否持久化到 D 盘；
- 是否显式传入了硅基流动 Embedding，未触发本地模型下载；
- 相同文档重复入库是否幂等；
- 删除/重建索引是否能从 MySQL 恢复；
- 检索结果是否包含可追溯的文档和切片信息；
- 免费 API 限速和失败时是否有清晰错误。
