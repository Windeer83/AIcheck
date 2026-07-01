# 稳定可演示 MVP 升级规划

> 日期：2026-07-01
> 目标版本：Stable Demo MVP
> 范围来源：PRD、当前代码体检、用户 10 个问题反馈
> 交付方式：本地文档规划，不提交 GitHub

## 1. 阶段目标

本阶段目标不是一次性完成 PRD 全量 P0，而是把当前系统升级为“稳定、可演示、可解释”的论文事实核查 MVP。

演示时用户应能完成以下闭环：

1. 在 Web 工作台创建项目。
2. 批量上传 PDF 文献。
3. 系统解析 PDF，生成可追溯到文档、chunk、页码和原文片段的 evidence。
4. 粘贴中文 AI 生成论文段落。
5. 系统通过 SiliconFlow OpenAI-compatible provider 抽取 claims、检索 evidence、生成 verdict。
6. 前端以中文展示原文高亮、核查表、证据卡片和风险解释。
7. 点击原文高亮后跳转到对应核查表行，并同步显示证据详情。
8. 用户可删除文献、屏蔽某条确认不合理的核查结果。
9. 导出 Markdown 报告。
10. 在 Sealos 以 Backend all-in-one + Web 两应用方式稳定部署演示。

## 2. 当前完成度判断

当前系统已经具备工程闭环，但还偏“跑通 demo”，离稳定演示还差交互、管理能力、中文验收集和部署固化。

已完成或基本完成：

- FastAPI API、Celery pipeline、PostgreSQL schema、Next.js 工作台已搭建。
- 已有项目、PDF 上传、输入文本、启动核查、结果查询、Markdown 导出接口。
- Evidence 已落库，并包含 `document_id`、`chunk_id`、`page_start`、`page_end`、`evidence_text`，符合系统核心原则。
- 前端已有项目区、文献区、文本输入区、原文高亮、核查表、风险概览、证据检查器。
- 前端 `typecheck` 和 `build` 已通过。

当前主要缺口：

- 前端仍有部分英文状态和技术字段，中文论文用户理解成本较高。
- 原文高亮和核查表没有联动，结果多时难以定位。
- 文献管理能力不足：缺批量上传、删除、解析失败重试和清晰状态反馈。
- 核查结果缺人工管理能力：用户无法屏蔽或标记一条明显不合理的核查。
- SiliconFlow 接入需要做稳定化：模型配置、JSON 解析失败降级、错误提示、超时重试、演示环境验证。
- 当前引用绑定较弱，主要适合数字引用按上传顺序匹配。
- 缺中文自动化 gold cases，无法证明演示结果是稳定可复现的。
- Sealos 两应用部署路径需要固化为明确验收流程。

## 3. 用户决策与范围约束

已确认：

- 阶段目标：稳定可演示 MVP。
- LLM provider：SiliconFlow，走 OpenAI-compatible 接口。
- 资料输入：只支持 PDF。
- 报告输出：Markdown 足够。
- 外部学术源：当前阶段不接，只使用用户上传文献。
- 部署目标：Sealos 两应用部署。
- 验收样本：设计中文自动化 gold cases。
- 前端重点：中文显示、原文高亮跳转核查表、文献管理、核查结果屏蔽。

待默认处理：

- 原问题 3“引用绑定与文献定位”解释：当文本中出现 `[1]`、`[2]` 或“张三等，2023”时，系统需要知道它对应哪篇上传 PDF。当前阶段推荐先做好数字引用 `[1]` 按上传顺序绑定，并在 UI 中明确提示“数字引用按上传顺序匹配”。DOI、作者年份精确校验和文献真实性校验放到后续阶段。
- 原问题 10 未回答：本规划默认按 1 个稳定演示 sprint 推进，建议周期 5 到 7 个工作日。若需要更快上线，可压缩为“中文 UI + SiliconFlow + Sealos + gold cases”的最小组合。

## 4. 风险识别优先级

用户希望风险类型都重要，但当前阶段必须服务稳定演示，因此排序如下：

