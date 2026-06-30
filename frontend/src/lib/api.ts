import type { DocumentRecord, InputText, Project, Run, RunResults } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const APP_ACCESS_TOKEN = process.env.NEXT_PUBLIC_APP_ACCESS_TOKEN || "dev-token";

type JsonValue = Record<string, unknown> | unknown[];

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("X-Access-Token", APP_ACCESS_TOKEN);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, cache: "no-store" });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  baseUrl: API_BASE_URL,
  token: APP_ACCESS_TOKEN,

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

  createInputText(projectId: string, payload: { title: string; raw_text: string; section_type: string; citation_style: string }) {
    return request<InputText>(`/api/projects/${projectId}/input-texts`, { method: "POST", body: JSON.stringify(payload) });
  },

  startVerification(inputTextId: string) {
    return request<Run>(`/api/input-texts/${inputTextId}/verify`, {
      method: "POST",
      body: JSON.stringify({
        mode: "strict_paper",
        retrieval_top_k: 12,
        evidence_top_n: 5,
        external_search_enabled: false,
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

  exportUrl(runId: string) {
    return `${API_BASE_URL}/api/runs/${runId}/export?format=markdown`;
  }
};


