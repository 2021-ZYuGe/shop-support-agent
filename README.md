# 青禾生活 · 电商售后智能问答 Agent

面向电商售后场景的完整问答工程：可追溯的知识回答、订单与物流工具、人工转接，以及面向客服的运营后台。

这是一个**虚构店铺**的教学项目，所有商品、客户、订单和地址均为合成数据。

> 当前进度：**M1 · 工程骨架与数据库**。已完成前后端骨架、MySQL 数据模型与迁移、管理员认证、虚构种子数据和运营入口；RAG 与 Agent 在后续里程碑接入。

![青禾生活首页](docs/images/m1-landing.png)

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vite + React + TypeScript |
| 后端 | Python 3.12 + FastAPI |
| 数据库 | MySQL 5.7 + SQLAlchemy + Alembic |
| Agent（M4） | LangGraph |
| 对话模型（M3） | DeepSeek `deepseek-flash` |
| Embedding（M2） | 硅基流动 `BAAI/bge-m3` |
| 向量索引（M2） | 本地 Chroma |
| 认证 | 数据库会话 + HttpOnly Cookie + scrypt 密码哈希 |

全部 AI 推理通过 API 完成，本地不下载或运行大模型。由于电脑配置有限，前端选择更轻的 Vite，而不是 Next.js。

## M1 已完成

- Vite + React 消费者落地页、管理员登录页与运营后台；
- FastAPI 健康检查、登录、登出、当前管理员、运营概览和订单列表接口；
- 13 张 MySQL 表：管理员、会话、商品、订单、明细、物流、知识文档、知识切片、会话消息、工具调用、人工工单、反馈；
- Alembic 初始迁移；
- scrypt 密码哈希、随机会话令牌、HttpOnly Cookie；
- 幂等种子数据：6 个商品、8 个订单、3 份售后文档、9 个知识切片；
- 后端 7 个自动化测试通过；
- 桌面与手机端视觉验收通过。

![运营概览](docs/images/m1-dashboard.png)

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

DeepSeek 和硅基流动的 Key 在 M3 / M2 之前可以留空。

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

当前结果：

- 后端：**7 passed**
- 前端：TypeScript 构建通过
- 浏览器验收：登录 → 概览 → 订单台账 → 退出 → 未登录访问后台自动跳转

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 服务、数据库和 AI Key 配置状态 |
| POST | `/api/auth/login` | 管理员登录并写入 HttpOnly 会话 Cookie |
| POST | `/api/auth/logout` | 删除服务端会话并清除 Cookie |
| GET | `/api/auth/me` | 当前登录管理员 |
| GET | `/api/admin/overview` | 运营指标、最近订单、能力进度 |
| GET | `/api/admin/orders` | 订单台账，最多返回 100 条 |

## 目录结构

```text
.
├─ backend/
│  ├─ app/
│  │  ├─ api/              # API 路由与登录依赖
│  │  ├─ core/             # 配置与密码/会话安全
│  │  ├─ db/               # SQLAlchemy 模型、会话、种子
│  │  ├─ schemas/          # Pydantic 接口模型
│  │  └─ main.py
│  ├─ alembic/             # 数据库迁移
│  ├─ scripts/             # MySQL 初始化脚本
│  ├─ tests/
│  └─ requirements.txt
├─ frontend/
│  └─ src/
│     ├─ auth/             # 登录状态
│     ├─ components/       # 品牌、后台框架、状态徽标
│     ├─ lib/              # API 客户端与格式化
│     └─ pages/            # 首页、登录、概览、订单
├─ data/                   # 本地上传、索引和验收库，不提交
├─ docs/                   # 方案、学习过程、开发日志与双视角复盘
└─ .env.example
```

## 开发文档

- [项目方案](docs/00-project-plan.md)
- [学习版开发全过程](docs/01-learning-journey.md)
- [开发日志](docs/02-dev-log.md)
- [产品经理视角](docs/03-product-manager-view.md)
- [AI 应用开发视角](docs/04-ai-developer-view.md)

## 后续里程碑

- **M2**：硅基流动 BGE-M3 + Chroma 知识入库与检索调试；
- **M3**：DeepSeek RAG 流式问答与引用；
- **M4**：LangGraph Agent、订单/物流工具、人工转接；
- **M5**：会话中心、工单和运营数据面板；
- **M6**：评测集、Rerank 与 Prompt 优化；
- **M7**：安全、测试、文档与最终演示。

## 安全与边界

- 不接入真实淘宝/京东账号；
- 不执行真实退款、改地址或赔付；
- 不使用真实客户个人信息；
- API Key 只存本地 `.env`，不提交 Git；
- 后台密码使用 scrypt 哈希，会话保存在服务端数据库；
- 后续阶段会对工具调用增加白名单、参数校验和审计。
