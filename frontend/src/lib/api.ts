import type { ClaimResult, DocumentRecord, EvidenceSource, InputText, Project, ReviewStatus, Run, RunResults, VersionInfo } from "./types";

const API_PROXY_BASE = "/api/backend";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_PROXY_BASE}${path}`, { ...options, headers, cache: "no-store" });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  baseUrl: API_PROXY_BASE,

  getVersion() {
    return request<VersionInfo>("/api/version");
  },

  listProjects() {
    return request<Project[]>("/api/projects");
  },

  createProject(payload: { name: string; description?: string; verification_mode?: string }) {
    return request<Project>("/api/projects", { method: "POST", body: JSON.stringify(payload) });
  },

  listDocuments(projectId: string) {
    return request<DocumentRecord[]>(`/api/projects/${projectId}/documents`);
  },

  uploadDocument(projectId: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    form.append("source_type", "pdf");
    return request<DocumentRecord>(`/api/projects/${projectId}/documents`, { method: "POST", body: form });
  },

  deleteDocument(documentId: string) {
    return request<void>(`/api/documents/${documentId}`, { method: "DELETE" });
  },

  retryDocument(documentId: string) {
    return request<DocumentRecord>(`/api/documents/${documentId}/retry`, { method: "POST" });
  },

  createInputText(projectId: string, payload: { title: string; raw_text: string; section_type: string; citation_style: string }) {
    return request<InputText>(`/api/projects/${projectId}/input-texts`, { method: "POST", body: JSON.stringify(payload) });
  },

  startVerification(inputTextId: string, options: { evidence_source: EvidenceSource }) {
    return request<Run>(`/api/input-texts/${inputTextId}/verify`, {
      method: "POST",
      body: JSON.stringify({
        mode: "strict_paper",
        evidence_source: options.evidence_source,
        retrieval_top_k: 12,
        evidence_top_n: 5,
        external_search_enabled: options.evidence_source === "openalex",
        check_citations: true,
        check_reference_authenticity: true
      })
    });
  },

  getRun(runId: string) {
    return request<Run>(`/api/runs/${runId}`);
  },

  getResults(runId: string) {
    return request<RunResults>(`/api/runs/${runId}/results`);
  },

  reviewResult(resultId: string, payload: { review_status: ReviewStatus; review_note?: string | null }) {
    return request<ClaimResult>(`/api/verification-results/${resultId}/review`, { method: "PATCH", body: JSON.stringify(payload) });
  },

  exportUrl(runId: string) {
    return `${API_PROXY_BASE}/api/runs/${runId}/export?format=markdown`;
  }
};


