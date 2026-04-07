import type {
  WorkoutProgram,
  StartWorkoutResponse,
  WorkoutSessionData,
  LoggedSet,
  CompleteWorkoutResponse,
  ExerciseHistoryEntry,
} from "./types";

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

  const res = await fetch(`/api${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.text();
    let message = `Request failed (${res.status})`;
    try {
      const json = JSON.parse(body);
      message = json.detail || json.message || message;
    } catch {
      // use default
    }
    throw new Error(message);
  }

  return res.json();
}

// Program
export function getActiveProgram(): Promise<{ program: WorkoutProgram | null }> {
  return fetchApi("/workout/program");
}

export function generateProgram(coach: string): Promise<{ program: WorkoutProgram }> {
  return fetchApi("/workout/program/generate", {
    method: "POST",
    body: JSON.stringify({ coach }),
  });
}

// Sessions
export function startWorkout(dayId: string): Promise<StartWorkoutResponse> {
  return fetchApi("/workout/start", {
    method: "POST",
    body: JSON.stringify({ day_id: dayId }),
  });
}

export function getSession(sessionId: string): Promise<WorkoutSessionData> {
  return fetchApi(`/workout/session/${sessionId}`);
}

export function logSet(
  sessionId: string,
  exerciseId: string,
  setNumber: number,
  weightKg: number,
  reps: number
): Promise<LoggedSet> {
  return fetchApi(`/workout/session/${sessionId}/log`, {
    method: "POST",
    body: JSON.stringify({
      exercise_id: exerciseId,
      set_number: setNumber,
      weight_kg: weightKg,
      reps: reps,
    }),
  });
}

export function completeWorkout(sessionId: string): Promise<CompleteWorkoutResponse> {
  return fetchApi(`/workout/session/${sessionId}/complete`, {
    method: "POST",
  });
}

export function getWorkoutHistory(): Promise<WorkoutSessionData[]> {
  return fetchApi("/workout/history");
}

export function getExerciseHistory(exerciseId: string): Promise<ExerciseHistoryEntry[]> {
  return fetchApi(`/workout/exercise/${exerciseId}/history`);
}
