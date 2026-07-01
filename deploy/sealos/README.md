# Sealos 部署指南

本项目按 Sealos App Deploy / App Launchpad 思路准备。新手建议先用两个应用部署：`Backend(API + Worker)` 和 `Web`。这样不需要 Object Storage，上传 PDF 暂存在 Backend 应用的 `/data` 目录。

后续生产化再拆成 Web、API、Worker、PostgreSQL、Redis、Object Storage 六个部分部署。

参考文档：

- App Deploy：https://sealos.io/docs/guides/app-deploy/
- Docker Compose 迁移：https://sealos.io/docs/guides/app-deploy/docker-compose-migration/
- 环境变量：https://sealos.io/docs/guides/app-deploy/environments/
- PostgreSQL：https://sealos.io/docs/guides/databases/postgresql/
- Object Storage：https://sealos.io/docs/guides/object-storage/
- 首次部署：https://sealos.io/docs/guides/app-deploy/first-deploy/
- 绑定域名：https://sealos.io/docs/guides/app-deploy/add-a-domain/

## 1. 准备镜像

推送到 GitHub 后，GitHub Actions 会构建：

- `ghcr.io/windeer83/aicheck-api:<tag>`
- `ghcr.io/windeer83/aicheck-worker:<tag>`
- `ghcr.io/windeer83/aicheck-web:<tag>`

如果仓库是私有仓库，GHCR 镜像也可能是私有的，需要在 Sealos 中配置镜像拉取凭据。

演示阶段可以使用 `:main` 标签，但需要在 Sealos 里关注镜像拉取策略和应用重启；如果要可追溯回滚，优先使用 GitHub Actions 生成的 `sha-*` 标签。

## 2. 新手推荐：两个应用部署

### 2.1 Backend 应用

创建一个 Sealos 应用：

- 镜像：`ghcr.io/windeer83/aicheck-api:main`
- 端口：`8000`
- 公网访问：开启
- 建议挂载持久化存储到：`/data`
- 启动命令：建议留空，使用镜像默认命令。

如果 Sealos 强制要求填写启动命令，填：

```bash
sh
```

Arguments 填：

```bash
/app/start-sealos-all-in-one.sh
```

环境变量：复制 `deploy/sealos/.env.backend-allinone`，或参考 `env.backend-allinone.example`。

这个方式把 API 和 Worker 放在同一个容器里，所以 PDF 文件可以用本地 `/data` 共享，暂时不需要 Object Storage。启动脚本会先运行 `alembic upgrade head`，包括文献软删除和人工复核字段迁移。

如果要使用 OpenAlex 开放库模式，Backend 应用需要能访问公网 `api.openalex.org`。`OPENALEX_API_KEY` 和 `OPENALEX_EMAIL` 是可选项，建议在生产或演示环境中配置 email/key 以降低限流风险；不要把真实 key 写入仓库。

### 2.2 Web 应用

创建第二个 Sealos 应用：

- 镜像：`ghcr.io/windeer83/aicheck-web:main`
- 端口：`3000`
- 公网访问：开启
- 环境变量：

```text
API_BASE_URL=https://你的-backend-公网地址
APP_ACCESS_TOKEN=必须和 Backend 的 APP_ACCESS_TOKEN 一样
```

Web 通过自己的服务端代理访问 Backend，不会把 `APP_ACCESS_TOKEN` 暴露到浏览器。

## 3. 进阶部署：拆分 API / Worker / Object Storage

如果你后续要把 API 和 Worker 拆成两个独立应用，就需要 Object Storage。Object Storage 不是数据库，它是 S3 兼容文件桶，用来共享上传 PDF 和导出报告。

在 Sealos 里它一般不在“数据库”页面，而是在应用市场、对象存储、云存储或 S3 相关入口。如果你的 Sealos 工作区没有这个入口，先用上面的两个应用部署法。

### 3.1 创建数据库

在 Sealos 中创建 PostgreSQL，记录：

- host
- port
- database
- username
- password

拼成：

```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME
```

MVP 默认不要求 pgvector 扩展，embedding 会存入 PostgreSQL JSONB 字段，方便直接部署到 Sealos 托管 PostgreSQL。

你当前这套 Sealos PostgreSQL 连接串需要给 SQLAlchemy 补上 driver 和数据库名：

```text
DATABASE_URL=postgresql+psycopg://postgres:<password>@aicheck-postgresql.ns-1cqo7ki6.svc:5432/postgres
```

