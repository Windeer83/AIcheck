"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Database,
  Download,
  Eye,
  EyeOff,
  FileText,
  Gauge,
  Loader2,
  Play,
  RefreshCcw,
  Search,
  Server,
  Trash2,
  Upload,
  Workflow
} from "lucide-react";
import { api } from "@/lib/api";
import type { ClaimResult, DocumentRecord, Project, Run, RunLog, RunResults, VersionInfo } from "@/lib/types";

const sampleText =
  "张明等研究发现，睡眠干预组在两周后记忆保持率提高了 18%[1]。\n\n现有研究普遍认为短期正念训练能够显著降低所有研究生群体的压力水平[3]。";

const verdictLabels: Record<string, string> = {
  SUPPORTED: "支持",
  PARTIALLY_SUPPORTED: "部分支持",
  REFUTED: "反驳",
  INSUFFICIENT_EVIDENCE: "证据不足",
  CITATION_MISMATCH: "引用错配",
  FABRICATED_REFERENCE: "疑似伪造文献",
  NOT_VERIFIABLE: "不可核查"
};

const riskLabels: Record<ClaimResult["risk_level"], string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
  critical: "严重风险"
};

const reviewLabels: Record<ClaimResult["review_status"], string> = {
  unreviewed: "未复核",
  confirmed: "已确认",
  suppressed: "已屏蔽"
};

const parseStatusLabels: Record<string, string> = {
  queued: "排队中",
  parsing: "解析中",
  completed: "已完成",
  failed: "解析失败"
};

const runStatusLabels: Record<string, string> = {
  queued: "排队中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  ready: "待启动"
};

const stepLabels: Record<string, string> = {
  idle: "待启动",
  queued: "排队中",
  extracting_claims: "抽取声称",
  binding_citations: "绑定引用",
  verifying_claims: "检索与判定",
  generating_report: "生成报告",
  completed: "已完成",
  failed: "失败"
};

