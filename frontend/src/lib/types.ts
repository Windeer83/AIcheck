export type VersionInfo = {
  backend_version: string;
  build_sha: string | null;
  build_time: string | null;
  database_revision: string | null;
  environment: string;
};

export type Project = {
  id: string;
  name: string;
  description: string | null;
  verification_mode: string;
  created_at: string;
  updated_at: string;
};

export type DocumentRecord = {
  id: string;
  project_id: string;
  title: string | null;
  authors: string[] | null;
  year: number | null;
  doi: string | null;
  source_type: string;
  file_name: string;
  parse_status: string;
  parse_error: string | null;
  metadata_confidence: number;
  chunks_count: number;
  citation_index: number | null;
  created_at: string;
  deleted_at: string | null;
};

export type InputText = {
  id: string;
  project_id: string;
  title: string;
  raw_text: string;
  section_type: string | null;
  citation_style: string | null;
  created_at: string;
};

export type RunLog = {
  id: string;
  run_id: string;
  step: string;
  level: "info" | "warning" | "error" | string;
  message: string;
  created_at: string;
};

export type Run = {
  id: string;
  input_text_id: string;
  status: string;
  progress: number;
  current_step: string;
  claims_total: number;
  claims_checked: number;
  config: Record<string, unknown> | null;
  report_path: string | null;
  error: string | null;
  logs: RunLog[];
  created_at: string;
  updated_at: string;
};

export type Evidence = {
  id: string;
  document_id: string;
  chunk_id: string;
  document_title: string | null;
  evidence_text: string;
  page_start: number;
  page_end: number;
  retrieval_score: number;
  rerank_score: number;
  relation: string | null;
  relevance_score: number;
  entailment_score: number;
  numeric_match: boolean | null;
  explanation: string | null;
  risk_flags: string[] | null;
};

export type ReviewStatus = "unreviewed" | "confirmed" | "suppressed";

export type ClaimResult = {
  result_id: string;
  claim_id: string;
  original_sentence: string;
  atomic_claim: string;
  claim_type: string;
  citation_refs: string[] | null;
  paragraph_index: number;
  sentence_index: number;
  char_start: number;
  char_end: number;
  check_required: boolean;
  verdict: string;
  confidence: number;
  risk_level: "low" | "medium" | "high" | "critical";
  risk_flags: string[];
  explanation: string | null;
  review_status: ReviewStatus;
  review_note: string | null;
  reviewed_at: string | null;
  evidences: Evidence[];
};

export type RunResults = {
  summary: {
    total_claims: number;
    checked_claims: number;
    supported: number;
    partially_supported: number;
    insufficient_evidence: number;
    citation_mismatch: number;
    fabricated_reference: number;
    refuted: number;
    high_risk: number;
    critical_risk: number;
    suppressed: number;
  };
  claims: ClaimResult[];
};