1. 证据可追溯缺失：任何 verdict 都必须有可回溯 evidence；没有 evidence 时必须标证据不足。
2. 数值、年份、单位错误：论文幻觉高发，且适合中文 gold cases 自动化验收。
3. 引用错配：文本引用了 `[1]`，但 `[1]` 对应文献不支持该声称。
4. 证据不足：上传文献库中找不到足够证据，不能让模型凭常识补证。
5. 过度概括：例如“普遍认为”“大量研究表明”但只有单篇或弱证据。
6. 原文反驳：证据与 claim 方向相反，应标高风险或严重风险。
7. 主题错配：检索到相似词，但文献主题不支持该 claim。
8. 方法/结果混淆：把方法描述写成实验结论，或把相关性写成因果。
9. 疑似伪造文献：当前不接外部学术源，只能识别“引用未绑定到上传文献”，不做 DOI 真伪判断。

## 5. 推荐实现路径

### 5.1 前端中文化与联动

方案 A：只把界面文案翻译为中文。

- 复杂度低。
- 演示观感改善有限。
- 不解决“结果多时难定位”的问题。

方案 B：中文化 + 原文高亮联动核查表 + 当前 claim 详情。

- 复杂度中等。
- 明显提升演示可用性。
- 需要在前端维护 `selectedClaimId`，并给核查表行加稳定 DOM id 或 ref。

推荐：方案 B。

影响范围：

- `frontend/src/app/page.tsx`
- `frontend/src/lib/types.ts`
- 可能少量调整 CSS

验证方式：

- 点击任意高亮片段后，核查表滚动到对应 claim 行。
- 该行有选中态，右侧 evidence 检查器同步切换。
- 所有用户可见状态、按钮和风险标签显示中文。

### 5.2 文献管理

方案 A：前端循环调用现有单文件上传 API，实现批量上传。

- 复杂度低。
- 不改后端 schema。
- 每个文件独立显示进度和错误。

方案 B：新增后端批量上传 API。

- 复杂度中等。
- 后端一次处理多个文件，接口更完整。
- 当前阶段收益不如方案 A 明显。

推荐：先用方案 A 完成稳定演示；后端只新增删除文献和解析失败重试能力。

删除策略：

- 当前阶段采用软删除：给文献标记 `deleted_at`，列表、检索、重试都会排除已删除文献。
- 历史 claim/evidence/result 不被删除，保证已生成报告和核查记录仍可追溯。
- 后续如果需要释放存储空间，再增加管理员级清理任务，而不是在普通用户删除操作中硬删。

影响范围：

- `backend/app/api.py`
- `backend/app/services/storage.py`
- `frontend/src/app/page.tsx`
- 可能需要补充测试

验证方式：

- 可一次选择多个 PDF 上传。
- 每个 PDF 单独显示 queued/parsing/completed/failed。
- 可删除文献；删除后文献列表和 chunks 统计刷新。
- 删除进行中任务时给出限制或明确错误。

### 5.3 核查结果屏蔽与人工复核

方案 A：只在前端本地隐藏某条结果。

- 复杂度最低。
- 刷新页面后丢失。
- Markdown 报告无法反映人工复核。
- 不推荐作为产品能力。

方案 B：在后端持久化人工复核状态。

- 复杂度中等。
- 可在结果页和 Markdown 报告中保留人工记录。
- 符合 PRD 中 P1 人工反馈方向。

推荐：方案 B。

建议数据设计：

- 在 `verification_results` 增加：
  - `review_status`：`unreviewed | confirmed | suppressed`
  - `review_note`
  - `reviewed_at`
- 或新增 `claim_reviews` 表。稳定 MVP 推荐先加字段，后续多人协作再拆表。

前端交互：

- 每条核查结果显示“确认合理”“屏蔽此条”。
- 屏蔽需要二次确认。
- 默认核查表可切换“显示全部 / 隐藏已屏蔽”。
- Markdown 报告中增加“人工复核记录”，已屏蔽项不计入风险概览，或单独列为“已屏蔽”。

影响范围：

- `backend/app/models.py`
- `backend/migrations/`
- `backend/app/api.py`
- `backend/app/schemas.py`
- `backend/app/services/report.py`
- `frontend/src/app/page.tsx`

验证方式：

- 屏蔽后刷新页面仍保留状态。
- 导出 Markdown 能看到人工复核记录。
- 屏蔽不删除原始 claim/evidence/result，保证可追溯。

### 5.4 SiliconFlow 稳定化

方案 A：复用现有 OpenAI-compatible provider，只补环境变量和文档。

- 复杂度低。
- 可能无法处理部分模型 JSON 输出不稳定、embedding 参数差异。

方案 B：保留 provider 抽象，针对 SiliconFlow 做演示级稳定化。

- 复杂度中等。
- 更适合真实演示。
- 需要补错误提示、重试、JSON 修复、超时配置。