注意：不要把真实密码提交到 Git。真实值放到 Sealos 应用环境变量，或本地被忽略的 `deploy/sealos/.env.api`、`deploy/sealos/.env.worker`。

### 3.2 创建 Redis

优先使用 Sealos 可用的 Redis 模板；如果没有，用 App Deploy 部署：

- 镜像：`redis:7-alpine`
- 端口：`6379`
- 公网访问：关闭

环境变量示例：

```text
CELERY_BROKER_URL=redis://<redis-host>:6379/0
CELERY_RESULT_BACKEND=redis://<redis-host>:6379/1
```

你当前这套 Sealos Redis 推荐这样拆分队列库和结果库：

```text
CELERY_BROKER_URL=redis://default:<password>@aicheck1-redis-redis.ns-1cqo7ki6.svc:6379/0
CELERY_RESULT_BACKEND=redis://default:<password>@aicheck1-redis-redis.ns-1cqo7ki6.svc:6379/1
```

### 3.3 创建 Object Storage

创建私有 bucket，记录：

- bucket name
- Access Key
- Secret Key
- Internal endpoint
- region

API 和 Worker 使用同一组 S3 环境变量。

开放库模式不依赖 Object Storage，但 API/Worker 都需要相同的 OpenAlex 配置，尤其是拆分部署时的 `OPENALEX_API_KEY`、`OPENALEX_EMAIL`、`OPENALEX_PER_CLAIM_LIMIT` 和 `OPENALEX_TIMEOUT_SECONDS`。

如果 API 和 Worker 分开部署，强烈建议使用 Object Storage。否则 API 上传的 PDF 在 API 容器本地，Worker 容器可能读不到文件。临时试运行可以用 `STORAGE_BACKEND=local`，但完整核查闭环请使用 S3-compatible Object Storage。

### 3.4 部署 API

- 镜像：`ghcr.io/windeer83/aicheck-api:<tag>`
- 端口：`8000`
- 启动命令：

```bash
sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
```

- 健康检查路径：`/healthz`
- 就绪检查路径：`/readyz`
- 环境变量：复制 `env.api.example` 并填入真实值。

本地已生成 `deploy/sealos/.env.api` 时，可以直接复制其中内容到 Sealos API 应用环境变量区，再把 `S3_*`、`OPENAI_API_KEY`、`BACKEND_CORS_ORIGINS` 替换成真实值。

### 3.5 部署 Worker

- 镜像：`ghcr.io/windeer83/aicheck-worker:<tag>`
- 不开放公网端口。
- 启动命令：

```bash
celery -A app.worker.celery_app worker --loglevel=INFO
```

- 环境变量：复制 `env.worker.example` 并填入真实值。

本地已生成 `deploy/sealos/.env.worker` 时，可以直接复制其中内容到 Sealos Worker 应用环境变量区，再把 `S3_*`、`OPENAI_API_KEY` 替换成真实值。

### 3.6 部署 Web

- 镜像：`ghcr.io/windeer83/aicheck-web:<tag>`
- 端口：`3000`
- 公网访问：开启
- 环境变量：复制 `env.web.example`。

Web 通过 Next 服务端代理访问 API，环境变量使用：

```text
API_BASE_URL=https://replace-api-domain-or-internal-api-service
APP_ACCESS_TOKEN=replace-with-the-same-token-as-api
```

优先填写 API 的 Sealos 内网服务地址；如果不确定，就填 API 的公网 HTTPS 地址。`APP_ACCESS_TOKEN` 必须与 API/Worker 一致。

## 4. 验收

1. Web 页面可打开。
2. API `/healthz` 返回 `{"status":"ok"}`。
3. API `/readyz` 返回 `{"status":"ready"}`。
4. 创建项目成功。
5. 可以批量上传 PDF，Worker 能解析 chunks。
6. 可以移除文献、重新解析失败文献。
7. 内部库模式启动核查后 PostgreSQL 有 claims/evidences/results。
8. OpenAlex 模式能写入 `source_type=openalex` 的外部证据文档和对应 evidences；如果外网不可用，运行日志应出现 warning 且结果为证据不足。
9. 点击原文高亮能定位到核查表对应行。
10. 可以确认或屏蔽某条核查结果，刷新后状态仍保留。
11. 能导出包含 evidence、证据来源模式和人工复核记录的 Markdown 报告。

两应用部署使用本地 `/data` 挂载保存上传 PDF 和 Markdown 报告；只有拆分 API/Worker 时才要求 Object Storage。
