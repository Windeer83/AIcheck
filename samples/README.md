# 测试样本说明

这个目录用于手工验收 MVP。`pdfs/` 目录中的 PDF 是可上传的证据文献；`input_texts.md` 中是可直接粘贴到系统里的 AI 输出样本文本。

## 使用顺序

1. 新建项目：`MVP 控制样本测试`。
2. 按以下顺序上传 PDF：
   1. `pdfs/01_sleep_memory_study.pdf`
   2. `pdfs/02_caffeine_sleep_latency_trial.pdf`
   3. `pdfs/03_mindfulness_stress_pilot.pdf`
3. 等待 PDF 解析完成。
4. 打开 `input_texts.md`，复制其中一个样本块到系统输入区。
5. 启动核查，查看 verdict、evidence 页码和 Markdown 导出。

## 预期现象

- 样本 A 主要应得到支持类结果。
- 样本 B 包含与证据冲突的内容，应出现 REFUTED 或高风险提示。
- 样本 C 包含证据未测量的指标，应出现 INSUFFICIENT_EVIDENCE 或证据不足提示。
- 样本 D 混合了支持、数字错误、范围夸大和证据不足，适合做综合验收。

模型输出会受 LLM provider 影响，最终 verdict 可能略有波动。验收时重点看 evidence 是否被正确检索、页码是否可追溯、风险解释是否指出关键差异。

