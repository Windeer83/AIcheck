# Sealos 部署指南

本项目按 Sealos App Deploy / App Launchpad 思路准备：把本地 Docker Compose 拆成 Web、API、Worker、PostgreSQL、Redis、Object Storage 六个部分部署。

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

- `ghcr.io/<owner>/ai-output-factcheck-system-api:<tag>`
- `ghcr.io/<owner>/ai-output-factcheck-system-worker:<tag>`
- `ghcr.io/<owner>/ai-output-factcheck-system-web:<tag>`

如果仓库是私有仓库，GHCR 镜像也可能是私有的，需要在 Sealos 中配置镜像拉取凭据。

## 2. 创建数据库

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

数据库需要启用 pgvector。迁移脚本会执行：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

如果托管实例不允许创建 extension，请在数据库管理界面手动启用 pgvector。

你当前这套 Sealos PostgreSQL 连接串需要给 SQLAlchemy 补上 driver 和数据库名：

```text
DATABASE_URL=postgresql+psycopg://postgres:<password>@aicheck-postgresql.ns-1cqo7ki6.svc:5432/postgres
```

注意：不要把真实密码提交到 Git。真实值放到 Sealos 应用环境变量，或本地被忽略的 `deploy/sealos/.env.api`、`deploy/sealos/.env.worker`。

## 3. 创建 Redis

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

## 4. 创建 Object Storage

创建私有 bucket，记录：

- bucket name
- Access Key
- Secret Key
- Internal endpoint
- region

API 和 Worker 使用同一组 S3 环境变量。

如果 API 和 Worker 分开部署，强烈建议使用 Object Storage。否则 API 上传的 PDF 在 API 容器本地，Worker 容器可能读不到文件。临时试运行可以用 `STORAGE_BACKEND=local`，但完整核查闭环请使用 S3-compatible Object Storage。

## 5. 部署 API

- 镜像：`ghcr.io/<owner>/ai-output-factcheck-system-api:<tag>`
- 端口：`8000`
- 启动命令：

```bash
sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
```

- 健康检查路径：`/healthz`
- 就绪检查路径：`/readyz`
- 环境变量：复制 `env.api.example` 并填入真实值。

本地已生成 `deploy/sealos/.env.api` 时，可以直接复制其中内容到 Sealos API 应用环境变量区，再把 `S3_*`、`OPENAI_API_KEY`、`BACKEND_CORS_ORIGINS` 替换成真实值。

## 6. 部署 Worker

- 镜像：`ghcr.io/<owner>/ai-output-factcheck-system-worker:<tag>`
- 不开放公网端口。
- 启动命令：

```bash
celery -A app.worker.celery_app worker --loglevel=INFO
```

- 环境变量：复制 `env.worker.example` 并填入真实值。

本地已生成 `deploy/sealos/.env.worker` 时，可以直接复制其中内容到 Sealos Worker 应用环境变量区，再把 `S3_*`、`OPENAI_API_KEY` 替换成真实值。

## 7. 部署 Web

- 镜像：`ghcr.io/<owner>/ai-output-factcheck-system-web:<tag>`
- 端口：`3000`
- 公网访问：开启
- 环境变量：复制 `env.web.example`。

Web 通过 Next 服务端代理访问 API，环境变量使用：

```text
API_BASE_URL=https://replace-api-domain-or-internal-api-service
APP_ACCESS_TOKEN=replace-with-the-same-token-as-api
```

优先填写 API 的 Sealos 内网服务地址；如果不确定，就填 API 的公网 HTTPS 地址。`APP_ACCESS_TOKEN` 必须与 API/Worker 一致。

## 8. 验收

1. Web 页面可打开。
2. API `/healthz` 返回 `{"status":"ok"}`。
3. API `/readyz` 返回 `{"status":"ready"}`。
4. 创建项目成功。
5. 上传 PDF 后 Worker 能解析 chunks。
6. 启动核查后 PostgreSQL 有 claims/evidences/results。
7. Object Storage 中出现上传 PDF 和 Markdown 报告。
