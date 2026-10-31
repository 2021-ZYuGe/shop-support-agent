# 青禾生活 · 电商售后智能问答 Agent

面向电商售后场景的完整问答工程：可追溯的知识回答、订单与物流工具、人工转接，以及面向客服的运营后台。

这是一个**虚构店铺**的教学项目，所有商品、客户、订单和地址均为合成数据。

> 当前进度：**M7 · 安全加固与演示交付（已完成）**。M1-M6 已完成全栈底座、知识库、带引用的 RAG 问答、Agent 业务工具、运营工作台和 50 条评测集；M7 新增接口限流、PII 脱敏、安全响应头、提示注入拦截和完整演示指南。项目已可本地演示。

![青禾生活首页](docs/images/m4-landing.png)

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vite + React + TypeScript |
| 后端 | Python 3.12 + FastAPI |
| 数据库 | MySQL 5.7 + SQLAlchemy + Alembic |
| Agent | LangGraph 1.2.19 |
| 对话模型 | DeepSeek `deepseek-flash` + SSE 流式输出 |
| Embedding | 硅基流动 `BAAI/bge-m3`，1024 维 |
| 重排（可选） | 硅基流动 `BAAI/bge-reranker-v2-m3` |
| 向量索引 | 本地 Chroma 1.5.9（HNSW / cosine） |
| 业务工具 | 订单、物流、售后条件判断、人工工单 |
| 认证 | 管理员数据库会话 + HttpOnly Cookie + scrypt 密码哈希 |
| 安全 | 滑动窗口限流、PII 脱敏、安全响应头、提示注入拦截 |

全部 AI 推理通过 API 完成，本地不下载或运行大模型。由于电脑配置有限，前端选择更轻的 Vite，而不是 Next.js。

## M1 已完成

- Vite + React 消费者落地页、管理员登录页与运营后台；
- FastAPI 健康检查、登录、登出、当前管理员、运营概览和订单列表接口；
- 13 张业务表：管理员、会话、商品、订单、明细、物流、知识文档、知识切片、会话消息、工具调用、人工工单、反馈；
- Alembic 初始迁移已在 MySQL 5.7 开发库和测试库执行；
- scrypt 密码哈希、随机会话令牌、HttpOnly Cookie；
- 幂等种子数据：6 个商品、8 个订单、3 份售后文档、9 个知识切片；
- 后端 7 个自动化测试通过；
- MySQL 真库登录、运营接口与浏览器验收通过；
- 桌面与手机端视觉验收通过。

![运营概览](docs/images/m1-dashboard.png)

## M2 已完成

- 支持 Markdown、TXT、PDF、DOCX 上传；
- 按 Markdown 标题与段落切片，目标约 600 字符，80 字符重叠；
- 批量调用硅基流动 `BAAI/bge-m3`，返回 1024 维向量；
- 使用 Chroma `PersistentClient` 保存向量，余弦距离检索；
- 显式传入向量，不触发 Chroma 默认本地 Embedding 模型下载；
- MySQL 保存文档与切片正文，Chroma 作为可重建索引；
- 支持 `pending / indexed / failed` 索引状态与失败重试；
- 后台知识库页支持上传、查看索引状态、逐份建立索引和语义检索调试；
- 后端测试扩展到 **12 passed**。

种子数据包含 3 份文档、9 个切片。M2 验收时还通过上传接口导入 [`docs/examples/member-policy.md`](docs/examples/member-policy.md)，因此当前本地演示库为 4 份文档、12 个切片。

![知识库与检索](docs/images/m2-knowledge.png)

## M3 已完成

- 新增消费者聊天页 `/chat`，无需管理员登录；
- 首次提问创建匿名会话，使用随机 public ID，不暴露顺序主键；
- 短期会话历史保存在 MySQL，刷新页面可恢复；
- 调用 Chroma 检索 Top-K 片段，低于 0.40 相似度时不进入模型；
- DeepSeek `deepseek-flash` 通过 SSE 流式返回答案；
- Prompt 要求仅依据参考资料回答，并禁止编造订单状态、退款承诺或引用来源；
- 回答展示内联引用编号和可展开的引用资料卡片；
- 知识库未命中时返回明确的“无足够依据/建议转人工”兜底；
- 记录用户与助手消息、引用、token 使用量和响应延迟；
- 支持停止生成、错误提示、开始新对话和会话恢复。

