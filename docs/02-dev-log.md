# 开发日志

按时间顺序记录实际构建过程、验证结果、问题和下一步。  
面向工程复盘，不替代 `01-learning-journey.md` 的概念讲解。

---

## 2026-10-31 · M1 工程骨架与数据库（已完成）

### 本轮目标

把仓库从空项目变成可运行的全栈底座：

- Vite + React 前端；
- FastAPI 后端；
- MySQL 表结构和迁移；
- 管理员登录；
- 虚构商品、订单、知识文档种子；
- 运营首页和订单台账；
- 学习文档、方案和双视角复盘骨架。

本轮不调用任何 AI API。

### 环境与路径

| 项 | 结果 |
|---|---|
| Python | 新增 Python 3.12.10 到 `D:\python\python3.12`，保留原 3.9.6 |
| 虚拟环境 | `D:\videcoding\shop-support-agent\.venv` |
| Node | 已有 22.20.0，满足 Vite 要求，未升级、未删除 |
| MySQL | 已有 MySQL 5.7.31 服务运行中 |
| Docker | 未安装 |
| 本地验收库 | `data/m1_smoke.db`（临时 SQLite，仅用于先行验收） |
| 依赖缓存 | `D:\dev\cache\pip`、`D:\dev\cache\npm` |

安装 Python 时，Git Bash 将 `/quiet` 参数错误转换成路径，首次安装失败。  
检查安装日志后，改用 PowerShell `Start-Process` 传入参数数组，安装成功并验证：

```text
Python 3.12.10
pip 25.0.1
```

### 后端

新增内容：

- `backend/app/main.py`：FastAPI 应用、CORS 和根路由；
- `backend/app/core/config.py`：环境变量和项目路径；
- `backend/app/core/security.py`：scrypt 密码哈希、随机会话令牌；
- `backend/app/db/models.py`：13 张业务表；
- `backend/app/db/session.py`：SQLAlchemy Engine 与 Session；
- `backend/app/db/seed.py`：幂等虚构数据；
- `backend/app/api/`：健康检查、认证、运营概览和订单接口；
- `backend/alembic/`：初始迁移；
- `backend/tests/`：7 个自动化测试。

关键设计：

- 会话令牌只把 SHA-256 哈希写入数据库；
- 浏览器 Cookie 使用 HttpOnly、SameSite=Lax；
- 管理员密码使用 scrypt 随机盐；
- 订单项保存商品名称、SKU 和成交价快照；
- MySQL 是事实源，下一阶段的 Chroma 只做可重建索引；
- 时间统一存 UTC，API 返回带时区的 ISO 字符串。

### 数据模型

共 13 张表：

1. `admins`
2. `admin_sessions`
3. `products`
4. `orders`
5. `order_items`
6. `shipments`
7. `knowledge_documents`
8. `knowledge_chunks`
9. `conversations`
10. `messages`
11. `tool_call_logs`
12. `handoff_tickets`
13. `feedback`

迁移文件：

- `backend/alembic/versions/577954661af3_initial_schema.py`

### 种子数据

虚构店铺：青禾生活。

- 6 个商品；
- 8 个订单：待发货、运输中、已签收、已完成、已取消；
- 3 份售后知识文档；
- 9 个知识切片，当前索引状态均为 `pending`；
- 所有客户姓名、手机号、地址为合成数据。

默认演示管理员：

```text
邮箱：admin@qinghe.local
密码：ChangeMe123!
```

密码可以通过 `.env` 的 `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` 修改。  
种子脚本可以重复执行，不重复插入商品、订单和文档。

### 前端

新增页面：

- `/`：消费者品牌首页与能力预览；
- `/admin/login`：运营登录；
- `/admin`：运营概览；
- `/admin/orders`：订单台账。

交互：

- 登录后通过 HttpOnly Cookie 维持会话；
- 未登录访问后台会自动跳回登录页；
- 登录成功回到原目标页；
- 概览展示订单、商品、知识切片和待处理工单；
- 能力进度展示 M1 已完成与后续 M2/M3/M4 计划；
- 退出登录会同时删除服务端会话。

