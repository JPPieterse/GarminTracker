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

// ── Workout Program Tracker ─────────────────────────────────────────────

export interface ProgramExercise {
  id: string;
  name: string;
  sets: number;
  rep_range: string;
  description: string;
  muscles_targeted: string[];
  muscles_warning: string;
  form_cues: string;
  youtube_search: string;
}

export interface ProgramDay {
  id: string;
  name: string;
  day_label: string;
  exercises: ProgramExercise[];
}

export interface WorkoutProgram {
  id: string;
  name: string;
  coach_id: string;
  program_data: { days: ProgramDay[] };
  created_at?: string;
}

export interface LoggedSet {
  exercise_id: string;
  set_number: number;
  weight_kg: number;
  reps: number;
  logged_at?: string;
}

export interface WorkoutSessionData {
  id: string;
  day_id: string;
  started_at: string;
  finished_at: string | null;
  coach_debrief: string | null;
  sets: LoggedSet[];
}

export interface StartWorkoutResponse {
  session_id: string;
  day_id: string;
  last_weights: Record<string, number>;
}

export interface CompleteWorkoutResponse {
  status: string;
  duration_min: number | null;
  total_sets: number;
  coach_debrief: string;
}

export interface ExerciseHistoryEntry {
  date: string;
  sets: { set: number; weight_kg: number; reps: number }[];
}
