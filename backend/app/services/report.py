from __future__ import annotations

import json
from collections import Counter

from app.models import Claim, Document, InputText, Run, VerificationResult


def build_markdown_report(
    run: Run,
    input_text: InputText,
    documents: list[Document],
    claims: list[Claim],
    results: list[VerificationResult],
) -> str:
    result_by_claim = {result.claim_id: result for result in results}
    active_results = [result for result in results if result.review_status != "suppressed"]
    verdict_counter = Counter(result.verdict for result in active_results)
    high_risk = sum(1 for result in active_results if result.risk_level == "high")
    critical_risk = sum(1 for result in active_results if result.risk_level == "critical")
    suppressed = sum(1 for result in results if result.review_status == "suppressed")
    lines = [
        "# AI 输出事实核查报告",
        "",
        "## 1. 核查任务信息",
        "",
        f"- 项目 ID：{input_text.project_id}",
        f"- 输入文本：{input_text.title}",
        f"- 核查模式：{(run.config or {}).get('mode', 'strict_paper')}",
        f"- 证据来源模式：{_label_evidence_source((run.config or {}).get('evidence_source'))}",
        f"- 内部上传文献数量：{len(documents)}",
        f"- 输入文本长度：{len(input_text.raw_text)}",
        f"- 核查时间：{run.updated_at.isoformat()}",
        "- 证据保存原则：所有结论均引用 evidences 表中的 document_id、chunk_id、页码/位置和原文片段",
        "",
        "## 2. 总体结论",
        "",
        _summary_sentence(len(claims), high_risk, critical_risk, suppressed),
        "",
        "## 3. 风险概览",
        "",
        f"- 总声称数：{len(claims)}",
        f"- 已核查声称数：{len(active_results)}",
        f"- 支持：{verdict_counter.get('SUPPORTED', 0)}",
        f"- 部分支持：{verdict_counter.get('PARTIALLY_SUPPORTED', 0)}",
        f"- 证据不足：{verdict_counter.get('INSUFFICIENT_EVIDENCE', 0)}",
        f"- 引用错配：{verdict_counter.get('CITATION_MISMATCH', 0)}",
        f"- 反驳：{verdict_counter.get('REFUTED', 0)}",
        f"- 高风险：{high_risk}",
        f"- 严重风险：{critical_risk}",
        f"- 已屏蔽：{suppressed}",
        "",
        "## 4. 高风险声称清单",
        "",
        "| Claim ID | 原文 | 原子声称 | 判定 | 可信度 | 风险 | 建议 |",
        "|---|---|---|---|---:|---|---|",
    ]
    high_risk_found = False
    for claim in claims:
        result = result_by_claim.get(claim.id)
        if result and result.review_status != "suppressed" and result.risk_level in {"high", "critical"}:
            high_risk_found = True
            lines.append(
                "| {id} | {original} | {atomic} | {verdict} | {confidence:.1f} | {flags} | {suggestion} |".format(
                    id=claim.id,
                    original=_cell(claim.original_sentence),
                    atomic=_cell(claim.atomic_claim),
                    verdict=_label_verdict(result.verdict),
                    confidence=result.confidence,
                    flags=", ".join(result.risk_flags or []),
                    suggestion=_suggestion(result.verdict, result.risk_flags or []),
                )
            )
    if not high_risk_found:
        lines.append("| - | 暂无 | 暂无 | - | - | - | - |")

    lines.extend(["", "## 5. 引用错配清单", ""])
    _append_verdict_table(lines, claims, result_by_claim, "CITATION_MISMATCH")
    lines.extend(["", "## 6. 疑似伪造文献清单", "", "开放库模式会查询 OpenAlex Works 并把命中的题名、DOI、年份和摘要导入为可追溯证据片段；内部库模式仅提示未绑定到上传 PDF 的引用风险，不做 DOI 真伪判断。"])
    lines.extend(["", "## 7. 全量声称核查表", "", "| Claim ID | 原子声称 | 类型 | 判定 | 可信度 | 风险等级 | 复核状态 |", "|---|---|---|---|---:|---|---|"])
    for claim in claims:
        result = result_by_claim.get(claim.id)
        if not result:
            continue
        lines.append(
            f"| {claim.id} | {_cell(claim.atomic_claim)} | {_label_claim_type(claim.claim_type)} | {_label_verdict(result.verdict)} | {result.confidence:.1f} | {_label_risk(result.risk_level)} | {_label_review(result.review_status)} |"
        )

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
                f"**判定**：{_label_verdict(result.verdict)}",
                f"**可信度**：{result.confidence:.1f} / 100",
                f"**风险等级**：{_label_risk(result.risk_level)}",
                f"**风险标签**：{', '.join(result.risk_flags or []) or '无'}",
                f"**复核状态**：{_label_review(result.review_status)}",
                "",
                f"**系统解释**：{result.explanation or ''}",
                "",
            ]
        )
        for evidence in sorted(claim.evidences, key=lambda e: e.rerank_score, reverse=True)[:3]:
            source_name = evidence.document.title or evidence.document.file_name if evidence.document else str(evidence.document_id)
            lines.extend(
                [
                    f"- 文献：{source_name}，Page {evidence.page_start}-{evidence.page_end}",
                    f"  - 关系：{_label_relation(evidence.relation)}，相关度：{evidence.relevance_score:.2f}，支持度：{evidence.entailment_score:.2f}",
                    f"  - 片段：{_snippet(evidence.evidence_text)}",
                ]
            )
        lines.append("")

    lines.extend(["## 9. 系统配置", "", "```json", json.dumps(run.config or {}, ensure_ascii=False, indent=2), "```", "", "## 10. 人工复核记录", ""])
    reviewed = [result for result in results if result.review_status != "unreviewed"]
    if not reviewed:
        lines.append("暂无。")
    else:
        lines.extend(["| Result ID | Claim ID | 复核状态 | 备注 | 复核时间 |", "|---|---|---|---|---|"])
        for result in reviewed:
            lines.append(
                f"| {result.id} | {result.claim_id} | {_label_review(result.review_status)} | {_cell(result.review_note or '')} | {result.reviewed_at.isoformat() if result.reviewed_at else '-'} |"
            )
    lines.append("")
    return "\n".join(lines)