开发代理：

```text
Vite /api → http://127.0.0.1:8000
```

### 验证结果

#### 自动化测试

```text
7 passed in 0.45s
```

覆盖：

- 健康检查；
- 登录错误密码；
- 登录、当前用户、退出登录；
- 未登录访问运营接口；
- 概览指标与最近订单；
- 订单列表；
- UTC 时间序列化。

#### 前端

```text
tsc -b && vite build → 成功
```

产物体积：

- JS 约 296 KB（gzip 约 94 KB）
- CSS 约 29 KB（gzip 约 6.6 KB）

#### 浏览器

实际走通：

1. 打开消费者首页；
2. 点击运营后台；
3. 一键填入演示账号并登录；
4. 查看概览的 8 个订单、6 个商品、9 个知识切片；
5. 进入订单台账，看到 8 条合成订单；
6. 退出登录；
7. 未登录直接访问 `/admin`，自动跳转回登录页。

视觉验收：

- 1440px 桌面；
- 390px 手机；
- 截图保存在 `docs/images/`。

### 补充验收：MySQL 真库联调

`.env` 配置完成后，使用专用账号 `shop_support_app` 完成真实 MySQL 验收。

连接信息（不记录密码）：

```text
MySQL 5.7.31
开发库：shop_support_dev
测试库：shop_support_test
字符集：utf8mb4_unicode_ci
引擎：InnoDB
```

执行结果：

- 开发库 Alembic 迁移成功；
- 测试库 Alembic 迁移成功；
- 开发库种子脚本执行成功；
- 开发库共 14 张表（13 张业务表 + `alembic_version`）；
- 数据：1 个管理员、6 个商品、8 个订单、11 条订单明细、5 条物流、3 份知识文档、9 个知识切片。

真实 MySQL 接口验收：

- `/api/health` 返回 `database=connected`；
- 管理员登录成功，会话写入 `admin_sessions`；
- `/api/admin/overview` 返回真实 MySQL 指标与最近订单；
- 登出成功，服务端会话被删除；
- 浏览器登录后台成功，页面显示 MySQL 数据，UTC 时间正确转为本地时间。

至此 M1 的数据库验收项关闭。

### 已知问题与未完成项

1. **Chroma 尚未安装**
   - 按计划在 M2 安装到项目虚拟环境；
   - M1 不下载模型，也不调用 Embedding API。

2. **AI API 尚未接入业务**
   - DeepSeek 和硅基流动 Key 只放 `.env`；
   - 本轮不调用 AI API。

3. **公网部署**
   - 本阶段不做，避免引入服务器和 Docker；
   - 先完成本地可演示作品。

### 本轮功能在项目中的作用

M1 不是“先做一个空壳页面”，而是在为后续 AI 链路准备可信的业务底座：

- 认证保护运营数据；
- 订单表为 M4 工具调用提供真实结构；
- 知识文档和切片表为 M2 入库提供事实源；
- 会话、消息和工具日志表为 M3/M4 留好持久化位置；
- 运营后台为 M5 的会话与工单管理打基础。

### 下一步：M2

计划完成知识库入库与检索调试：

1. 在项目虚拟环境安装 Chroma；
2. 实现 Markdown / TXT 文档解析和切片；
3. 调用硅基流动 `BAAI/bge-m3` 生成向量；
4. 把 chunk ID、向量和基础元数据写入 Chroma；
5. 把文档和切片正文写入 MySQL；
6. 新增后台知识库上传与索引状态页；
7. 新增检索调试页，展示命中片段、相似度和引用元数据；
8. 补充测试和开发日志；
9. 验证 Chroma 的默认本地 Embedding 没有被触发。

M2 开工前需要：

- 项目 `.env` 中配置 `SILICONFLOW_API_KEY`；
- 部署 Chroma 的所有数据目录保持在 D 盘项目内；
- 使用已经验收的 MySQL 开发库继续开发。

