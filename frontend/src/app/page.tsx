"use client";

import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Download,
  FileText,
  Gauge,
  Loader2,
  Play,
  Search,
  Server,
  Upload,
  Workflow
} from "lucide-react";
import { api } from "@/lib/api";
import type { ClaimResult, DocumentRecord, Project, Run, RunResults } from "@/lib/types";

const sampleText =
  "Zhang 等提出了一种基于 Transformer 的负荷预测模型，并在真实工业数据集上将 MAE 降低了 15%[1]。\n\n现有研究普遍认为两阶段鲁棒优化能够显著提升虚拟电厂低碳调度的经济性。";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [results, setResults] = useState<RunResults | null>(null);
  const [projectName, setProjectName] = useState("论文综述核查项目");
  const [textTitle, setTextTitle] = useState("AI 生成相关工作段落");
  const [rawText, setRawText] = useState(sampleText);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void refreshProjects();
  }, []);

  useEffect(() => {
    if (!activeProject) return;
    void refreshDocuments(activeProject.id);
  }, [activeProject]);

  useEffect(() => {
    if (!run || ["completed", "failed"].includes(run.status)) return;
    const timer = window.setInterval(async () => {
      const nextRun = await api.getRun(run.id);
      setRun(nextRun);
      if (nextRun.status === "completed") {
        setResults(await api.getResults(nextRun.id));
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [run]);

  const selectedClaim = useMemo(() => results?.claims.find((claim) => claim.risk_level === "critical" || claim.risk_level === "high") ?? results?.claims[0], [results]);

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
      const project = await api.createProject({ name: projectName, description: "本地单用户 MVP 项目", verification_mode: "strict_paper" });
      setProjects((items) => [project, ...items]);
      setActiveProject(project);
      setMessage("项目已创建");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "项目创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(file: File | undefined) {
    if (!activeProject || !file) return;
    setBusy(true);
    try {
      const document = await api.uploadDocument(activeProject.id, file);
      setDocuments((items) => [document, ...items]);
      setMessage("文献已上传，解析任务已进入队列");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleVerify() {
    if (!activeProject) return;
    setBusy(true);
    setResults(null);
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
              <p className="text-xs text-slate">证据可追溯的论文写作风险扫描器</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <StatusPill icon={<Server size={14} />} label="API" value={api.baseUrl} />
            <StatusPill icon={<Database size={14} />} label="Deploy" value="Sealos ready" />
          </div>
        </div>
      </header>

      <section className="mx-auto grid max-w-[1500px] gap-5 px-6 py-5 xl:grid-cols-[280px_minmax(0,1fr)_390px]">
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
                  <div className="mt-1 text-xs text-slate">{project.verification_mode}</div>
                </button>
              ))}
            </div>
          </Panel>

          <Panel title="文献库">
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-teal bg-[#f2fbf9] px-3 py-4 text-sm font-semibold text-teal">
              <Upload size={16} />
              上传 PDF
              <input type="file" accept="application/pdf" className="hidden" onChange={(event) => void handleUpload(event.target.files?.[0])} />
            </label>
            <div className="mt-4 space-y-2">
              {documents.map((document) => (
                <div key={document.id} className="rounded-lg border border-line bg-white p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-ink">{document.title || document.file_name}</div>
                      <div className="mt-1 text-xs text-slate">{document.chunks_count} chunks · {document.year || "年份待识别"}</div>
                    </div>
                    <ParseStatus status={document.parse_status} />
                  </div>
                  {document.parse_error ? <p className="mt-2 text-xs text-danger">{document.parse_error}</p> : null}
                </div>
              ))}
              {!documents.length ? <EmptyLine text="上传 PDF 后会生成带页码 chunks" /> : null}
            </div>
          </Panel>
        </aside>

        <section className="space-y-4">
          <Panel title="待核查文本" action={<ModeSelector />}>
            <div className="grid gap-3">
              <input className="field" value={textTitle} onChange={(event) => setTextTitle(event.target.value)} />
              <textarea className="min-h-[240px] resize-y rounded-lg border border-line bg-white px-4 py-3 text-sm leading-7 outline-none focus:border-teal" value={rawText} onChange={(event) => setRawText(event.target.value)} />
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs text-slate">{rawText.length} 字符 · 引用优先限定在上传文献中检索</div>
                <button className="primary-button min-w-[150px]" onClick={handleVerify} disabled={!activeProject || busy}>
                  {busy ? <Loader2 className="animate-spin" size={16} /> : <Play size={16} />}
                  启动核查
                </button>
              </div>
            </div>
          </Panel>

          <Panel title="原文高亮">
            <HighlightedText text={rawText} claims={results?.claims ?? []} />
          </Panel>

          <Panel title="声称级核查表">
            <div className="overflow-x-auto">
              <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
                <thead className="text-xs uppercase text-slate">
                  <tr>
                    <th className="border-b border-line px-3 py-2">Claim</th>
                    <th className="border-b border-line px-3 py-2">判定</th>
                    <th className="border-b border-line px-3 py-2">可信度</th>
                    <th className="border-b border-line px-3 py-2">风险</th>
                  </tr>
                </thead>
                <tbody>
                  {(results?.claims ?? []).map((claim) => (
                    <tr key={claim.claim_id} className="align-top">
                      <td className="max-w-[560px] border-b border-line px-3 py-3 text-ink">{claim.atomic_claim}</td>
                      <td className="border-b border-line px-3 py-3 font-semibold text-ink">{claim.verdict}</td>
                      <td className="border-b border-line px-3 py-3">{claim.confidence.toFixed(1)}</td>
                      <td className="border-b border-line px-3 py-3">
                        <span className={clsx("rounded-md px-2 py-1 text-xs font-semibold", riskClass(claim.risk_level))}>{claim.risk_level}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!results?.claims.length ? <EmptyLine text="核查完成后会显示所有 claim、verdict 和证据引用" /> : null}
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
                <Metric icon={<Workflow size={16} />} label="步骤" value={run?.current_step ?? "idle"} />
                <Metric icon={<Gauge size={16} />} label="状态" value={run?.status ?? "ready"} />
              </div>
              {message ? <p className="rounded-lg bg-panel px-3 py-2 text-xs text-slate">{message}</p> : null}
              {run?.error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-danger">{run.error}</p> : null}
            </div>
          </Panel>

          <Panel title="风险概览">
            <div className="grid grid-cols-2 gap-2">
              <SummaryTile label="总声称" value={results?.summary.total_claims ?? 0} />
              <SummaryTile label="支持" value={results?.summary.supported ?? 0} />
              <SummaryTile label="证据不足" value={results?.summary.insufficient_evidence ?? 0} />
              <SummaryTile label="引用错配" value={results?.summary.citation_mismatch ?? 0} />
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
    <select className="rounded-lg border border-line bg-white px-3 py-2 text-xs font-semibold text-ink outline-none focus:border-teal" defaultValue="strict_paper">
      <option value="strict_paper">严格论文模式</option>
      <option value="quick">快速模式</option>
      <option value="citation">指定文献模式</option>
    </select>
  );
}

function ParseStatus({ status }: { status: string }) {
  const ok = status === "completed";
  const failed = status === "failed";
  return (
    <span className={clsx("inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold", ok ? "bg-emerald-50 text-emerald-700" : failed ? "bg-red-50 text-danger" : "bg-amber-50 text-amber")}>
      {ok ? <CheckCircle2 size={13} /> : failed ? <AlertTriangle size={13} /> : <Loader2 className="animate-spin" size={13} />}
      {status}
    </span>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <p className="rounded-lg bg-panel px-3 py-4 text-center text-xs text-slate">{text}</p>;
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

function HighlightedText({ text, claims }: { text: string; claims: ClaimResult[] }) {
  if (!claims.length) {
    return <p className="whitespace-pre-wrap text-sm leading-7 text-ink">{text}</p>;
  }
  const sorted = [...claims].sort((a, b) => a.char_start - b.char_start);
  const nodes: React.ReactNode[] = [];
  let cursor = 0;
  sorted.forEach((claim) => {
    if (claim.char_start > cursor) nodes.push(<span key={`plain-${cursor}`}>{text.slice(cursor, claim.char_start)}</span>);
    nodes.push(
      <mark key={claim.claim_id} className={clsx("rounded px-1 py-0.5", claim.risk_level === "low" ? "bg-emerald-100" : claim.risk_level === "medium" ? "bg-sky-100" : claim.risk_level === "high" ? "bg-amber-100" : "bg-red-100")}>
        {text.slice(claim.char_start, claim.char_end)}
      </mark>
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
        <div className="text-xs font-semibold uppercase text-slate">当前 Claim</div>
        <p className="mt-2 text-sm leading-6 text-ink">{claim.atomic_claim}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className={clsx("rounded-md px-2 py-1 text-xs font-semibold", riskClass(claim.risk_level))}>{claim.verdict}</span>
          <span className="rounded-md bg-white px-2 py-1 text-xs font-semibold text-slate">{claim.confidence.toFixed(1)} / 100</span>
        </div>
      </div>
      <p className="text-sm leading-6 text-slate">{claim.explanation}</p>
      {claim.evidences.map((evidence) => (
        <article key={evidence.id} className="rounded-lg border border-line p-3">
          <div className="flex items-start gap-2">
            <FileText className="mt-0.5 text-teal" size={16} />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-ink">{evidence.document_title || "未命名文献"}</div>
              <div className="text-xs text-slate">Page {evidence.page_start}-{evidence.page_end} · {evidence.relation}</div>
            </div>
          </div>
          <p className="mt-3 line-clamp-6 text-xs leading-5 text-slate">{evidence.evidence_text}</p>
        </article>
      ))}
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

