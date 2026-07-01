# AI 输出事实核查与可信度评估系统使用说明

## 1. 产品用途

本系统用于论文写作场景中的 AI 输出事实核查。你可以先上传论文、报告或实验材料 PDF，再粘贴一段 AI 生成文本，系统会抽取其中可核查的事实声称，按所选证据来源匹配证据，并给出 verdict、confidence、risk level、证据页码/位置和 Markdown 报告。

系统当前是 MVP，支持两种证据来源模式：内部上传文献库和 OpenAlex 开放学术库。无论哪种模式，所有结论都必须落到 evidence 记录，不会只保存模型判断。

## 2. 核心概念

- Project：一个核查项目，建议对应一篇论文、一个课题或一个写作任务。
- Document：上传到项目中的 PDF 文献。系统会解析页码并切分为 chunks。
- Input Text：需要核查的 AI 输出文本。
- Claim：系统从输入文本中抽取的最小事实声称。
- Evidence：从 PDF chunks 或 OpenAlex 导入片段中检索到的证据，保留 document、chunk、page_start、page_end 和原文。
- Evidence Source：核查时选择的证据来源。内部库模式只检索当前项目上传并解析完成的 PDF；OpenAlex 模式会按 claim 查询 OpenAlex Works，并把命中的题名、作者、年份、DOI、来源 URL 和摘要导入为外部证据片段。
- Verdict：系统对 claim 的综合判定。

## 3. 使用流程

### 3.1 打开系统

访问 Sealos Web 应用公网地址。如果你只打开 Backend 地址，根路径会返回 API 状态；真正的工作台在 Web 应用里。

页面顶部会显示后端代理地址和当前后端版本/数据库迁移版本。只刷新浏览器只能确认前端页面已重新加载；如果后端、Worker 或数据库迁移有更新，应结合版本号、容器重启状态和迁移版本一起确认。

### 3.2 创建项目

在左侧项目区域输入项目名称，例如：

```text
睡眠与学习事实核查测试
```

点击创建项目后，系统会自动选中该项目。

### 3.3 上传 PDF

在“文献库”区域点击“批量上传 PDF”，可以一次选择多篇 PDF。

注意：

- MVP 目前只支持 PDF。
- 上传后需要等待解析完成，每个文件会单独显示排队、解析中、已完成或解析失败。
- `[1]`、`[2]`、`[3]` 这类数字引用按上传顺序绑定文献，所以测试时请按样本文档指定顺序上传。
- 文献卡片左侧的 `[1]`、`[2]` 编号就是当前项目内的引用绑定顺序。
- 解析失败时可以点击重新解析。
- 点击移除文献会从当前文献库软删除该文献；历史报告中的 evidence 仍保留可追溯信息。

### 3.4 粘贴待核查文本

在输入区粘贴 AI 输出段落，建议每次先测试 3 到 6 句话。文本中可包含数字引用，例如 `[1]`。

### 3.5 启动核查

启动前先在输入区右上角选择证据来源：

- 内部库：适合你已经上传了论文 PDF，希望核验文本是否被这些文献支持。数字引用 `[1]`、`[2]` 会继续按上传顺序绑定。
- 开放库：适合你还没有完整内部文献库，或想让系统按 claim 自动搜索开放学术数据库。当前实现使用 OpenAlex Works，证据以题名、DOI、年份、来源链接和摘要片段保存；如果网络不可用或被限流，该模式会提示 warning 并返回证据不足。

点击运行核查。系统会依次执行：

1. 抽取 claims。
2. 绑定 citation refs。
3. 根据证据来源模式检索 evidence：内部库做 PDF chunk 混合检索；开放库先查 OpenAlex 并导入候选摘要片段，再做混合检索。
4. 调用模型判定 claim 与 evidence 的关系。
5. 聚合 verdict、confidence、risk flags。
6. 生成 Markdown 报告。

运行状态区域会实时追加日志，显示当前正在抽取、绑定引用、检索证据、判定 claim 或生成报告。刷新页面后，只要任务仍存在，历史日志仍可通过当前 run 查看。

### 3.6 查看结果

结果页重点看：

- 原文高亮是否覆盖待核查句子；点击高亮后，核查表会滚动到对应 claim 行。
- 原文高亮采用下划线和分数标记：绿色偏支持，黄色表示部分支持或中等风险，红色表示反驳、引用错配或严重风险。
- 核查表可以按判定、风险等级和复核状态筛选。
- verdict 是否符合预期。
- confidence 是否合理。
- evidence 是否能追溯到文档和页码。
- risk flags 是否指出数字、范围、证据不足等问题。
- 对明显不合理的核查，可以点击“确认”或“屏蔽”；屏蔽不会删除原始 claim/evidence，只是不纳入风险概览。
- Markdown 导出是否包含 claim、verdict、evidence 和人工复核记录。

## 4. Verdict 含义

- SUPPORTED / 支持：证据支持该声称。
- PARTIALLY_SUPPORTED / 部分支持：证据支持部分内容，但存在范围、样本、数字或条件差异。
- REFUTED / 反驳：证据与声称冲突。
- INSUFFICIENT_EVIDENCE / 证据不足：证据不足，不能支持或反驳。
- CITATION_MISMATCH / 引用错配：其他文献可能支持，但当前引用文献不支持该声称。
- NOT_VERIFIABLE / 不可核查：写作安排、主观评价或不适合自动核查的表达。

## 5. 常见问题

### 打开 Backend 地址显示 404 或状态 JSON

这是正常的。Backend 是 API 服务，不是前端工作台。请访问 Web 应用公网地址。Backend 可用这些路径检查：

```text
/ 
/healthz
/readyz
/docs
```

### 上传 PDF 后没有解析结果

检查 Backend 日志，确认 Celery worker 已启动。如果使用 all-in-one 镜像，启动日志中应能看到 `parse_document` 和 `verify_input_text` 两个任务。

### 前端提示 401

Web 和 Backend 的 `APP_ACCESS_TOKEN` 必须完全一致。

### 浏览器跨域错误

Backend 的 `BACKEND_CORS_ORIGINS` 需要包含 Web 的公网域名。多个域名用英文逗号分隔。

### `/readyz` 失败

通常是数据库连接问题。检查 `DATABASE_URL` 是否包含：

- driver：`postgresql+psycopg://`
- 用户名
- 密码
- Sealos 内网 host
- 端口
- 数据库名，例如 `/postgres`

## 6. 推荐验收顺序

1. Backend `/healthz` 返回 `{"status":"ok"}`。
2. Backend `/readyz` 返回 `{"status":"ready"}`。
3. Web 能创建项目。
4. Web 能上传 PDF。
5. 文献解析状态完成。
6. 能批量上传、重新解析失败文献，并移除不需要的文献。
7. 能提交输入文本并启动核查。
8. 结果中有 claims、evidences、verdicts。
9. 内部库模式下 evidence 来自上传 PDF；OpenAlex 模式下 evidence 来自 OpenAlex 导入片段。
10. 点击原文高亮能跳转到对应核查表行。
11. 能确认或屏蔽某条核查结果。
12. 能导出包含证据来源模式和人工复核记录的 Markdown 报告。