---

## 2026-10-31 · M2 知识库与向量检索（已完成）

### 本轮目标

把静态售后知识接入 RAG 数据链路：

- 文档上传与解析；
- 标题/段落感知切片；
- 硅基流动 BGE-M3 Embedding；
- Chroma 本地向量索引；
- 索引状态与失败重试；
- 后台知识库页与语义检索调试；
- 为 M3 的 DeepSeek 问答准备可复用上下文。

### 依赖与安装

新增：

```text
chromadb==1.5.9
```

Chroma 安装在项目虚拟环境中，数据目录位于 D 盘项目目录，不启动独立服务、不使用 Docker。

安装 Chroma 时带入了 ONNX Runtime、tokenizers 等依赖，但本项目没有调用 Chroma 默认 Embedding Function，也没有下载或运行本地向量模型。向量全部来自硅基流动 API。

### 后端实现

新增：

- `backend/app/services/embedding.py`：硅基流动 BGE-M3 客户端，批量 Embedding、429/5xx 重试和错误处理；
- `backend/app/services/vector_store.py`：Chroma `PersistentClient`、cosine 集合、显式向量 upsert 和 Top-K 查询；
- `backend/app/services/knowledge.py`：文档解析、切片、索引状态、检索编排；
- `backend/app/api/routes/knowledge.py`：知识文档列表、上传、索引、检索接口；
- `backend/app/schemas/knowledge.py`：知识库接口数据模型。

配置新增：

- `CHROMA_PATH`；
- `CHROMA_COLLECTION`；
- `UPLOAD_DIR`；
- `EMBEDDING_BATCH_SIZE`；
- `EMBEDDING_TIMEOUT_SECONDS`；
- `MAX_UPLOAD_SIZE_MB`。

数据库迁移：

- `cb67c75b7d70_add_knowledge_chunk_index_error.py`
- 为 `knowledge_chunks` 增加 `index_error` 字段。
- 开发库和测试库均已升级。

### 知识入库规则

- 支持 `.md`、`.markdown`、`.txt`、`.pdf`、`.docx`；
- 单文件最大 10MB；
- 中文切片目标约 600 字符，重叠 80 字符；
- 单个文档最多 200 个切片；
- 相同内容通过 SHA-256 去重；
- 文件原文保存在 `data/uploads`，不提交 Git；
- MySQL 保存文档与切片正文；Chroma 保存向量和检索元数据。

### 索引与检索

索引接口只处理 `pending` 和 `failed` 切片。  
失败切片会记录 `index_error`，可以再次点击“建立索引”重试。

搜索流程：

```text
query → BGE-M3 查询向量 → Chroma Top-K → 回 MySQL 取正文 → 返回相似度与来源
```

M2 仍只做纯向量检索，尚未加入 Reranker、混合检索和相似度阈值。

### 真实 API 验收

硅基流动连通性：

- 模型：`BAAI/bge-m3`
- HTTP 200
- 维度：1024

种子知识库索引：

- 3 份文档，9 个切片；
- 全部成功写入 Chroma；
- 文档索引状态均为 `indexed`。

查询结果（Top-1）：

| 查询 | Top-1 命中 | 相似度 |
|---|---|---:|
| 七天无理由退货怎么退 | 七天无理由退货 | 0.774 |
| 物流一直不更新怎么办 | 物流异常 | 0.690 |
| 发票怎么开 | 发票申请 | 0.693 |

浏览器实际上传：

- 文件：`docs/examples/member-policy.md`
- 自动切成 3 个切片并建立索引；
- 当前开发库：4 份文档、12 个切片，全部 `indexed`；
- 查询“会员积分怎么抵扣？”Top-1 为“积分抵扣”，相似度 73.2%。

### 前端

新增知识库工作台：

- 文档上传表单；
- 文件类型、标题、版本、生效日期；
- 上传后自动调用索引；
- 索引统计与文档状态表；
- 单份文档的索引/重试按钮；
- 语义检索调试，显示 Top-K、相似度、原文片段和 chunk 来源；
- 顶部运营概览同步展示 4/6 能力已完成。