真实浏览器验收中，“会员积分怎么抵扣？”返回了正确政策并引用 1 条来源；
“请讲一个笑话”触发知识库未命中兜底；“我的订单 QH20261031007 到哪了？”
没有编造物流状态，而是说明无法查询具体订单并建议转人工。

![消费者聊天页](docs/images/m3-chat.png)

## M4 已完成

- 使用 LangGraph 编排意图路由、工具节点、知识检索和上下文组织；
- 从用户问题和会话历史中提取订单号，支持多轮补全；
- 订单查询与物流查询从 MySQL 读取，只返回脱敏的必要信息；
- 售后条件判断结合签收时间、订单状态、问题类型和售后窗口；
- 人工工单写入 `handoff_tickets`，会话状态变为 `handed_off`；
- 每次工具调用写入 `tool_call_logs`，并在聊天消息中保存工具轨迹；
- 工具参数校验、MySQL SELECT 查询超时、单轮调用次数上限；
- 缺失订单号时直接追问；订单不存在时明确说明，不编造；
- 聊天界面展示工具结果、工具耗时和转人工状态；
- 真实 Agent 场景通过浏览器与 API 验收。

真实验收结果：

| 用户输入 | Agent 行为 |
|---|---|
| 查一下订单 QH20261028003 的物流 | 调用物流工具，返回顺丰已签收、最新动态 |
| 订单 QH20261028003 有划痕能退吗？ | 调用售后条件工具 + 检索售后政策，给出带引用的辅助判断 |
| 我要转人工处理退款 | 创建高优先级人工工单 #1，会话标记为已转人工 |
| 我的订单到哪了 | 不猜测，先追问订单号 |

![Agent 工具调用](docs/images/m4-chat.png)

## M5 已完成

- 会话中心：列表、状态筛选、消息数与最近内容、工单和反馈计数；
- 会话详情：完整对话、知识引用、工具轨迹、token、延迟和反馈；
- 工单队列：按状态筛选，分配当前管理员，更新优先级、状态和处理备注；
- 消费者反馈：每条 AI 回答支持点赞/点踩并写回数据库；
- 运营洞察：负反馈、知识缺口、工具使用、Token、估算成本和平均延迟；
- 后台导航启用会话中心、工单队列和运营洞察；
- 运营概览升级为 7/7 能力已就绪；
- 后端测试覆盖反馈提交/更新、权限、会话详情、工单状态流和洞察统计。

当前演示数据中的反馈/工单写入由自动化测试库验证；真实本地演示库的后台页面已完成只读浏览器验收，避免自动改动演示状态。

![会话中心](docs/images/m5-conversations.png)

## M6 已完成

- 建立 50 条固定评测集，覆盖知识、订单、物流、售后、转人工、拒答和多轮场景；
- 每条样本显式声明期望模式、工具、知识来源、引用、关键词和禁止内容；
- LangGraph Agent 支持 `AgentOptions` 注入 Top-K、阈值、Reranker 和 Prompt 版本；
- 接入硅基流动 `BAAI/bge-reranker-v2-m3`，从 12 个候选中重排后取 Top-5；
- 新增 Prompt v2：先结论、引用编号、限制篇幅、明确不确定时拒答；
- 评测运行在回滚事务中，不向演示库写入会话、工单或工具日志；
- 自动输出逐题结果、分类通过率、检索 Top-1/MRR、Token、延迟和估算成本；
- 运营概览增加评测能力，当前 8/8 已就绪；
- 报告：[M6 评测报告](docs/05-evaluation-report.md)。

实测结果（50 条样本，真实 Chroma + SiliconFlow + DeepSeek）：

