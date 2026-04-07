export interface User {
  id: string;
  email: string;
  name: string;
  picture?: string;
  role?: "user" | "doctor";
  garmin_connected?: boolean;
}

export interface ChartDataPoint {
  date: string;
  value: number;
}

export interface StatsResponse {
  total_days: number;
  total_activities: number;
  date_range: { start: string; end: string };
  ai_queries: number;
}

export interface AskResponse {
  answer: string;
  model: string;
  sources?: string[];
}

export interface SyncResult {
  status: string;
  records_synced: number;
  error?: string | null;
}

export interface ModelInfo {
  id: string;
  name: string;
  description?: string;
}

export interface PatientSummary {
  id: string;
  name: string;
  email: string;
  last_sync?: string;
  permissions: string[];
}

export interface SubscriptionInfo {
  tier: "free" | "pro" | "premium";
  status: string;
  expires_at?: string;
  features: string[];
}

export interface SharingLink {
  id: string;
  doctor_email: string;
  permissions: string[];
  created_at: string;
  status: "active" | "pending" | "revoked";
}

export interface PatientDetail {
  id: string;
  name: string;
  email: string;
  permissions: string[];
  chart_data: Record<string, ChartDataPoint[]>;
  annotations: Annotation[];
}

export interface Coach {
  id: string;
  name: string;
  title: string;
  avatar: string;
  color: string;
  bio: string;
  style: string;
}

export interface Annotation {
  id: string;
  text: string;
  created_at: string;
  metric?: string;
}

export interface SleepBreakdown {
  date: string;
  deep: number | null;
  light: number | null;
  rem: number | null;
  awake: number | null;
  total: number | null;
}

export interface ActivitySummary {
  date: string;
  type: string;
  name: string;
  duration_min: number;
  distance_km: number | null;
  calories: number | null;
  avg_hr: number | null;
  max_hr: number | null;
}