截图：

- `docs/images/m2-knowledge.png`
- `docs/images/m2-dashboard.png`

### 验证结果

- 后端测试：**12 passed**；
- 前端 TypeScript 构建通过；
- lint：0 errors，5 个 React 建议级警告；
- 真实 MySQL + Chroma + 硅基流动 API 联调通过；
- 浏览器完整走通上传、自动索引、检索和结果展示。

### 已知限制

1. 扫描版 PDF 不做 OCR；
2. 暂无文档删除和知识版本回滚；
3. 暂无 Reranker、关键词混合检索和相似度阈值；
4. Chroma 是本地索引，部署时必须保证数据目录持久化；
5. 免费 Embedding 有速率/额度限制，重复索引会消耗额度；
6. 公网部署和 Docker 仍不在本阶段范围。

### 下一步：M3

M3 计划：

1. 配置 `DEEPSEEK_API_KEY`；
2. 把用户问题、历史消息和检索片段组装成 Prompt；
3. 调用 DeepSeek `deepseek-flash` 流式生成；
4. 回答展示引用来源；
5. 证据不足时拒答或建议转人工；
6. 记录 token、延迟和费用；
7. 建立 20 条左右的问答评测样本；
8. 验证 SSE 流式输出、引用和错误降级。

M3 开始需要 DeepSeek API Key；硅基流动 Key 已经在 M2 使用。

---

## 2026-10-31 · M3 RAG 问答与引用（已完成）

### 本轮目标

把 M2 的检索能力接入消费者问答：

- 匿名会话创建与恢复；
- 检索 Top-K 售后知识；
- DeepSeek 流式回答；
- 内联引用与引用资料卡片；
- 低相关拒答/转人工提示；
- 保存消息、引用、token 和延迟；
- 完整的消费者聊天页面。

### 依赖验证

DeepSeek 兼容 OpenAI SDK，使用：

```text
model: deepseek-flash
base_url: https://api.deepseek.com
stream: true
stream_options.include_usage: true
```

实际验证：

- 流式请求成功；
- 返回多条 delta；
- 最终返回 usage；
- 配置中的 Key 只存在于本地 `.env`。

### 后端实现

新增：

- `backend/app/api/routes/chat.py`：SSE 聊天接口、会话历史接口；
- `backend/app/schemas/chat.py`：会话、消息、引用结构；
- `backend/app/services/llm.py`：DeepSeek 流式客户端与 usage 事件；
- `backend/app/services/chat.py`：Prompt、历史裁剪、引用拼装、消息保存、SSE 编码。

路由：

- `POST /api/chat/stream`
- `GET /api/chat/conversations/{public_id}`

本轮没有新增数据库表；沿用 M1 的 `conversations` 和 `messages`。

### 问答策略

- `RAG_TOP_K=5`；
- `RAG_MIN_SIMILARITY=0.40`；
- 无高于阈值的结果时，不调用 DeepSeek，返回固定拒答文案；
- 有结果时，将历史、资料编号和用户问题组装后调用 `deepseek-flash`；
- 系统提示词禁止编造政策、订单状态、退款承诺和引用来源；
- SSE 的 meta 事件先返回会话 ID、模式与来源；
- 流式 delta 逐段推送；
- 完成后保存助手消息和 citations，并返回 done；
- 失败通过 error 事件返回，已生成的部分会尽力保存。

### 阈值校准

使用真实 Embedding + Chroma 抽样：

| 查询 | 最高相似度 | 行为 |
|---|---:|---|
| 请讲一个笑话 | 0.389 | 低于阈值，拒答 |
| 你们支持比特币付款吗 | 0.516 | 进入模型，由 Prompt 判断资料不足 |
| 我的订单 QH20261031007 到哪了 | 0.645 | 进入模型，但明确说明无法查具体订单 |
| 七天无理由退货怎么退 | 0.774 | 正常 RAG 回答 |

