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

## 协作规则

- 每次开始实质性工作前，先关注 `AGENTS.md` 和 `git status -sb`。如果发现用户手动更新了说明或工作区已有变更，必须先理解并尊重这些变更，不要覆盖用户改动。
- 当用户直接给出实现方案时，先区分用户目标、当前方案、可选方案和推荐方案；如果产品目标、用户场景或成功标准不清楚，先简短追问。
- 涉及架构、状态管理、数据模型、权限、依赖、路由或主要 UI 结构变更时，先说明技术判断依据、影响范围、可能破坏的模块和验证方式。
- 如果存在多个实现路径，至少给出两个方案，并比较复杂度、扩展性、风险和开发成本，再推荐一个。
- 不为了短期跑通引入长期难维护的方案。若必须临时处理，必须标记 TODO 或明确说明原因、影响和后续处理建议。
- 大的功能、信息架构、数据结构、权限模型、部署方式或主要布局变更前后，主动询问是否同步更新 `/docs`，并给出文档更新大纲。
- 定期检查 `/docs`、`README.md`、Sealos 部署文档与实际代码是否一致。发现偏差时，提醒用户选择：更新代码、更新文档，或记录偏差原因。
- 当代码实现与文档方案发生偏离时，说明偏离点、偏离原因和潜在影响。
- 交付结果时，适度解释关键工程判断，让用户理解为什么这样做；当更好的长期方案存在时，礼貌但明确地提出。

## 部署与安全

- Sealos、GHCR、环境变量相关变更必须说明镜像标签策略、重启/拉取策略、健康检查和回滚方式。
- 当前 GitHub 仓库为 `Windeer83/AIcheck`，GHCR 镜像为 `ghcr.io/windeer83/aicheck-api`、`ghcr.io/windeer83/aicheck-worker`、`ghcr.io/windeer83/aicheck-web`。
- 不得把 API key、数据库密码、Redis 密码、`APP_ACCESS_TOKEN` 写入仓库、README、docs、示例文件或日志。
- Sealos 若使用 `:main` 镜像标签，必须提醒用户同时关注镜像拉取策略和应用重启；若需要可追溯发布，优先使用 `sha-*` 标签。

## GitHub 发布

默认仓库：`Windeer83/AIcheck`。

Windows 本机 GitHub CLI：

- GitHub CLI 安装路径为 `C:\Program Files\GitHub CLI\gh.exe`。
- 如果 PowerShell 报 `gh : 无法将“gh”项识别为 cmdlet`，先运行 `gh --version`；仍失败时运行 `& 'C:\Program Files\GitHub CLI\gh.exe' --version` 确认安装是否存在。
- 已在用户级 PATH 中加入 `C:\Program Files\GitHub CLI`；新开的 PowerShell 应可直接使用 `gh`。
- 为兼容已打开的 PowerShell，会话可通过 `C:\Users\16690\AppData\Local\Microsoft\WindowsApps\gh.cmd` 转发到正式的 `gh.exe`。
- 首次发布前先运行 `gh auth login` 登录 GitHub。

发布前检查：

1. `git status -sb`
2. 后端测试通过。
3. 前端类型检查或构建通过。
4. `docker compose config` 无明显错误。
5. 确认没有 `.env`、上传文件或密钥被 staged。