| 配置 | 通过率 | 引用覆盖 | 检索 Top-1 | 平均延迟 | 总 tokens | 估算成本 |
|---|---:|---:|---:|---:|---:|---:|
| baseline（Prompt v1） | 50/50 | 100% | 15/19 | 2,780ms | 38,850 | ¥0.0759 |
| prompt_v2（生产默认） | 50/50 | 100% | 15/19 | 2,394ms | 32,130 | ¥0.0613 |
| optimized（+ Reranker） | 50/50 | 100% | 18/19 | 2,862ms | 32,041 | ¥0.0601 |

结论：当前评测集上三种配置都完成了任务，Prompt v2 在保持通过率的同时减少约 17% tokens、14% 平均延迟和 19% 估算成本；Reranker 明显改善首条依据排序（MRR 0.8702 → 0.9649），但增加约 20% 延迟，端到端通过率没有继续提升。因此生产默认 **Prompt v2 + 关闭 Reranker**，Reranker 作为可选的排序增强。

## M7 已完成

- 消费者聊天：每分钟 20 次、每小时 120 次滑动窗口限流；
- 登录：每分钟 10 次限流，降低暴力尝试风险；
- 会话读取与反馈分别限流，超出返回 `429` 和 `Retry-After`；
- 聊天输入与反馈评论做手机号、身份证、银行卡、邮箱脱敏后入库；
- 后台订单手机号再次脱敏；日志过滤订单号、Bearer Token 和 API Key；
- 明显提示注入在 Agent 路由层直接拦截，不进入检索和模型生成；
- API 增加安全响应头、CSP、请求体大小限制和更严格的 CORS 方法/头；
- 生产环境下 Cookie 自动使用 `Secure`；未登录管理员请求统一 `401`；
- 新增演示指南：[docs/06-demo-guide.md](docs/06-demo-guide.md)；
- 后端测试扩展到 **43 passed**。

限流当前是单进程内存滑动窗口，适合本地演示和单实例；多进程/多实例部署需要换成 Redis 等共享存储。PII 规则覆盖常见手机号、身份证、银行卡和邮箱，不宣称覆盖所有地址或自由文本变体。

浏览器验收：运营概览显示 10/10 能力就绪，聊天输入框展示敏感信息提示；后端 `43 passed`，前端构建通过。

![M7 安全与演示交付](docs/images/m7-dashboard.png)

## 本地启动

### 1. 环境要求

- Python 3.12（本项目使用 `D:\python\python3.12`）
- Node.js 22.20+ 或 20.19+（当前 Node 22.20.0 已满足 Vite 要求）
- MySQL 5.7
- 不需要 Docker

### 2. 安装依赖

在项目根目录执行：

```powershell
D:\python\python3.12\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

cd frontend
npm install
cd ..
```

安装依赖都在 D 盘项目目录内；如需把 pip/npm 缓存放到 D 盘：

```powershell
$env:PIP_CACHE_DIR = "D:\dev\cache\pip"
$env:npm_config_cache = "D:\dev\cache\npm"
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env`，然后填写：

```text
DATABASE_URL=mysql+pymysql://shop_support_app:你的密码@127.0.0.1:3306/shop_support_dev?charset=utf8mb4
TEST_DATABASE_URL=mysql+pymysql://shop_support_app:你的密码@127.0.0.1:3306/shop_support_test?charset=utf8mb4
SEED_ADMIN_PASSWORD=你自己的初始管理员密码
```

M2 的文档向量化和语义检索需要 `SILICONFLOW_API_KEY`；M3 的聊天需要 `DEEPSEEK_API_KEY`。两个 Key 都只写入本地 `.env`，不会提交 Git。

### 4. 初始化 MySQL

用 MySQL 管理员账号执行 `backend/scripts/init_mysql.sql`。执行前先修改脚本中的占位密码，避免把真实密码提交到仓库。

脚本会创建：

- `shop_support_dev`
- `shop_support_test`
- 专用的 `shop_support_app` 账号