推荐：方案 B。

关键要求：

- `.env.example` 只保留占位符，不写真实 key。
- `LLM_PROVIDER=openai_compatible`
- `OPENAI_BASE_URL=https://api.siliconflow.cn/v1`
- `OPENAI_MODEL` 和 `EMBEDDING_MODEL` 使用可配置值。
- LLM 输出必须按 JSON 解析；失败时降级 Mock 或给出明确失败状态。
- evidence 判定 prompt 必须强调“只能基于 Evidence，不允许用模型知识补证”。

验证方式：

- 无 key 时 Mock 流程可跑通。
- 有 SiliconFlow key 时真实模型可完成中文 claim 抽取和 evidence 判定。
- LLM JSON 异常不导致整个 run 崩溃。

### 5.5 中文自动化 Gold Cases

目标：建立一套中文可重复验收集，证明“稳定可演示 MVP”不是只靠手工观察。

建议样本结构：

- 中文 PDF 1：睡眠干预与记忆保持，包含明确样本量、结果数值和限制。
- 中文 PDF 2：咖啡因与入睡潜伏期，包含与睡眠相关但不测量记忆准确率的内容。
- 中文 PDF 3：正念训练与压力评分，包含 pilot study 和不可外推限制。

建议 gold cases：

1. SUPPORTED：claim 与 PDF 明确一致。
2. UNSUPPORTED_NUMERIC_VALUE：claim 中数值与原文不一致。
3. CITATION_MISMATCH：`[1]` 不支持，但 `[2]` 或其他文献支持。
4. INSUFFICIENT_EVIDENCE：上传文献没有测量该指标。
5. OVERGENERALIZATION_RISK：把单个 pilot study 写成普遍结论。
6. REFUTED：claim 与 PDF 明确相反。
7. NOT_VERIFIABLE：写作安排或主观评价不进入事实核查。

自动化层级：

- 第一层：服务级单元测试，使用 deterministic Mock，不依赖外部 API。
- 第二层：API 集成测试，验证 evidence 字段完整、Markdown 导出包含页码和片段。
- 第三层：可选真实 SiliconFlow smoke test，只有设置环境变量时才运行。

验收标准：

- 每个 gold case 至少检查 verdict 或 risk flag。
- 每条可核查 claim 至少有 evidence 或明确 `NO_EVIDENCE_FOUND`。
- 所有 evidence 必须包含 `document_id`、`chunk_id`、`page_start`、`page_end`、`evidence_text`。

### 5.6 Sealos 两应用部署

本阶段部署采用：

- Backend all-in-one：API + Worker 同容器，挂载 `/data` 持久化存储。
- Web：Next.js 应用，通过服务端代理访问 Backend。

选择依据：

- 用户当前目标是稳定演示，不是生产级拆分。
- 两应用部署避免 API 和 Worker 分开后本地文件不共享的问题。
- 暂不需要 Object Storage，降低部署复杂度。

必须提醒：

- 公网部署必须设置强随机 `APP_ACCESS_TOKEN`。
- 不得把真实 API key、数据库密码、Redis 密码、访问 token 写入仓库或文档。
- 如果 Sealos 使用 `:main` 镜像标签，要关注镜像拉取策略和应用重启；可追溯发布优先用 `sha-*` 标签。
- Backend all-in-one 是演示推荐方式，不代表后续生产架构。

验收方式：

1. Backend `/healthz` 返回 ok。
2. Backend `/readyz` 返回 ready。
3. Web 能创建项目。
4. Web 能批量上传 PDF。
5. Worker 能解析文献并生成 chunks。
6. 能启动核查并得到 results。
7. 能导出 Markdown。

## 6. 建议里程碑

### Milestone A：演示基线冻结

目标：明确当前可运行基线，避免后续改动时不知道哪里坏了。

任务：

- 补齐本地 Python 依赖或使用容器执行 backend pytest。
- 记录前端 typecheck/build 通过状态。
- 记录 Docker/Sealos 验证方式。
- 确认 `.env`、上传文件、报告文件、密钥未进入仓库。

交付：

- 一份当前基线检查记录。
- 可复现的开发/演示启动步骤。

### Milestone B：中文演示工作台

目标：让非开发用户也能理解结果。

任务：

