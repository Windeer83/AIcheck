# Agent 开发说明

## 项目定位

这是一个面向论文写作场景的 AI 输出事实核查系统 MVP。核心原则：所有核查结论必须能追溯到 evidence，不允许仅保存模型判断。

## 目录职责

- `backend/app/api.py`：FastAPI 路由。
- `backend/app/tasks.py`：Celery 任务与核查 pipeline 编排。
- `backend/app/models.py`：SQLAlchemy ORM。
- `backend/app/services/`：PDF 解析、存储、LLM provider、检索、聚合、报告。
- `backend/migrations/`：Alembic schema。
- `frontend/src/app/page.tsx`：单页工作台。
- `frontend/src/lib/`：前端 API client 和类型。
- `deploy/sealos/`：Sealos 部署材料。

## 开发命令

```bash
docker compose up --build
cd backend && pytest
cd frontend && npm run typecheck && npm run build
```

## 环境变量

- 本地默认 `STORAGE_BACKEND=local`。
- Sealos 推荐 `STORAGE_BACKEND=s3`。
- 没有模型密钥时使用 `LLM_PROVIDER=mock`。
- 公网部署必须设置强随机 `APP_ACCESS_TOKEN`。

## 编码约定

- 后端保持 pipeline 可测试：复杂逻辑放在 `services/`，API 只做请求/响应。
- LLM 输出必须按 JSON 解析，解析失败要降级或重试。
- Evidence 必须保留 `document_id`、`chunk_id`、`page_start`、`page_end`、`evidence_text`。
- 前端界面以工作台为主，不做营销首页。
- 不要提交 `.env`、上传文件、报告文件、数据库卷、缓存或构建产物。

## GitHub 发布

默认仓库名：`ai-output-factcheck-system`。

发布前检查：

1. `git status -sb`
2. 后端测试通过。
3. 前端类型检查或构建通过。
4. `docker compose config` 无明显错误。
5. 确认没有 `.env`、上传文件或密钥被 staged。