### 前端实现

新增消费者聊天页 `/chat`：

- 首页“开始咨询”直接进入；
- 流式回答与停止生成；
- 引用资料折叠卡片；
- 回答实际引用到的来源才展示；
- 刷新页面恢复当前会话；
- 新对话清除当前 local/session 会话；
- 无关问题展示“知识库未命中”；
- 错误提示、输入长度限制和移动端布局。

新增 `frontend/src/lib/chatStream.ts`：原生 fetch + ReadableStream 的 SSE 解析。

### 真实验收

真实 DeepSeek + Chroma + MySQL：

1. “会员积分怎么抵扣？”
   - RAG 回答；
   - 引用 1 条来源；
   - 656 prompt + 129 completion tokens；
   - 约 1.6 秒。
2. “我的订单 QH20261031007 到哪了？”
   - 不编造物流状态；
   - 说明知识库没有该订单实时信息；
   - 建议转人工。
3. “请讲一个笑话”
   - 检索结果低于阈值；
   - 知识库未命中兜底；
   - 不调用生成模型。
4. 浏览器刷新后恢复会话；
5. 新对话清空界面；
6. 引用资料展开后显示原文与相似度。

自动化测试：

```text
16 passed
```

新增覆盖：

- SSE meta/delta/done；
- 无来源 fallback；
- RAG 流式回答；
- 引用持久化；
- 会话历史恢复；
- 未知会话 404。

截图：

- `docs/images/m3-chat.png`
- `docs/images/m3-chat-mobile.png`
- `docs/images/m3-dashboard.png`
- `docs/images/m3-landing.png`

### 已知限制

1. 消费者会话是随机 public ID，不是正式登录认证；
2. `/api/chat/stream` 暂无请求限流，不能直接公开部署；
3. 具体订单和物流状态尚未接入工具，只能安全拒答/建议转人工；
4. 还没有真正可创建的工单，M3 只是文字建议；
5. 没有用户反馈按钮和低分回答闭环；
6. 没有系统化评测集，当前质量来自抽样验收。

### 下一步：M4

M4 计划：

1. 用 LangGraph 建立确定性工作流；
2. 意图路由：知识问答、订单、物流、售后、转人工；
3. 只读订单和物流工具；
4. 售后退换条件判断；
5. 创建人工工单；
6. 工具参数校验、超时、最多调用次数与审计日志；
7. 把工具结果、知识引用一起合成最终回答；
8. 更新聊天页支持工具信息与转人工结果；
9. 补充 Agent 场景测试和开发文档。

M4 开始前不需要新的外部 Key，现有 DeepSeek 和硅基流动 Key 已足够。

---

## 2026-10-31 · M4 Agent 业务工具与人工兜底（已完成）

### 本轮目标

让聊天从“知识回答”升级为有边界的业务处理：

- LangGraph 意图路由与工具节点；
- 查询订单和物流；
- 判断售后退换条件；
- 创建人工工单；
- 将工具结果与知识引用组合；
- 在聊天中展示工具轨迹；
- 审计、超时和调用次数限制。

### 依赖与数据结构

新增依赖：

```text
langgraph==1.2.19
```

新增迁移：

- `578f969917f3_add_message_tool_trace.py`
- 为 `messages` 增加 `tool_trace` JSON 字段。
- 开发库和测试库均已升级。

新增配置：

- `TOOL_TIMEOUT_MS=5000`
- `MAX_TOOL_CALLS_PER_TURN=3`

### 后端实现

新增：

- `backend/app/services/tools.py`：订单、物流、售后条件、人工工单；
- `backend/app/services/agent.py`：LangGraph 状态图与意图路由；
- `backend/app/api/routes/chat.py`：改为调用 Agent 工作流；
- `backend/app/services/chat.py`：Prompt 支持工具结果；
- `backend/app/schemas/chat.py`：返回工具轨迹。

工作流：

