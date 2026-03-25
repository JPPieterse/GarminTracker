export interface HealthMetric {
  id: string;
  date: string;
  metric_type: string;
  value: number;
  unit: string;
}

export interface DailySummary {
  date: string;
  steps: number;
  heart_rate_avg: number;
  heart_rate_max: number;
  heart_rate_min: number;
  sleep_hours: number;
  calories: number;
  active_minutes: number;
  stress_avg: number;
}

export interface AskRequest {
  question: string;
  model?: string;
}

export interface AskResponse {
  answer: string;
  model: string;
  tokens_used: number;
}

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  plan: "free" | "pro";
  garmin_connected: boolean;
  ai_queries_used: number;
  ai_queries_limit: number;
}

export interface SyncStatus {
  last_sync: string | null;
  is_syncing: boolean;
  records_synced: number;
}
