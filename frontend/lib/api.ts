import type {
  AgentRunResponse,
  ApplicationDetailResponse,
  ApplicationListItem,
  JobDetailResponse,
  JobsPageResponse,
  MetricsResponse,
  ResumeProfile,
  UserPreferences,
} from "../types/api";
import { errorCopy } from "./errors";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type QueryValue = string | number | boolean | null | undefined;

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    const copy = errorCopy(code, message);
    super(`${copy.message} ${copy.action}`.trim());
    this.status = status;
    this.code = code;
  }
}

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem("autohire_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function queryString(params: Record<string, QueryValue | QueryValue[]>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.filter(Boolean).forEach((item) => search.append(key, String(item)));
    } else if (value !== null && value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  });
  const result = search.toString();
  return result ? `?${result}` : "";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormData = init.body instanceof FormData;
  const headers = new Headers(init.headers);
  if (!isFormData) headers.set("Content-Type", "application/json");
  Object.entries(authHeaders()).forEach(([key, value]) => headers.set(key, value));

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let message = response.statusText;
    let code = "ERROR";
    try {
      const payload = await response.json();
      code = payload.error ?? payload.detail?.error ?? code;
      message = payload.message ?? payload.detail?.message ?? message;
    } catch {
      // Keep status text.
    }
    throw new ApiError(response.status, code, message);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  async uploadResume(file: File) {
    const formData = new FormData();
    formData.append("file", file);
    return request<{ resume_id: string; status: string; profile: ResumeProfile }>(
      "/api/resume/upload",
      { method: "POST", body: formData },
    );
  },

  getProfile() {
    return request<{
      resume_id: string;
      profile: ResumeProfile;
      preferences: UserPreferences;
    }>("/api/profile");
  },

  updateProfile(payload: Partial<ResumeProfile & UserPreferences>) {
    return request<{ status: string; updated_fields: string[] }>("/api/profile", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  getProfileCompleteness() {
    return request<{ score: number; missing_fields: string[] }>("/api/profile/completeness");
  },

  listJobs(params: Record<string, QueryValue | QueryValue[]> = {}) {
    return request<JobsPageResponse>(`/api/jobs${queryString(params)}`);
  },

  getJob(jobId: string) {
    return request<JobDetailResponse>(`/api/jobs/${jobId}`);
  },

  queueJob(jobId: string) {
    return request<{ job_id: string; application_id: string; status: string }>(
      `/api/jobs/${jobId}/queue`,
      { method: "POST" },
    );
  },

  skipJob(jobId: string) {
    return request<{ job_id: string; status: string }>(`/api/jobs/${jobId}/skip`, {
      method: "POST",
    });
  },

  runAgent() {
    return request<AgentRunResponse>("/api/agent/run", { method: "POST" });
  },

  stopAgent() {
    return request<{ status: string; message: string }>("/api/agent/stop", {
      method: "POST",
    });
  },

  getAgentStatus() {
    return request<Record<string, unknown>>("/api/agent/status");
  },

  listApplications(params: Record<string, QueryValue | QueryValue[]> = {}) {
    return request<ApplicationListItem[]>(`/api/applications${queryString(params)}`);
  },

  getApplication(applicationId: string) {
    return request<ApplicationDetailResponse>(`/api/applications/${applicationId}`);
  },

  updateApplicationStatus(applicationId: string, status: string) {
    return request<{ application_id: string; status: string }>(`/api/applications/${applicationId}/status`, {
      method: "PUT",
      body: JSON.stringify({ status }),
    });
  },

  submitApplication(applicationId: string) {
    return request<{ application_id: string; status: string }>(
      `/api/applications/${applicationId}/submit`,
      { method: "POST" },
    );
  },

  getMetrics() {
    return request<MetricsResponse>("/api/metrics");
  },

  testTelegram(payload: { bot_token?: string; chat_id?: string }) {
    return request<{ status: string }>("/api/settings/telegram/test", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  saveBoardLogin(board: string, wait_seconds = 180) {
    return request<{ status: string; board: string }>(`/api/boards/${board}/login`, {
      method: "POST",
      body: JSON.stringify({ wait_seconds }),
    });
  },

  submitFeedback(payload: {
    application_id?: string;
    trace_id?: string;
    message: string;
    screenshot?: File | null;
  }) {
    const formData = new FormData();
    if (payload.application_id) formData.append("application_id", payload.application_id);
    if (payload.trace_id) formData.append("trace_id", payload.trace_id);
    formData.append("message", payload.message);
    if (payload.screenshot) formData.append("screenshot", payload.screenshot);
    return request<{ status: string; url?: string; path?: string }>("/api/feedback", {
      method: "POST",
      body: formData,
    });
  },

  fileUrl(path: string) {
    return `${API_BASE}${path}`;
  },
};