- 所有用户可见字段中文化。
- 风险等级中文化：低风险、中风险、高风险、严重风险。
- verdict 中文映射：支持、部分支持、反驳、证据不足、引用错配、不可核查。
- 原文高亮点击后跳转核查表对应行。
- 当前 claim 与 evidence 检查器联动。

交付：

- 中文工作台。
- 高亮到核查表的定位交互。

### Milestone C：文献管理能力

目标：演示时能管理项目资料，不需要手动刷新或重建项目。

任务：

- 批量上传 PDF。
- 上传队列和单文件状态显示。
- 删除文献。
- 解析失败错误展示和重试入口。
- 明确提示数字引用按上传顺序绑定。

交付：

- 可批量上传、删除、重试的文献库区域。

### Milestone D：人工复核与屏蔽

目标：允许用户管理明显不合理的核查结果，但不破坏 evidence 追溯。

任务：

- 增加后端复核状态字段或 review 表。
- 增加结果复核 API。
- 前端支持确认合理、屏蔽此条、显示全部/隐藏已屏蔽。
- Markdown 报告体现人工复核记录。

交付：

- 持久化的结果屏蔽与复核能力。

### Milestone E：SiliconFlow 稳定化

目标：真实模型演示时不因 JSON、超时或配置问题频繁失败。

任务：

- 校验 SiliconFlow chat completions 和 embeddings 配置。
- 增加更清晰的 LLM 错误信息。
- 强化 JSON 解析失败降级或重试。
- 保留 Mock provider 作为无 key 演示 fallback。

交付：

- SiliconFlow 可用配置说明。
- 有 key 真实运行、无 key Mock 运行都可演示。

### Milestone F：中文 Gold Cases 自动化

目标：用中文样本验证系统能稳定识别核心风险。

任务：

- 设计中文 PDF 样本和输入文本。
- 建立 gold expected verdict/risk flags。
- 补 backend pytest。
- 可选增加真实 provider smoke test。

交付：

- 中文 gold cases。
- 自动化测试覆盖 supported、numeric mismatch、citation mismatch、insufficient evidence、overgeneralization、refuted、not verifiable。

### Milestone G：Sealos 两应用验收

目标：形成稳定演示部署路径。

任务：

- 更新 Backend all-in-one 和 Web 环境变量说明。
- 验证强 token、CORS、健康检查。
- 验证上传 PDF、解析、核查、导出。
- 说明 `:main` 和 `sha-*` 镜像标签策略。

交付：

- Sealos 两应用演示验收清单。
- 回滚说明：切回上一镜像 tag 或 sha tag，保留数据库和 `/data` 挂载。

## 7. 成功标准

稳定演示 MVP 完成时，应满足：

- 前端中文工作台可顺畅演示完整流程。
- 一次演示上传 3 篇中文 PDF，粘贴 1 段中文 AI 文本，能得到多种 verdict。
- 每条核查结论都可追溯到 evidence，或明确说明没有找到证据。
- 点击原文高亮能定位到核查表行。
- 用户可批量上传、删除文献。
- 用户可屏蔽某条不合理核查，并在刷新和导出后保留人工记录。
- Markdown 报告包含任务信息、风险概览、高风险清单、全量声称、证据详情、人工复核记录。
- 后端测试、前端 typecheck/build、部署验收清单通过。
- Sealos 两应用部署可稳定完成一次端到端核查。

## 8. 暂不做事项

为保证阶段收敛，以下功能暂不进入稳定演示 MVP：

- DOCX、Markdown、BibTeX、DOI 列表上传。
- JSON、HTML、CSV、DOCX、PDF 导出。
- Crossref、OpenAlex、Semantic Scholar 等外部学术源。
- DOI 真伪判断和完整伪造文献识别。
- Zotero、Word、LaTeX 插件。
- 团队协作、权限系统、多用户隔离。
- 图表、公式、扫描件 OCR 深度解析。
- 大规模向量数据库或 pgvector 强依赖。

## 9. 文档同步建议

实现上述升级后，建议同步更新：

- `README.md`：当前交付范围、SiliconFlow 配置、演示流程。
- `docs/product_usage_zh.md`：中文操作说明、批量上传、删除、屏蔽结果。
- `deploy/sealos/README.md`：两应用部署、镜像标签、重启/拉取策略、健康检查、回滚方式。
- `samples/README.md`：中文 gold cases 的使用方式和预期结果。

如果代码实现与本规划发生偏离，应记录：

- 偏离点。
- 偏离原因。
- 对演示、测试、部署和后续 PRD P0 的影响。
