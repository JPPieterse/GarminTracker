import type {
  User,
  ChartDataPoint,
  StatsResponse,
  AskResponse,
  SyncResult,
  ModelInfo,
  Coach,
  PatientSummary,
  SubscriptionInfo,
  SharingLink,
  PatientDetail,
  SleepBreakdown,
  ActivitySummary,
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
  provider: string;
}> {
  return fetchApi("/auth/config");
}

// Garmin
export function connectGarmin(
  email: string,
  password: string
): Promise<{ status: string }> {
  return fetchApi("/auth/garmin/connect", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function disconnectGarmin(): Promise<void> {
  return fetchApi("/auth/garmin/disconnect", { method: "POST" });
}

// Chat History
export function getChatHistory(
  limit?: number
): Promise<{ role: string; content: string; created_at: string | null }[]> {
  const params = limit ? `?limit=${limit}` : "";
  return fetchApi(`/health/chat/history${params}`);
}

// Health Profile
export function getProfile(): Promise<{ context: string }> {
  return fetchApi("/auth/profile");
}

export function updateProfile(context: string): Promise<{ status: string }> {
  return fetchApi("/auth/profile", {
    method: "PUT",
    body: JSON.stringify({ context }),
  });
}

export function syncData(): Promise<SyncResult> {
  return fetchApi("/health/sync", { method: "POST", body: JSON.stringify({}) });
}

export async function analyzeMeal(
  image: File,
  message?: string,
  coach?: string
): Promise<AskResponse> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const formData = new FormData();
  formData.append("image", image);
  if (message) formData.append("message", message);
  if (coach) formData.append("coach", coach);

  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch("/api/health/meal/analyze", {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const body = await res.text();
    let msg = `Request failed (${res.status})`;
    try {
      const json = JSON.parse(body);
      msg = json.detail || json.message || msg;
    } catch {
      // use default
    }
    throw new ApiError(msg, res.status);
  }

  return res.json();
}

// AI
export function askQuestion(
  question: string,
  model?: string,
  coach?: string
): Promise<AskResponse> {
  return fetchApi("/health/ask", {
    method: "POST",
    body: JSON.stringify({ question, model, coach }),
  });
}

export function getCoaches(): Promise<Coach[]> {
  return fetchApi("/health/coaches");
}

export function getModels(): Promise<ModelInfo[]> {
  return fetchApi("/health/models");
}

// Data
export function getChart(
  metric: string,
  days?: number
): Promise<ChartDataPoint[]> {
  const params = days ? `?days=${days}` : "";
  return fetchApi(`/health/chart/${metric}${params}`);
}

export function getStats(): Promise<StatsResponse> {
  return fetchApi("/health/stats");
}

// Onboarding
export function getOnboardingStatus(): Promise<{ needs_onboarding: boolean }> {
  return fetchApi("/health/onboarding/status");
}

export function sendOnboardingMessage(
  message: string,
  history: { role: string; content: string }[]
): Promise<{
  reply: string;
  history: { role: string; content: string }[];
  complete: boolean;
}> {
  return fetchApi("/health/onboarding/chat", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
}

export function getSleepBreakdown(days?: number): Promise<SleepBreakdown[]> {
  const params = days ? `?days=${days}` : "";
  return fetchApi(`/health/sleep/breakdown${params}`);
}

export function getActivities(days?: number): Promise<ActivitySummary[]> {
  const params = days ? `?days=${days}` : "";
  return fetchApi(`/health/activities/summary${params}`);
}

export function exportData(format: string = "json"): Promise<Blob> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;
  return fetch(`/api/health/export?format=${format}`, {
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
  return fetchApi("/health/account", { method: "DELETE" });
}