const relationLabels: Record<string, string> = {
  SUPPORTS: "支持",
  PARTIALLY_SUPPORTS: "部分支持",
  REFUTES: "反驳",
  NOT_ENOUGH_INFO: "信息不足",
  IRRELEVANT: "不相关"
};

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [results, setResults] = useState<RunResults | null>(null);
  const [projectName, setProjectName] = useState("中文论文事实核查演示");
  const [textTitle, setTextTitle] = useState("AI 生成相关工作段落");
  const [rawText, setRawText] = useState(sampleText);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [showSuppressed, setShowSuppressed] = useState(false);
  const [version, setVersion] = useState<VersionInfo | null>(null);
  const [verdictFilter, setVerdictFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");
  const [reviewFilter, setReviewFilter] = useState("all");

  useEffect(() => {
    void refreshProjects();
    void refreshVersion();
  }, []);

  useEffect(() => {
    if (!activeProject) return;
    void refreshDocuments(activeProject.id);
  }, [activeProject]);

  useEffect(() => {
    if (!activeProject || !documents.some((document) => ["queued", "parsing"].includes(document.parse_status))) return;
    const timer = window.setInterval(() => {
      void refreshDocuments(activeProject.id);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [activeProject, documents]);

  useEffect(() => {
    if (!run || ["completed", "failed"].includes(run.status)) return;
    const timer = window.setInterval(async () => {
      const nextRun = await api.getRun(run.id);
      setRun(nextRun);
      if (nextRun.status === "completed") {
        const nextResults = await api.getResults(nextRun.id);
        setResults(nextResults);
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [run]);

  const visibleClaims = useMemo(
    () =>
      (results?.claims ?? []).filter((claim) => {
        if (!showSuppressed && claim.review_status === "suppressed") return false;
        if (verdictFilter !== "all" && claim.verdict !== verdictFilter) return false;
        if (riskFilter !== "all" && claim.risk_level !== riskFilter) return false;
        if (reviewFilter !== "all" && claim.review_status !== reviewFilter) return false;
        return true;
      }),
    [results, reviewFilter, riskFilter, showSuppressed, verdictFilter]
  );

  const selectedClaim = useMemo(() => {
    return visibleClaims.find((claim) => claim.claim_id === selectedClaimId) ?? visibleClaims.find((claim) => claim.risk_level === "critical" || claim.risk_level === "high") ?? visibleClaims[0];
  }, [selectedClaimId, visibleClaims]);

  useEffect(() => {
    if (!visibleClaims.length) {
      setSelectedClaimId(null);
      return;
    }
    if (!selectedClaimId || !visibleClaims.some((claim) => claim.claim_id === selectedClaimId)) {
      const nextClaim = visibleClaims.find((claim) => claim.risk_level === "critical" || claim.risk_level === "high") ?? visibleClaims[0];
      setSelectedClaimId(nextClaim.claim_id);
    }
  }, [selectedClaimId, visibleClaims]);

  async function refreshVersion() {
    try {
      setVersion(await api.getVersion());
    } catch {
      setVersion(null);
    }
  }

  async function refreshProjects() {
    try {
      const loaded = await api.listProjects();
      setProjects(loaded);
      setActiveProject((current) => current ?? loaded[0] ?? null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "项目加载失败");
    }
  }

  async function refreshDocuments(projectId: string) {
    try {
      setDocuments(await api.listDocuments(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "文献加载失败");
    }
  }

  async function handleCreateProject() {
    setBusy(true);
    try {
      const project = await api.createProject({ name: projectName, description: "稳定演示 MVP 项目", verification_mode: "strict_paper" });
      setProjects((items) => [project, ...items]);
      setActiveProject(project);
      setMessage("项目已创建");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "项目创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(fileList: FileList | null) {
    if (!activeProject || !fileList?.length) return;
    const files = Array.from(fileList).filter((file) => file.name.toLowerCase().endsWith(".pdf"));
    if (!files.length) {
      setMessage("当前阶段只支持 PDF 文件");
      return;
    }
    setBusy(true);
    try {
      const uploaded: DocumentRecord[] = [];
      for (const file of files) {
        const document = await api.uploadDocument(activeProject.id, file);
        uploaded.push(document);
        setDocuments((items) => [document, ...items]);
      }
      setMessage(`已上传 ${uploaded.length} 个 PDF，解析任务已进入队列`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteDocument(document: DocumentRecord) {
    if (!window.confirm(`确定从当前文献库移除“${document.title || document.file_name}”吗？历史报告中的 evidence 仍会保留。`)) return;
    setBusy(true);
    try {
      await api.deleteDocument(document.id);
      setDocuments((items) => items.filter((item) => item.id !== document.id));
      setMessage("文献已从当前文献库移除");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除文献失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRetryDocument(document: DocumentRecord) {
    setBusy(true);
    try {
      const retried = await api.retryDocument(document.id);
      setDocuments((items) => items.map((item) => (item.id === retried.id ? retried : item)));
      setMessage("已重新提交解析任务");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "重试解析失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleVerify() {
    if (!activeProject) return;
    setBusy(true);
    setResults(null);
    setSelectedClaimId(null);
    try {
      const inputText = await api.createInputText(activeProject.id, {
        title: textTitle,
        raw_text: rawText,
        section_type: "related_work",
        citation_style: "numeric"
      });
      const nextRun = await api.startVerification(inputText.id);
      setRun(nextRun);
      setMessage("核查任务已启动");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "核查启动失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleReview(claim: ClaimResult, reviewStatus: ClaimResult["review_status"]) {
    setBusy(true);
    try {
      await api.reviewResult(claim.result_id, {
        review_status: reviewStatus,
        review_note: reviewStatus === "suppressed" ? "用户确认该条核查暂不纳入演示风险统计。" : null
      });
      if (run) {
        const nextResults = await api.getResults(run.id);
        setResults(nextResults);
      }
      setSelectedClaimId(claim.claim_id);
      setMessage(reviewStatus === "suppressed" ? "已屏蔽该条核查" : reviewStatus === "confirmed" ? "已确认该条核查" : "已恢复为未复核");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "复核状态更新失败");
    } finally {
      setBusy(false);
    }
  }

  function handleSelectClaim(claimId: string) {
    setSelectedClaimId(claimId);
    window.setTimeout(() => {
      document.getElementById(`claim-row-${claimId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 0);
  }

  return (
    <main className="min-h-screen bg-white">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-lg bg-teal text-white">
              <Search size={18} />
            </div>
            <div>
              <h1 className="text-lg font-semibold leading-tight text-ink">AI 事实核查工作台</h1>
              <p className="text-xs text-slate">证据可追溯的中文论文写作风险扫描器</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <StatusPill icon={<Server size={14} />} label="后端" value={api.baseUrl} />
            <StatusPill icon={<Database size={14} />} label="版本" value={formatVersion(version)} />
          </div>
        </div>
      </header>

      <section className="mx-auto grid max-w-[1500px] gap-5 px-6 py-5 xl:grid-cols-[300px_minmax(0,1fr)_410px]">
        <aside className="space-y-4">
          <Panel title="项目">
            <div className="space-y-3">
              <input className="field" value={projectName} onChange={(event) => setProjectName(event.target.value)} />
              <button className="primary-button w-full" onClick={handleCreateProject} disabled={busy}>
                新建项目
              </button>
            </div>
            <div className="mt-4 space-y-2">
              {projects.map((project) => (
                <button
                  key={project.id}
                  className={clsx("w-full rounded-lg border px-3 py-3 text-left transition", activeProject?.id === project.id ? "border-teal bg-[#eef8f6]" : "border-line bg-white hover:border-teal")}
                  onClick={() => setActiveProject(project)}
                >
                  <div className="text-sm font-semibold text-ink">{project.name}</div>
                  <div className="mt-1 text-xs text-slate">严格论文模式</div>
                </button>
              ))}
              {!projects.length ? <EmptyLine text="先创建一个核查项目" /> : null}
            </div>
          </Panel>

          <Panel title="文献库">
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-teal bg-[#f2fbf9] px-3 py-4 text-sm font-semibold text-teal">
              <Upload size={16} />
              批量上传 PDF
              <input
                type="file"
                accept="application/pdf"
                multiple
                className="hidden"
                onChange={(event) => {
                  void handleUpload(event.target.files);
                  event.target.value = "";
                }}
              />
            </label>
            <p className="mt-2 text-xs leading-5 text-slate">数字引用按上传顺序绑定：文本中的 [1] 对应最早上传的第 1 篇 PDF。</p>
            <div className="mt-4 space-y-2">
              {documents.map((document) => (
                <div key={document.id} className="rounded-lg border border-line bg-white p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        {document.citation_index ? <span className="shrink-0 rounded bg-[#eef8f6] px-2 py-0.5 text-xs font-semibold text-teal">[{document.citation_index}]</span> : null}
                        <div className="truncate text-sm font-semibold text-ink">{document.title || document.file_name}</div>
                      </div>
                      <div className="mt-1 text-xs text-slate">{document.chunks_count} 个片段 · {document.year || "年份待识别"}</div>
                    </div>
                    <ParseStatus status={document.parse_status} />
                  </div>
                  {document.parse_error ? <p className="mt-2 text-xs text-danger">{document.parse_error}</p> : null}
                  <div className="mt-3 flex items-center gap-2">
                    <IconButton label="重新解析" disabled={busy || document.parse_status === "parsing"} onClick={() => void handleRetryDocument(document)} icon={<RefreshCcw size={14} />} />
                    <IconButton label="移除文献" disabled={busy} onClick={() => void handleDeleteDocument(document)} icon={<Trash2 size={14} />} danger />
                  </div>
                </div>
              ))}
              {!documents.length ? <EmptyLine text="上传 PDF 后会生成带页码证据片段" /> : null}
            </div>
          </Panel>
        </aside>

        <section className="space-y-4">
          <Panel title="待核查文本" action={<ModeSelector />}>
            <div className="grid gap-3">
              <input className="field" value={textTitle} onChange={(event) => setTextTitle(event.target.value)} />
              <textarea className="min-h-[240px] resize-y rounded-lg border border-line bg-white px-4 py-3 text-sm leading-7 outline-none focus:border-teal" value={rawText} onChange={(event) => setRawText(event.target.value)} />
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs text-slate">{rawText.length} 字符 · 当前阶段只使用已上传 PDF 作为证据来源</div>
                <button className="primary-button min-w-[150px]" onClick={handleVerify} disabled={!activeProject || busy}>
                  {busy ? <Loader2 className="animate-spin" size={16} /> : <Play size={16} />}
                  启动核查
                </button>
              </div>
            </div>
          </Panel>

          <Panel title="原文高亮">
            <HighlightedText text={rawText} claims={visibleClaims} selectedClaimId={selectedClaim?.claim_id ?? null} onSelectClaim={handleSelectClaim} />
          </Panel>

          <Panel
            title="声称级核查表"
            action={
              <button className="secondary-button px-3 py-2 text-xs" onClick={() => setShowSuppressed((value) => !value)}>
                {showSuppressed ? <EyeOff size={14} /> : <Eye size={14} />}
                {showSuppressed ? "隐藏已屏蔽" : "显示已屏蔽"}
              </button>
            }
          >
            <div className="mb-3 grid gap-2 md:grid-cols-3">
              <FilterSelect label="判定" value={verdictFilter} onChange={setVerdictFilter} options={[{ label: "全部判定", value: "all" }, ...Object.entries(verdictLabels).map(([value, label]) => ({ label, value }))]} />
              <FilterSelect label="风险" value={riskFilter} onChange={setRiskFilter} options={[{ label: "全部风险", value: "all" }, ...Object.entries(riskLabels).map(([value, label]) => ({ label, value }))]} />
              <FilterSelect label="复核" value={reviewFilter} onChange={setReviewFilter} options={[{ label: "全部状态", value: "all" }, ...Object.entries(reviewLabels).map(([value, label]) => ({ label, value }))]} />
            </div>
            <div className="max-h-[520px] overflow-auto">
              <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
                <thead className="sticky top-0 bg-white text-xs text-slate">
                  <tr>
                    <th className="border-b border-line px-3 py-2">原子声称</th>
                    <th className="border-b border-line px-3 py-2">判定</th>
                    <th className="border-b border-line px-3 py-2">可信度</th>
                    <th className="border-b border-line px-3 py-2">风险</th>
                    <th className="border-b border-line px-3 py-2">复核</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleClaims.map((claim) => (
                    <tr
                      id={`claim-row-${claim.claim_id}`}
                      key={claim.claim_id}
                      className={clsx("cursor-pointer align-top transition", selectedClaim?.claim_id === claim.claim_id ? "bg-[#eef8f6]" : "hover:bg-panel", claim.review_status === "suppressed" && "opacity-60")}
                      onClick={() => handleSelectClaim(claim.claim_id)}
                    >
                      <td className="max-w-[520px] border-b border-line px-3 py-3 text-ink">
                        <div className="leading-6">{claim.atomic_claim}</div>
                        {claim.citation_refs?.length ? <div className="mt-1 text-xs text-slate">引用：{claim.citation_refs.join(", ")}</div> : null}
                      </td>
                      <td className="border-b border-line px-3 py-3 font-semibold text-ink">{labelVerdict(claim.verdict)}</td>
                      <td className="border-b border-line px-3 py-3">{claim.confidence.toFixed(1)}</td>
                      <td className="border-b border-line px-3 py-3">
                        <span className={clsx("rounded-md px-2 py-1 text-xs font-semibold", riskClass(claim.risk_level))}>{riskLabels[claim.risk_level]}</span>
                      </td>
                      <td className="min-w-[160px] border-b border-line px-3 py-3">
                        <div className="mb-2 text-xs text-slate">{reviewLabels[claim.review_status]}</div>
                        <div className="flex flex-wrap gap-2">
                          <button className="secondary-button px-2 py-1 text-xs" onClick={(event) => { event.stopPropagation(); void handleReview(claim, "confirmed"); }} disabled={busy || claim.review_status === "confirmed"}>
                            <Check size={13} />确认
                          </button>
                          <button className="secondary-button px-2 py-1 text-xs" onClick={(event) => { event.stopPropagation(); void handleReview(claim, claim.review_status === "suppressed" ? "unreviewed" : "suppressed"); }} disabled={busy}>
                            {claim.review_status === "suppressed" ? <Eye size={13} /> : <EyeOff size={13} />}
                            {claim.review_status === "suppressed" ? "恢复" : "屏蔽"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!visibleClaims.length ? <EmptyLine text="核查完成后会显示所有 claim、verdict 和证据引用" /> : null}
            </div>
          </Panel>
        </section>

        <aside className="space-y-4">
          <Panel title="运行状态" action={run ? <span className="text-xs text-slate">{Math.round(run.progress * 100)}%</span> : null}>
            <div className="space-y-3">
              <div className="h-2 overflow-hidden rounded-full bg-panel">
                <div className="h-full rounded-full bg-teal transition-all" style={{ width: `${Math.round((run?.progress ?? 0) * 100)}%` }} />
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <Metric icon={<Workflow size={16} />} label="步骤" value={stepLabels[run?.current_step ?? "idle"] ?? run?.current_step ?? "待启动"} />
                <Metric icon={<Gauge size={16} />} label="状态" value={runStatusLabels[run?.status ?? "ready"] ?? run?.status ?? "待启动"} />
              </div>
              {message ? <p className="rounded-lg bg-panel px-3 py-2 text-xs text-slate">{message}</p> : null}
              {run?.error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-danger">{run.error}</p> : null}
              <RunLogPanel logs={run?.logs ?? []} />
            </div>
          </Panel>

          <Panel title="风险概览">
            <div className="grid grid-cols-2 gap-2">
              <SummaryTile label="总声称" value={results?.summary.total_claims ?? 0} />
              <SummaryTile label="支持" value={results?.summary.supported ?? 0} />
              <SummaryTile label="证据不足" value={results?.summary.insufficient_evidence ?? 0} />
              <SummaryTile label="引用错配" value={results?.summary.citation_mismatch ?? 0} />
              <SummaryTile label="高风险" value={results?.summary.high_risk ?? 0} />
              <SummaryTile label="已屏蔽" value={results?.summary.suppressed ?? 0} />
            </div>
            {run?.status === "completed" ? (
              <a className="secondary-button mt-3 w-full" href={api.exportUrl(run.id)} target="_blank" rel="noreferrer">
                <Download size={16} />
                导出 Markdown
              </a>
            ) : null}
          </Panel>

          <Panel title="证据检查器">
            {selectedClaim ? <EvidenceInspector claim={selectedClaim} /> : <EmptyLine text="选择或完成一次核查后查看证据卡片" />}
          </Panel>
        </aside>
      </section>
    </main>
  );
}

function Panel({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-soft">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function StatusPill({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex max-w-[280px] items-center gap-2 rounded-lg border border-line px-3 py-2 text-slate">
      {icon}
      <span className="font-semibold text-ink">{label}</span>
      <span className="truncate">{value}</span>
    </div>
  );
}

function ModeSelector() {
  return (
    <select className="rounded-lg border border-line bg-white px-3 py-2 text-xs font-semibold text-ink outline-none focus:border-teal" defaultValue="strict_paper" aria-label="核查模式">
      <option value="strict_paper">严格论文模式</option>
      <option value="quick">快速预览模式</option>
      <option value="citation">指定文献模式</option>
    </select>
  );
}

function FilterSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: Array<{ label: string; value: string }> }) {
  return (
    <label className="grid gap-1 text-xs text-slate">
      <span>{label}</span>
      <select className="rounded-lg border border-line bg-white px-3 py-2 text-sm font-semibold text-ink outline-none focus:border-teal" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}
function ParseStatus({ status }: { status: string }) {
  const ok = status === "completed";
  const failed = status === "failed";
  return (
    <span className={clsx("inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold", ok ? "bg-emerald-50 text-emerald-700" : failed ? "bg-red-50 text-danger" : "bg-amber-50 text-amber")}>
      {ok ? <CheckCircle2 size={13} /> : failed ? <AlertTriangle size={13} /> : <Loader2 className="animate-spin" size={13} />}
      {parseStatusLabels[status] ?? status}
    </span>
  );
}

function IconButton({ icon, label, onClick, disabled, danger }: { icon: React.ReactNode; label: string; onClick: () => void; disabled?: boolean; danger?: boolean }) {
  return (
    <button
      type="button"
      className={clsx("inline-flex h-8 w-8 items-center justify-center rounded-lg border transition disabled:cursor-not-allowed disabled:opacity-50", danger ? "border-red-100 text-danger hover:bg-red-50" : "border-line text-slate hover:border-teal hover:text-teal")}
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
    >
      {icon}
    </button>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <p className="rounded-lg bg-panel px-3 py-4 text-center text-xs text-slate">{text}</p>;
}

function RunLogPanel({ logs }: { logs: RunLog[] }) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [logs.length]);

  return (
    <div className="rounded-lg border border-line bg-[#fbfdfc]">
      <div className="flex items-center justify-between border-b border-line px-3 py-2">
        <span className="text-xs font-semibold text-ink">运行日志</span>
        <span className="text-[11px] text-slate">{logs.length ? `${logs.length} 条` : "等待任务"}</span>
      </div>
      <div className="max-h-[180px] min-h-[92px] overflow-y-auto px-3 py-2 text-xs leading-5">
        {logs.length ? (
          <div className="space-y-2">
            {logs.map((log) => (
              <div key={log.id} className="grid grid-cols-[48px_minmax(0,1fr)] gap-2">
                <span className={clsx("font-mono", log.level === "error" ? "text-danger" : "text-slate")}>{formatLogTime(log.created_at)}</span>
                <div className="min-w-0">
                  <span className={clsx("mr-2 rounded px-1.5 py-0.5 text-[11px] font-semibold", log.level === "error" ? "bg-red-50 text-danger" : "bg-panel text-slate")}>{stepLabels[log.step] ?? log.step}</span>
                  <span className={log.level === "error" ? "text-danger" : "text-ink"}>{log.message}</span>
                </div>
              </div>
            ))}
            <div ref={endRef} />
          </div>
        ) : (
          <div className="flex h-[72px] items-center justify-center text-slate">启动核查后会实时显示抽取、检索、判定和报告生成过程。</div>
        )}
      </div>
    </div>
  );
}
function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line p-3">
      <div className="flex items-center gap-2 text-xs text-slate">{icon}{label}</div>
      <div className="mt-1 truncate font-semibold text-ink">{value}</div>
    </div>
  );
}

function SummaryTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-panel p-3">
      <div className="text-xs text-slate">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-ink">{value}</div>
    </div>
  );
}

function HighlightedText({ text, claims, selectedClaimId, onSelectClaim }: { text: string; claims: ClaimResult[]; selectedClaimId: string | null; onSelectClaim: (claimId: string) => void }) {
  if (!claims.length) {
    return <p className="whitespace-pre-wrap text-sm leading-7 text-ink">{text}</p>;
  }
  const sorted = [...claims].sort((a, b) => a.char_start - b.char_start || a.char_end - b.char_end);
  const nodes: React.ReactNode[] = [];
  let cursor = 0;
  sorted.forEach((claim) => {
    if (claim.char_end <= cursor) return;
    if (claim.char_start > cursor) nodes.push(<span key={`plain-${cursor}`}>{text.slice(cursor, claim.char_start)}</span>);
    nodes.push(
      <button
        key={claim.claim_id}
        type="button"
        className={clsx("rounded px-1 py-0.5 text-left align-baseline transition", selectedClaimId === claim.claim_id ? "outline outline-2 outline-teal" : "", claim.risk_level === "low" ? "bg-emerald-100" : claim.risk_level === "medium" ? "bg-sky-100" : claim.risk_level === "high" ? "bg-amber-100" : "bg-red-100")}
        onClick={() => onSelectClaim(claim.claim_id)}
      >
        {text.slice(claim.char_start, claim.char_end)}
      </button>
    );
    cursor = Math.max(cursor, claim.char_end);
  });
  if (cursor < text.length) nodes.push(<span key="tail">{text.slice(cursor)}</span>);
  return <p className="whitespace-pre-wrap text-sm leading-7 text-ink">{nodes}</p>;
}

function EvidenceInspector({ claim }: { claim: ClaimResult }) {
  return (
    <div className="space-y-3">
      <div className="rounded-lg bg-panel p-3">
        <div className="text-xs font-semibold text-slate">当前声称</div>
        <p className="mt-2 text-sm leading-6 text-ink">{claim.atomic_claim}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className={clsx("rounded-md px-2 py-1 text-xs font-semibold", riskClass(claim.risk_level))}>{labelVerdict(claim.verdict)}</span>
          <span className="rounded-md bg-white px-2 py-1 text-xs font-semibold text-slate">{claim.confidence.toFixed(1)} / 100</span>
          <span className="rounded-md bg-white px-2 py-1 text-xs font-semibold text-slate">{reviewLabels[claim.review_status]}</span>
        </div>
      </div>
      <p className="text-sm leading-6 text-slate">{claim.explanation}</p>
      {claim.risk_flags.length ? <p className="text-xs leading-5 text-slate">风险标签：{claim.risk_flags.join(", ")}</p> : null}
      {claim.evidences.map((evidence) => (
        <article key={evidence.id} className="rounded-lg border border-line p-3">
          <div className="flex items-start gap-2">
            <FileText className="mt-0.5 text-teal" size={16} />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-ink">{evidence.document_title || "未命名文献"}</div>
              <div className="text-xs text-slate">第 {evidence.page_start}-{evidence.page_end} 页 · {labelRelation(evidence.relation)}</div>
            </div>
          </div>
          <p className="mt-3 line-clamp-6 text-xs leading-5 text-slate">{evidence.evidence_text}</p>
          {evidence.explanation ? <p className="mt-2 text-xs leading-5 text-slate">判定说明：{evidence.explanation}</p> : null}
        </article>
      ))}
      {!claim.evidences.length ? <EmptyLine text="未找到可用证据，系统不会用模型常识补证。" /> : null}
    </div>
  );
}

function riskClass(risk: ClaimResult["risk_level"]) {
  return {
    low: "risk-low",
    medium: "risk-medium",
    high: "risk-high",
    critical: "risk-critical"
  }[risk];
}

function formatVersion(version: VersionInfo | null) {
  if (!version) return "版本未知";
  const sha = version.build_sha ? ` · ${version.build_sha.slice(0, 7)}` : "";
  const db = version.database_revision ? ` · DB ${version.database_revision}` : "";
  return `${version.backend_version}${sha}${db}`;
}
function formatLogTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}
function labelVerdict(verdict: string) {
  return verdictLabels[verdict] ?? verdict;
}

function labelRelation(relation: string | null) {
  return relationLabels[relation ?? ""] ?? relation ?? "未判定";
}