```text
router
  ├─ order_lookup ─────── compose
  ├─ logistics_lookup ─── compose
  ├─ after_sales_lookup → retrieve → compose
  ├─ handoff ───────────── compose
  ├─ missing_order ─────── compose
  └─ knowledge ─→ retrieve → compose
```

路由方式：

- 规则识别转人工、售后、订单、物流和缺槽位；
- 订单号从当前消息或历史消息提取；
- 多轮里用户只补订单号时，会根据上下文恢复上一个订单/物流意图；
- 不依赖模型自由决定调用哪个工具。

### 工具与安全

订单与物流：

- 从 MySQL 读取；
- 不返回手机号和地址；
- 运单号做掩码；
- 只读，不修改订单。

售后判断：

- 取消、未签收、七天无理由、十五天质量问题窗口；
- 输出是否符合、原因、签收天数、所需凭证和边界说明；
- 不执行真实退款或修改订单。

人工工单：

- 创建 `handoff_tickets`；
- 投诉/退款/质量等问题设为 high；
- 同一会话存在 open 工单时复用，避免重复创建；
- 会话状态更新为 `handed_off`。

安全限制：

- 工具参数由服务端代码控制；
- MySQL SELECT 设置 `max_execution_time`；
- 单轮工具调用上限；
- 每次工具调用写 `tool_call_logs`；
- 工具错误会形成 error trace，不伪造成功结果。

### 前端

聊天页新增：

- 工具调用折叠卡片：工具名、摘要、耗时、成功/失败状态；
- 模式标签：工具辅助、已转人工、需要补充信息；
- 工具轨迹随会话恢复；
- 建议问题新增演示订单查询；
- 侧边边界说明更新为“可查订单/物流、可建工单，但不自动退款”。

运营概览：

- 6/6 能力已就绪；
- 待处理工单真实计数；
- 当前里程碑切换为 M4 Agent 业务工具。

### 真实验收

真实 MySQL + Chroma + SiliconFlow + DeepSeek：

1. “查一下订单 QH20261028003 的物流”
   - 工具：`lookup_shipment`
   - 返回顺丰已签收和最新动态
   - 453 + 130 tokens / 约 1.3s
2. “订单 QH20261028003 有划痕能退吗？”
   - 工具：`check_after_sales`
   - 结合政策引用给出条件判断
   - 838 + 433 tokens / 约 3.2s
3. “我要转人工处理退款”
   - 工具：`create_handoff`
   - 创建人工工单 #1，优先级 high
   - 会话状态 handed_off
4. “我的订单到哪了”
   - 不调用生成模型，直接追问订单号

数据库核验：

- 3 条工具调用日志；
- 1 张人工工单；
- 4 条助手消息保存 tool_trace；
- 1 个会话状态为 handed_off。

自动化测试：

```text
26 passed
```

新增覆盖：

- 订单/物流/售后/工单工具；
- 无效订单号和错误 trace；
- 工单幂等；
- 多轮补全订单号后恢复物流意图；
- 工具模式 SSE；
- 工具结果 + 知识引用；
- 缺失订单号和工具失败兜底；
- 消息与历史中的工具轨迹。

截图：

- `docs/images/m4-chat.png`
- `docs/images/m4-chat-mobile.png`
- `docs/images/m4-dashboard.png`
- `docs/images/m4-landing.png`

### 已知限制

1. 消费者会话没有正式鉴权和限流；
2. 工单已创建，但没有管理员处理界面（M5）；
3. 工具只读取演示订单，未接真实电商平台；
4. 意图路由仍是规则优先，复杂表达可能识别不准；
5. 没有真实退款、改地址或赔付；
6. 没有系统化 Agent 评测集。

### 下一步：M5

M5 计划：

1. 运营会话列表与详情；
2. 会话中的消息、引用、工具轨迹和工单关联；
3. 人工工单队列、状态流转和客服备注；
4. 用户反馈与低分回答；
5. 知识缺口与未解决问题；
6. Token、延迟、工具耗时和成本面板；
7. 从知识库到工单的运营闭环。

M5 不需要新的外部 Key。
