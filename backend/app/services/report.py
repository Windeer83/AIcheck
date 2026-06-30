from __future__ import annotations

from collections import Counter

from app.models import Claim, Document, Evidence, InputText, Run, VerificationResult


def build_markdown_report(
    run: Run,
    input_text: InputText,
    documents: list[Document],
    claims: list[Claim],
    results: list[VerificationResult],
) -> str:
    result_by_claim = {result.claim_id: result for result in results}
    verdict_counter = Counter(result.verdict for result in results)
    high_risk = sum(1 for result in results if result.risk_level == "high")
    critical_risk = sum(1 for result in results if result.risk_level == "critical")
    lines = [
        "# AI 输出事实核查报告",
        "",
        "## 1. 核查任务信息",
        "",
        f"- 项目 ID：{input_text.project_id}",
        f"- 输入文本：{input_text.title}",
        f"- 核查模式：{(run.config or {}).get('mode', 'strict_paper')}",
        f"- 文献数量：{len(documents)}",
        f"- 输入文本长度：{len(input_text.raw_text)}",
        f"- 核查时间：{run.updated_at.isoformat()}",
        "",
        "## 2. 总体结论",
        "",
        _summary_sentence(len(claims), verdict_counter, high_risk, critical_risk),
        "",
        "## 3. 风险概览",
        "",
        f"- 总声称数：{len(claims)}",
        f"- 已核查声称数：{len(results)}",
        f"- 支持：{verdict_counter.get('SUPPORTED', 0)}",
        f"- 部分支持：{verdict_counter.get('PARTIALLY_SUPPORTED', 0)}",
        f"- 证据不足：{verdict_counter.get('INSUFFICIENT_EVIDENCE', 0)}",
        f"- 引用错配：{verdict_counter.get('CITATION_MISMATCH', 0)}",
        f"- 反驳：{verdict_counter.get('REFUTED', 0)}",
        f"- 高风险：{high_risk}",
        f"- 严重风险：{critical_risk}",
        "",
        "## 4. 高风险声称清单",
        "",
        "| Claim ID | 原文 | 原子声称 | 判定 | 可信度 | 风险 | 建议 |",
        "|---|---|---|---|---:|---|---|",
    ]
    for claim in claims:
        result = result_by_claim.get(claim.id)
        if result and result.risk_level in {"high", "critical"}:
            lines.append(
                "| {id} | {original} | {atomic} | {verdict} | {confidence:.1f} | {flags} | {suggestion} |".format(
                    id=claim.id,
                    original=_cell(claim.original_sentence),
                    atomic=_cell(claim.atomic_claim),
                    verdict=result.verdict,
                    confidence=result.confidence,
                    flags=", ".join(result.risk_flags or []),
                    suggestion=_suggestion(result.verdict, result.risk_flags or []),
                )
            )
    lines.extend(["", "## 5. 引用错配清单", ""])
    _append_verdict_table(lines, claims, result_by_claim, "CITATION_MISMATCH")
    lines.extend(["", "## 6. 疑似伪造文献清单", "", "MVP 阶段仅做引用绑定与上传文献匹配，外部元数据真实性校验默认关闭。"])
    lines.extend(["", "## 7. 全量声称核查表", "", "| Claim ID | 原子声称 | 类型 | 判定 | 可信度 | 风险等级 |", "|---|---|---|---|---:|---|"])
    for claim in claims:
        result = result_by_claim.get(claim.id)
        if not result:
            continue
        lines.append(f"| {claim.id} | {_cell(claim.atomic_claim)} | {claim.claim_type} | {result.verdict} | {result.confidence:.1f} | {result.risk_level} |")
    lines.extend(["", "## 8. 证据详情", ""])
    for claim in claims:
        result = result_by_claim.get(claim.id)
        if not result:
            continue
        lines.extend(
            [
                f"### Claim {claim.id}",
                "",
                f"**原文句子**：{claim.original_sentence}",
                "",
                f"**原子声称**：{claim.atomic_claim}",
                "",
                f"**判定**：{result.verdict}",
                f"**可信度**：{result.confidence:.1f} / 100",
                f"**风险等级**：{result.risk_level}",
                f"**风险标签**：{', '.join(result.risk_flags or []) or '无'}",
                "",
                f"**系统解释**：{result.explanation or ''}",
                "",
            ]
        )
        for evidence in sorted(claim.evidences, key=lambda e: e.rerank_score, reverse=True)[:3]:
            lines.extend(
                [
                    f"- 文献：{evidence.document.title or evidence.document.file_name}，Page {evidence.page_start}-{evidence.page_end}",
                    f"  - 关系：{evidence.relation}，相关度：{evidence.relevance_score:.2f}，支持度：{evidence.entailment_score:.2f}",
                    f"  - 片段：{_snippet(evidence.evidence_text)}",
                ]
            )
        lines.append("")
    lines.extend(["## 9. 系统配置", "", "```json", str(run.config or {}), "```", "", "## 10. 人工复核记录", "", "暂无。", ""])
    return "\n".join(lines)


def _summary_sentence(total: int, counter: Counter[str], high: int, critical: int) -> str:
    risky = high + critical
    if total == 0:
        return "未抽取到可核查声称。"
    if risky:
        return f"系统共抽取 {total} 条声称，其中 {risky} 条为高风险或严重风险，建议优先复核证据不足、数值和引用归因类表述。"
    return f"系统共抽取 {total} 条声称，当前项目文献库未发现严重风险，但仍建议人工复核关键证据。"


def _append_verdict_table(lines: list[str], claims: list[Claim], result_by_claim: dict, verdict: str) -> None:
    lines.extend(["| Claim ID | 原子声称 | 可信度 | 说明 |", "|---|---|---:|---|"])
    found = False
    for claim in claims:
        result = result_by_claim.get(claim.id)
        if result and result.verdict == verdict:
            found = True
            lines.append(f"| {claim.id} | {_cell(claim.atomic_claim)} | {result.confidence:.1f} | {_cell(result.explanation or '')} |")
    if not found:
        lines.append("| - | 暂无 | - | - |")


def _suggestion(verdict: str, flags: list[str]) -> str:
    if verdict == "CITATION_MISMATCH":
        return "更换引用或补充能直接支撑该句的文献。"
    if "UNSUPPORTED_NUMERIC_VALUE" in flags:
        return "回到原文表格核对数值，无法确认时删除或弱化。"
    if verdict == "INSUFFICIENT_EVIDENCE":
        return "补充证据或弱化为谨慎表述。"
    if verdict == "REFUTED":
        return "删除或重写该声称。"
    return "人工复核后保留。"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")[:240]


def _snippet(text: str) -> str:
    return text.replace("\n", " ")[:500]

