# Sealos 上线检查清单

## 上线前

- [ ] GitHub Actions 已成功推送 API/Worker/Web 镜像。
- [ ] Sealos PostgreSQL 可连接。
- [ ] 数据库连接字符串包含数据库名，例如末尾 `/postgres`。
- [ ] Redis 内网地址可用。
- [ ] 如果采用 API/Worker 分离部署，Object Storage bucket 已创建；如果采用 Backend all-in-one，可先跳过。
- [ ] API 和 Worker 使用同一个 `DATABASE_URL`、Redis 配置；分离部署时还要使用同一组 S3 配置。
- [ ] `APP_ACCESS_TOKEN` 是强随机值。
- [ ] `BACKEND_CORS_ORIGINS` 只包含 Web 域名。

## 上线后

- [ ] API `/healthz` 正常。
- [ ] API `/readyz` 正常。
- [ ] Web 页面可打开。
- [ ] 能创建项目。
- [ ] 能上传 PDF。
- [ ] Worker 日志显示解析任务完成。
- [ ] 能启动核查任务。
- [ ] 能导出 Markdown 报告。
- [ ] 分离部署时 Object Storage 出现 `uploads/` 和 `reports/` 对象；all-in-one 部署时检查 `/data/uploads`、`/data/reports`。

## 常见故障

### API readyz 失败

- 检查 `DATABASE_URL`。
- 检查数据库安全组/内网地址。
- 检查数据库名、用户名、密码和内网 host 是否正确。

### 上传成功但不解析

- 检查 Worker 是否运行。
- 检查 Worker 的 Redis URL 是否与 API 一致。
- 分离部署时检查 Worker 是否能访问 Object Storage；all-in-one 部署时检查 `/data` 是否可写。

### 前端 401

- 检查 Web 的 `APP_ACCESS_TOKEN` 是否等于 API 的 `APP_ACCESS_TOKEN`。

### 浏览器跨域错误

- 检查 API 的 `BACKEND_CORS_ORIGINS` 是否包含 Web 公网域名。
