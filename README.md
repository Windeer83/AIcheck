# AI 输出事实核查与可信度评估系统

面向论文写作场景的本地单用户 MVP：上传 PDF 文献或选择 OpenAlex 开放学术库，粘贴 AI 生成段落，系统抽取事实声称、匹配证据、判断支持关系，并导出 Markdown 核查报告。

## 当前交付范围

- FastAPI 后端 API：项目、文献上传、文献软删除/重试、文本提交、异步核查、运行日志、结果查询、人工复核、版本查询、报告导出。
- Celery Worker：PDF 解析、chunk 切分、embedding、内部库/OpenAlex 检索、claim-evidence 判定、聚合评分。
- PostgreSQL：保存项目、文献、chunks、claims、evidences、verification results；MVP 默认用 JSONB 存储 embedding，避免部署环境缺少 pgvector 扩展。
- Redis：本地异步任务队列。
- Next.js 中文工作台：项目、批量 PDF 上传、文献删除/重试、上传顺序引用编号、内部库/OpenAlex 双证据来源、输入文本、原文下划线高亮联动核查表、核查表筛选、实时运行日志、风险概览、证据卡片、核查结果确认/屏蔽、Markdown 导出。
- Sealos 兼容：稳定演示优先使用 Backend all-in-one + Web 两应用部署；后续生产化可拆分 API/Worker/Object Storage。

## 开发阶段

### 阶段 0：工程骨架

- 初始化 Git 工程。
- 创建 `backend/`、`frontend/`、`deploy/sealos/`、`.github/workflows/`。
- 配置 Docker Compose、Dockerfile、`.env.example`、`.gitignore`。

### 阶段 1：文献解析与索引

- 上传 PDF 到本地 `/data/uploads` 或 S3-compatible Object Storage。
- 使用 PyMuPDF/pdfplumber 抽取文本和页码。
- 将正文切分为可追溯 chunks。
- 生成 384 维 embedding，写入 PostgreSQL JSONB 字段。

### 阶段 2：声称抽取

- 按段落/句子解析输入文本。
- 识别 `[1]`、`[2-4]`、作者年份类引用。
- 使用 OpenAI 兼容 LLM provider 抽取原子 claim。
- 没有 API key 时使用 Mock provider 跑通流程。

### 阶段 3：证据检索与判定

- 在项目文献库中执行关键词 + 向量混合检索。
- 可切换到 OpenAlex Works 开放库模式：按 claim 搜索开放学术记录，将题名、作者、年份、DOI、来源 URL 和摘要导入为只读外部证据片段。
- 对每条 claim 保留 top evidence。
- 使用 LLM 或 Mock 判定 `SUPPORTS`、`PARTIALLY_SUPPORTS`、`REFUTES`、`NOT_ENOUGH_INFO`、`IRRELEVANT`。
- 聚合为 PRD 中的主 verdict、confidence、risk level 和 risk flags。

### 阶段 4：报告与部署

- 输出 Markdown 报告，报告包含人工复核记录；已屏蔽结果不进入风险概览但保留可追溯 evidence。
- 提供 `/healthz`、`/readyz` 供 Sealos 健康检查。
- 准备 Sealos 两应用部署环境变量模板、健康检查和上线检查清单。
- 通过 GitHub Actions 构建 API/Worker/Web 镜像到 GHCR。

## 本地启动

1. 复制环境变量：

```bash
cp .env.example .env
```

2. 如需真实 LLM，把 `.env` 改为：

```bash
LLM_PROVIDER=openai_compatible
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
OPENAI_MODEL=deepseek-ai/DeepSeek-V4-Pro
EMBEDDING_MODEL=BAAI/bge-m3
```

开放库模式使用 OpenAlex Works API。可选配置如下，留空时会尝试匿名请求；如果部署环境无法访问外网或被限流，系统会写入 warning 并降级为无外部证据，不会用模型常识补证。

```bash
OPENALEX_API_KEY=
OPENALEX_EMAIL=
OPENALEX_PER_CLAIM_LIMIT=5
OPENALEX_TIMEOUT_SECONDS=12
```

3. 启动：

```bash
docker compose up --build
```

4. 打开：

- Web：http://localhost:3000
- API：http://localhost:8000
- API 文档：http://localhost:8000/docs

默认访问 token 是 `.env` 中的 `APP_ACCESS_TOKEN`，前端服务端代理会用同名变量访问 API。

## 常用命令

```bash
# 后端测试
cd backend
pytest

# 前端开发
cd frontend
npm install
npm run dev

# 数据库迁移
cd backend
alembic upgrade head
```

## API 简例

所有 `/api/*` 请求都需要：

```http
X-Access-Token: dev-token
```

主要接口：

- `POST /api/projects`
- `GET /api/projects`
- `POST /api/projects/{project_id}/documents`
- `GET /api/documents/{document_id}`
- `DELETE /api/documents/{document_id}`
- `POST /api/documents/{document_id}/retry`
- `POST /api/projects/{project_id}/input-texts`
- `POST /api/input-texts/{input_text_id}/verify`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/results`
- `PATCH /api/verification-results/{result_id}/review`
- `GET /api/version`
- `GET /api/runs/{run_id}/export?format=markdown`

## Sealos 部署

详见 [deploy/sealos/README.md](deploy/sealos/README.md)。

稳定演示推荐：

- Backend all-in-one：FastAPI + Celery Worker，端口 `8000`，挂载 `/data`，运行 `alembic upgrade head` 后启动 API 和 Worker。
- Web：Next.js，端口 `3000`，公网访问，通过服务端代理访问 Backend。
- PostgreSQL：Sealos 托管 PostgreSQL 或兼容实例。
- Redis：Sealos 应用模板或 `redis:7-alpine` 内网部署。
- Object Storage：稳定演示阶段不强制；API/Worker 拆分后再设置 `STORAGE_BACKEND=s3`。

## 提交规则

需要提交：

- 源码、迁移、Dockerfile、Compose、README、AGENTS、部署模板、GitHub Actions。

不要提交：

- `.env`
- `data/`
- `uploads/`
- `reports/`
- 数据库卷
- `node_modules/`
- `.next/`
- Python 缓存与测试缓存
