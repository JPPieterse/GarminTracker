import type {
  User,
  ChartDataPoint,
  StatsResponse,
  AskResponse,
  SyncResult,
  ModelInfo,
  PatientSummary,
  SubscriptionInfo,
  SharingLink,
  PatientDetail,
} from "./types";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function fetchApi<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`/api${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.text();
    let message = `Request failed (${res.status})`;
    try {
      const json = JSON.parse(body);
      message = json.detail || json.message || message;
    } catch {
      // use default message
    }
    throw new ApiError(message, res.status);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// Auth
export function getMe(): Promise<User> {
  return fetchApi<User>("/auth/me");
}

export function getAuthConfig(): Promise<{
  configured: boolean;
  domain?: string;
  client_id?: string;
  audience?: string;
}> {
  return fetchApi("/auth/config");
}

// Garmin
export function connectGarmin(): Promise<{ redirect_url: string }> {
  return fetchApi("/garmin/connect", { method: "POST" });
}

export function disconnectGarmin(): Promise<void> {
  return fetchApi("/garmin/disconnect", { method: "POST" });
}

export function syncData(): Promise<SyncResult> {
  return fetchApi("/garmin/sync", { method: "POST" });
}

// AI
export function askQuestion(
  question: string,
  model?: string
): Promise<AskResponse> {
  return fetchApi("/ask", {
    method: "POST",
    body: JSON.stringify({ question, model }),
  });
}

export function getModels(): Promise<ModelInfo[]> {
  return fetchApi("/models");
}

// Data
export function getChart(
  metric: string,
  days?: number
): Promise<ChartDataPoint[]> {
  const params = new URLSearchParams({ metric });
  if (days) params.set("days", String(days));
  return fetchApi(`/chart?${params}`);
}

export function getStats(): Promise<StatsResponse> {
  return fetchApi("/stats");
}

export function exportData(format: string = "json"): Promise<Blob> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;
  return fetch(`/api/export?format=${format}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  }).then((res) => {
    if (!res.ok) throw new ApiError("Export failed", res.status);
    return res.blob();
  });
}

// Doctor
export function getDoctorPatients(): Promise<PatientSummary[]> {
  return fetchApi("/doctor/patients");
}

export function invitePatient(
  email: string,
  permissions: string[]
): Promise<{ status: string }> {
  return fetchApi("/doctor/invite", {
    method: "POST",
    body: JSON.stringify({ email, permissions }),
  });
}

export function getPatientData(patientId: string): Promise<PatientDetail> {
  return fetchApi(`/doctor/patients/${patientId}`);
}

// Sharing
export function getSharingLinks(): Promise<SharingLink[]> {
  return fetchApi("/sharing/links");
}

export function acceptInvite(linkId: string): Promise<{ status: string }> {
  return fetchApi(`/sharing/accept/${linkId}`, { method: "POST" });
}

export function revokeLink(linkId: string): Promise<void> {
  return fetchApi(`/sharing/links/${linkId}`, { method: "DELETE" });
}

// Subscription
export function getSubscription(): Promise<SubscriptionInfo> {
  return fetchApi("/subscription");
}

export function createCheckout(
  tier: string
): Promise<{ checkout_url: string }> {
  return fetchApi("/subscription/checkout", {
    method: "POST",
    body: JSON.stringify({ tier }),
  });
}

export function cancelSubscription(): Promise<void> {
  return fetchApi("/subscription/cancel", { method: "POST" });
}

// Account
export function deleteAccount(): Promise<void> {
  return fetchApi("/account", { method: "DELETE" });
}