### 5. 执行迁移并写入演示数据

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.db.seed
```

种子脚本可以重复执行；已有订单、商品和文档不会重复写入。

### 6. 启动前后端

终端 1：

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

终端 2：

```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

- 消费者首页：http://127.0.0.1:5173/
- 运营后台：http://127.0.0.1:5173/admin/login
- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health

### 7. 演示账号

默认种子账号：

```text
邮箱：admin@qinghe.local
密码：ChangeMe123!
```

正式使用前请在 `.env` 中修改 `SEED_ADMIN_EMAIL` 和 `SEED_ADMIN_PASSWORD`。如果管理员已经写入数据库，修改环境变量不会自动覆盖旧密码。

## 测试

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest

cd ..\frontend
npm run build
npm run lint
```

后端测试使用内存 SQLite，快速验证 API、认证和数据层逻辑；开发数据库仍按要求使用 MySQL。

评测需要真实的 `SILICONFLOW_API_KEY` 和 `DEEPSEEK_API_KEY`，会调用 Embedding/Reranker 与 DeepSeek，产生少量 API 费用：

```powershell
cd backend
..\.venv\Scripts\python.exe scripts/run_evaluation.py --config all
```

当前结果：

- 后端：**43 passed**
- MySQL：开发库/测试库迁移成功；开发库种子成功；健康检查、登录、概览、登出接口均通过真实 MySQL 验证
- 知识库：BGE-M3 连通性验证通过；种子文档实际写入 Chroma；语义检索返回正确命中
- 聊天：DeepSeek 流式回答、引用、拒答和会话持久化通过真实 API 与浏览器验收
- Agent：订单/物流工具、售后判断、人工工单、工具轨迹和审计日志通过真实 MySQL 与浏览器验收
- 运营：反馈、会话中心、工单队列与洞察统计通过自动化测试；后台页面完成只读浏览器验收
- 评测：50 条样本 × 3 组配置全部完成；Prompt v2 降低 17.3% tokens、13.9% 平均延迟；Reranker 将检索 MRR 从 0.8702 提升到 0.9649
- 安全：登录/聊天/读取/反馈限流、PII 脱敏、日志过滤、安全响应头、请求体限制和提示注入拦截通过自动化测试
- 前端：TypeScript 构建通过
- 浏览器验收：聊天 → 真实工具回答 → 工具轨迹；会话中心 → 会话详情；工单与洞察页面；知识库上传与检索；登录、订单台账、退出和未登录重定向；M7 概览 10/10 能力与 PII 输入提示

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 服务、数据库和 AI Key 配置状态 |
| POST | `/api/auth/login` | 管理员登录并写入 HttpOnly 会话 Cookie |
| POST | `/api/auth/logout` | 删除服务端会话并清除 Cookie |
| GET | `/api/auth/me` | 当前登录管理员 |
| GET | `/api/admin/overview` | 运营指标、最近订单、能力进度 |
| GET | `/api/admin/orders` | 订单台账，最多返回 100 条 |
| GET | `/api/admin/knowledge/documents` | 知识文档与索引状态 |
| POST | `/api/admin/knowledge/documents` | 上传 Markdown/TXT/PDF/DOCX 并切片入库 |
| POST | `/api/admin/knowledge/documents/{id}/index` | 为待处理/失败切片建立 Chroma 索引 |
| GET | `/api/admin/knowledge/search` | 语义检索召回片段、相似度与来源 |
| GET | `/api/chat/conversations/{public_id}` | 读取匿名会话与消息历史 |
| POST | `/api/chat/stream` | SSE 流式 RAG/Agent 回答，返回引用、工具和 token |
| POST | `/api/chat/conversations/{public_id}/messages/{message_id}/feedback` | 提交或更新 AI 回答反馈 |
| GET | `/api/admin/conversations` | 会话列表与状态统计 |
| GET | `/api/admin/conversations/{public_id}` | 会话详情、消息、引用、工具轨迹和工单 |
| GET | `/api/admin/tickets` | 工单队列与状态统计 |
| PATCH | `/api/admin/tickets/{id}` | 分配、状态、优先级和处理备注 |
| GET | `/api/admin/insights` | 反馈、知识缺口、工具和成本洞察 |

消费者接口受滑动窗口限流保护；超出配置额度时返回 `429` 和 `Retry-After`。登录接口同样限流，避免暴力尝试。

## 目录结构

```text
.
├─ backend/
│  ├─ app/
│  │  ├─ api/              # API 路由与登录依赖
│  │  ├─ core/             # 配置、认证、限流、PII、提示注入与安全中间件
│  │  ├─ db/               # SQLAlchemy 模型、会话、种子
│  │  ├─ schemas/          # Pydantic 接口模型
│  │  ├─ services/         # Embedding、Chroma、RAG、LLM、Reranker、Agent 与业务工具
│  │  └─ main.py
│  ├─ alembic/             # 数据库迁移
│  ├─ evals/               # 50 条固定评测样本
│  ├─ scripts/             # MySQL 初始化、评测运行器
│  ├─ tests/
│  └─ requirements.txt
├─ frontend/
│  └─ src/
│     ├─ auth/             # 登录状态
│     ├─ components/       # 品牌、后台框架、状态徽标
│     ├─ lib/              # API 客户端、SSE 解析与格式化
│     └─ pages/            # 首页、聊天、概览、订单、知识库、会话、工单、洞察
├─ data/                   # 上传文件、Chroma 索引，不提交
├─ docs/
│  ├─ examples/            # 可手动上传的示例文档
│  ├─ images/              # 验收截图
│  └─ 06-demo-guide.md     # 5-8 分钟演示脚本
└─ .env.example
```

## 开发文档

- [项目方案](docs/00-project-plan.md)
- [学习版开发全过程](docs/01-learning-journey.md)
- [开发日志](docs/02-dev-log.md)
- [产品经理视角](docs/03-product-manager-view.md)
- [AI 应用开发视角](docs/04-ai-developer-view.md)
- [M6 评测报告](docs/05-evaluation-report.md)
- [M7 演示指南](docs/06-demo-guide.md)

## 项目状态

M1-M7 已完成，项目可本地演示。后续可选优化：

- 用 Redis 替换单进程内存限流，支持多实例部署；
- 增加管理员角色权限、工单 SLA 和审计查询；
- 增加更难的评测样本、人工评审和线上指标；
- 正式部署前补充 HTTPS、域名、日志留存和隐私合规检查。

## 安全与边界

- 不接入真实淘宝/京东账号；
- 不执行真实退款、改地址或赔付；
- 不使用真实客户个人信息；
- API Key 只存本地 `.env`，不提交 Git；
- 后台密码使用 scrypt 哈希，会话保存在服务端数据库；生产环境 Cookie 自动 `Secure`；
- 消费者会话使用不可枚举的随机 public ID，没有正式账号体系；
- 聊天、登录、会话读取和反馈均有单进程滑动窗口限流，超限返回 `429` 和 `Retry-After`；
- 聊天输入、反馈评论和后台订单手机号做常见 PII 脱敏；日志过滤订单号、Bearer Token 与 API Key；
- 明显提示注入在 Agent 路由层拦截，不进入检索和模型生成；
- API 启用安全响应头、CSP、请求体大小限制和受限 CORS；
- 订单与物流工具只读，转人工只创建工单，不执行真实退款、改地址或赔付；
- 工单处理仅限管理员后台；成本是按 `.env` 单价计算的演示估值；
- 评测运行在回滚事务中，不写入演示库会话、工单或工具日志；
- Prompt v2 已设为默认；Reranker 默认关闭，可通过 `RAG_USE_RERANK=true` 开启；
- PII 正则覆盖常见手机号、身份证、银行卡和邮箱，不宣称覆盖所有地址或自由文本变体；
- 当前是本地单实例演示，不宣称生产级并发、合规或安全防护。
