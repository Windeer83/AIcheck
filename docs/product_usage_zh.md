# AI 输出事实核查与可信度评估系统使用说明

## 1. 产品用途

本系统用于论文写作场景中的 AI 输出事实核查。你可以先上传论文、报告或实验材料 PDF，再粘贴一段 AI 生成文本，系统会抽取其中可核查的事实声称，检索已上传 PDF 中的证据，并给出 verdict、confidence、risk level、证据页码和 Markdown 报告。

系统当前是 MVP，默认以“用户上传 PDF 文献库”为证据来源，不进行外部互联网检索。

## 2. 核心概念

- Project：一个核查项目，建议对应一篇论文、一个课题或一个写作任务。
- Document：上传到项目中的 PDF 文献。系统会解析页码并切分为 chunks。
- Input Text：需要核查的 AI 输出文本。
- Claim：系统从输入文本中抽取的最小事实声称。
- Evidence：从 PDF chunks 中检索到的证据，保留 document、chunk、page_start、page_end 和原文。
- Verdict：系统对 claim 的综合判定。

## 3. 使用流程

### 3.1 打开系统

访问 Sealos Web 应用公网地址。如果你只打开 Backend 地址，根路径会返回 API 状态；真正的工作台在 Web 应用里。

### 3.2 创建项目

在左侧项目区域输入项目名称，例如：

```text
睡眠与学习事实核查测试
```

点击创建项目后，系统会自动选中该项目。

### 3.3 上传 PDF

在“文献库”区域点击“上传 PDF”，按测试要求上传 PDF 文件。

注意：

- MVP 目前只支持 PDF。
- 上传后需要等待解析完成。
- `[1]`、`[2]`、`[3]` 这类数字引用按上传顺序绑定文献，所以测试时请按样本文档指定顺序上传。

### 3.4 粘贴待核查文本

在输入区粘贴 AI 输出段落，建议每次先测试 3 到 6 句话。文本中可包含数字引用，例如 `[1]`。

### 3.5 启动核查

点击运行核查。系统会依次执行：

1. 抽取 claims。
2. 绑定 citation refs。
3. 检索 evidence。
4. 调用模型判定 claim 与 evidence 的关系。
5. 聚合 verdict、confidence、risk flags。
6. 生成 Markdown 报告。

### 3.6 查看结果

结果页重点看：

- verdict 是否符合预期。
- confidence 是否合理。
- evidence 是否能追溯到文档和页码。
- risk flags 是否指出数字、范围、证据不足等问题。
- Markdown 导出是否包含 claim、verdict 和 evidence。

## 4. Verdict 含义

- SUPPORTED：证据支持该声称。
- PARTIALLY_SUPPORTED：证据支持部分内容，但存在范围、样本、数字或条件差异。
- REFUTED：证据与声称冲突。
- INSUFFICIENT_EVIDENCE：证据不足，不能支持或反驳。
- LOW_CONFIDENCE：相关性或判定置信度较低，需要人工复核。

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
6. 能提交输入文本并启动核查。
7. 结果中有 claims、evidences、verdicts。
8. 能导出 Markdown 报告。