def _summary_sentence(total: int, high: int, critical: int, suppressed: int) -> str:
    risky = high + critical
    if total == 0:
        return "未抽取到可核查声称。"
    suffix = f" 另有 {suppressed} 条已被人工屏蔽。" if suppressed else ""
    if risky:
        return f"系统共抽取 {total} 条声称，其中 {risky} 条为高风险或严重风险，建议优先复核证据不足、数值和引用归因类表述。{suffix}"
    return f"系统共抽取 {total} 条声称，当前项目文献库未发现严重风险，但仍建议人工复核关键证据。{suffix}"


def _append_verdict_table(lines: list[str], claims: list[Claim], result_by_claim: dict, verdict: str) -> None:
    lines.extend(["| Claim ID | 原子声称 | 可信度 | 说明 |", "|---|---|---:|---|"])
    found = False
    for claim in claims:
        result = result_by_claim.get(claim.id)
        if result and result.review_status != "suppressed" and result.verdict == verdict:
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


def _label_verdict(verdict: str) -> str:
    return {
        "SUPPORTED": "支持",
        "PARTIALLY_SUPPORTED": "部分支持",
        "REFUTED": "反驳",
        "INSUFFICIENT_EVIDENCE": "证据不足",
        "CITATION_MISMATCH": "引用错配",
        "FABRICATED_REFERENCE": "疑似伪造文献",
        "NOT_VERIFIABLE": "不可核查",
    }.get(verdict, verdict)


def _label_evidence_source(source: object) -> str:
    return {"openalex": "OpenAlex 开放学术库", "project_library": "内部上传文献库"}.get(str(source or "project_library"), str(source or "project_library"))


def _label_risk(risk: str) -> str:
    return {"low": "低风险", "medium": "中风险", "high": "高风险", "critical": "严重风险"}.get(risk, risk)


def _label_review(status: str) -> str:
    return {"unreviewed": "未复核", "confirmed": "已确认", "suppressed": "已屏蔽"}.get(status, status)


def _label_claim_type(claim_type: str) -> str:
    return {
        "DEFINITION": "定义",
        "METHOD": "方法",
        "RESULT": "结果",
        "NUMERIC": "数值",
        "COMPARATIVE": "比较",
        "CAUSAL": "因果",
        "CONSENSUS": "共识",
        "CITATION_ATTRIBUTION": "引用归因",
        "BACKGROUND": "背景事实",
        "NON_CHECKABLE": "不可核查",
    }.get(claim_type, claim_type)


def _label_relation(relation: str | None) -> str:
    return {
        "SUPPORTS": "支持",
        "PARTIALLY_SUPPORTS": "部分支持",
        "REFUTES": "反驳",
        "NOT_ENOUGH_INFO": "信息不足",
        "IRRELEVANT": "不相关",
    }.get(relation or "", relation or "未判定")


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")[:240]


def _snippet(text: str) -> str:
    return text.replace("\n", " ")[:500]
