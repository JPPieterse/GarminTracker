"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Minus,
  Plus,
  Trophy,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import {
  getActiveProgram,
  getSession,
  logSet,
  completeWorkout,
} from "@/lib/workout-api";
import type {
  ProgramDay,
  ProgramExercise,
  LoggedSet,
  CompleteWorkoutResponse,
} from "@/lib/types";

// ── Focused Exercise View ───────────────────────────────────────────────

function FocusedExercise({
  exercise,
  exerciseIndex,
  totalExercises,
  sessionId,
  loggedSets,
  lastWeight,
  onSetLogged,
  onBack,
}: {
  exercise: ProgramExercise;
  exerciseIndex: number;
  totalExercises: number;
  sessionId: string;
  loggedSets: LoggedSet[];
  lastWeight: number;
  onSetLogged: (set: LoggedSet) => void;
  onBack: () => void;
}) {
  const completedSets = loggedSets.filter(
    (s) => s.exercise_id === exercise.id
  ).length;
  const nextSetNumber = completedSets + 1;
  const allSetsComplete = completedSets >= exercise.sets;

  const [weight, setWeight] = useState(lastWeight || 20);
  const [reps, setReps] = useState(
    parseInt(exercise.rep_range.split("-")[0]) || 8
  );
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [logging, setLogging] = useState(false);

  const repRange = exercise.rep_range.split("-").map(Number);
  const minReps = repRange[0] || 4;
  const maxReps = repRange[1] || repRange[0] || 12;

  const handleLog = async () => {
    if (allSetsComplete || logging) return;
    setLogging(true);
    try {
      const result = await logSet(
        sessionId,
        exercise.id,
        nextSetNumber,
        weight,
        reps
      );
      onSetLogged(result);
    } catch (err) {
      console.error(err);
    } finally {
      setLogging(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-sm text-[#888] hover:text-[#e0e0e0] transition-colors"
        >
          <ArrowLeft size={16} />
          Back
        </button>
        <div className="flex gap-1">
          {Array.from({ length: totalExercises }).map((_, i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full ${
                i < exerciseIndex
                  ? "bg-green-500"
                  : i === exerciseIndex
                  ? "bg-brand"
                  : "bg-[#2a2d37]"
              }`}
            />
          ))}
        </div>
        <span className="text-sm text-[#888]">
          {exerciseIndex + 1} of {totalExercises}
        </span>
      </div>

      {/* Exercise name */}
      <div className="text-center">
        <h2 className="text-2xl font-heading font-bold text-[#e0e0e0]">
          {exercise.name}
        </h2>
        <p className="text-brand text-sm mt-1">
          {exercise.sets} sets · {exercise.rep_range} reps
          {lastWeight > 0 && (
            <span className="text-[#888]"> · Last: {lastWeight}kg</span>
          )}
        </p>
      </div>

      {/* Expandable details */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <button
          onClick={() => setDetailsOpen(!detailsOpen)}
          className="w-full flex items-center justify-between p-4 text-sm text-[#888] hover:text-[#e0e0e0] transition-colors"
        >
          <span>Exercise Details</span>
          {detailsOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        <AnimatePresence>
          {detailsOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="px-4 pb-4 space-y-2 border-t border-border pt-3">
                <p className="text-sm text-[#ccc]">{exercise.description}</p>
                <p className="text-sm text-green-400">
                  🔥 {exercise.muscles_targeted.join(", ")}
                </p>
                <p className="text-sm text-red-400">
                  ⚠️ {exercise.muscles_warning}
                </p>
                <p className="text-sm text-[#888]">
                  💡 {exercise.form_cues}
                </p>
                <a
                  href={`https://www.youtube.com/results?search_query=${encodeURIComponent(exercise.youtube_search)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-brand hover:underline"
                >
                  <ExternalLink size={12} />
                  Watch form video
                </a>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Completed sets */}
      {completedSets > 0 && (
        <div className="space-y-2">
          {loggedSets
            .filter((s) => s.exercise_id === exercise.id)
            .sort((a, b) => a.set_number - b.set_number)
            .map((s) => (
              <div
                key={s.set_number}
                className="flex items-center justify-between bg-card border border-border rounded-lg px-4 py-2 opacity-60"
              >
                <span className="text-sm text-[#888]">
                  Set {s.set_number}
                </span>
                <span className="text-sm text-green-400 font-medium">
                  {s.weight_kg}kg × {s.reps} ✓
                </span>
              </div>
            ))}
        </div>
      )}

      {/* Weight/rep input */}
      {!allSetsComplete && (
        <div className="bg-card border border-brand/30 rounded-xl p-5 space-y-5">
          <div className="text-center text-sm text-brand font-medium">
            Set {nextSetNumber} of {exercise.sets}
          </div>

          {/* Weight */}
          <div className="text-center">
            <div className="text-xs text-[#888] uppercase tracking-wider mb-2">
              Weight
            </div>
            <div className="flex items-center justify-center gap-4">
              <button
                onClick={() => setWeight(Math.max(0, weight - 2.5))}
                className="w-11 h-11 rounded-full bg-dark border border-border flex items-center justify-center text-[#888] hover:text-[#e0e0e0] transition-colors"
              >
                <Minus size={18} />
              </button>
              <div className="text-4xl font-bold text-brand min-w-[100px]">
                {weight}
                <span className="text-base text-[#888] ml-1">kg</span>
              </div>
              <button
                onClick={() => setWeight(weight + 2.5)}
                className="w-11 h-11 rounded-full bg-dark border border-border flex items-center justify-center text-[#888] hover:text-[#e0e0e0] transition-colors"
              >
                <Plus size={18} />
              </button>
            </div>
            <div className="flex justify-center gap-2 mt-3">
              {[-5, -2.5, 0, 2.5, 5].map((delta) => (
                <button
                  key={delta}
                  onClick={() =>
                    delta === 0
                      ? setWeight(lastWeight || weight)
                      : setWeight(Math.max(0, weight + delta))
                  }
                  className={`px-3 py-1 rounded-md text-xs transition-colors ${
                    delta === 0
                      ? "bg-brand text-dark font-semibold"
                      : "bg-dark border border-border text-[#888] hover:text-[#e0e0e0]"
                  }`}
                >
                  {delta === 0 ? "Same" : delta > 0 ? `+${delta}` : delta}
                </button>
              ))}
            </div>
          </div>

          {/* Reps */}
          <div className="text-center">
            <div className="text-xs text-[#888] uppercase tracking-wider mb-2">
              Reps
            </div>
            <div className="flex justify-center gap-2">
              {Array.from(
                { length: maxReps - minReps + 3 },
                (_, i) => minReps - 1 + i
              )
                .filter((r) => r >= 1)
                .map((r) => (
                  <button
                    key={r}
                    onClick={() => setReps(r)}
                    className={`w-10 h-10 rounded-lg text-sm font-medium transition-colors ${
                      reps === r
                        ? "bg-brand/20 border border-brand text-brand"
                        : "bg-dark border border-border text-[#888] hover:text-[#e0e0e0]"
                    }`}
                  >
                    {r}
                  </button>
                ))}
            </div>
          </div>

          {/* Log button */}
          <button
            onClick={handleLog}
            disabled={logging}
            className="w-full py-3.5 bg-brand text-dark font-bold rounded-xl text-lg hover:bg-brand/90 transition-colors disabled:opacity-50"
          >
            {logging ? "Logging..." : "Log Set ✓"}
          </button>
        </div>
      )}

      {/* All sets complete */}
      {allSetsComplete && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 text-center">
          <Check size={24} className="text-green-400 mx-auto mb-1" />
          <p className="text-green-400 font-medium">All sets complete!</p>
          <button
            onClick={onBack}
            className="text-sm text-[#888] hover:text-[#e0e0e0] mt-2 transition-colors"
          >
            Back to exercise list
          </button>
        </div>
      )}
    </div>
  );
}

// ── Debrief Screen ──────────────────────────────────────────────────────

function DebriefScreen({
  debrief,
  durationMin,
  totalSets,
}: {
  debrief: CompleteWorkoutResponse;
  durationMin: number | null;
  totalSets: number;
}) {
  const router = useRouter();

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-lg mx-auto space-y-6 py-8"
    >
      <div className="text-center">
        <Trophy size={48} className="text-brand mx-auto mb-3" />
        <h2 className="text-2xl font-heading font-bold text-[#e0e0e0]">
          Workout Complete!
        </h2>
      </div>

      <div className="flex justify-center gap-6 text-center">
        <div>
          <p className="text-2xl font-bold text-[#e0e0e0]">{totalSets}</p>
          <p className="text-xs text-[#888]">Total Sets</p>
        </div>
        {durationMin && (
          <div>
            <p className="text-2xl font-bold text-[#e0e0e0]">{durationMin}</p>
            <p className="text-xs text-[#888]">Minutes</p>
          </div>
        )}
      </div>

      <div className="bg-card border border-border rounded-xl p-5">
        <p className="text-xs text-brand font-medium mb-2 uppercase tracking-wider">
          Coach Debrief
        </p>
        <p className="text-sm text-[#e0e0e0] leading-relaxed whitespace-pre-wrap">
          {debrief.coach_debrief}
        </p>
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => router.push("/dashboard/program")}
          className="flex-1 py-3 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors"
        >
          Done
        </button>
        <button
          onClick={() => router.push("/dashboard/ask")}
          className="flex-1 py-3 border border-border text-[#888] rounded-lg hover:text-[#e0e0e0] hover:border-brand/30 transition-colors"
        >
          Chat with Coach
        </button>
      </div>
    </motion.div>
  );
}

// ── Main Workout Page ───────────────────────────────────────────────────

export default function WorkoutPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const router = useRouter();

  const [day, setDay] = useState<ProgramDay | null>(null);
  const [loggedSets, setLoggedSets] = useState<LoggedSet[]>([]);
  const [lastWeights, setLastWeights] = useState<Record<string, number>>({});
  const [focusedExercise, setFocusedExercise] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState(false);
  const [debrief, setDebrief] = useState<CompleteWorkoutResponse | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [programRes, sessionRes] = await Promise.all([
          getActiveProgram(),
          getSession(sessionId),
        ]);

        if (programRes.program) {
          const d = programRes.program.program_data.days.find(
            (d) => d.id === sessionRes.day_id
          );
          setDay(d || null);
        }
        setLoggedSets(sessionRes.sets);

        // Get last weights from the start response stored in URL or reload
        // For simplicity, calculate from session data or default to 0
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sessionId]);

  const handleSetLogged = (newSet: LoggedSet) => {
    setLoggedSets((prev) => [...prev, newSet]);
    // Update last weights
    setLastWeights((prev) => ({
      ...prev,
      [newSet.exercise_id]: newSet.weight_kg,
    }));
  };

  const handleComplete = async () => {
    setCompleting(true);
    try {
      const result = await completeWorkout(sessionId);
      setDebrief(result);
    } catch (err) {
      console.error(err);
    } finally {
      setCompleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size={48} />
      </div>
    );
  }

  if (debrief) {
    return (
      <DebriefScreen
        debrief={debrief}
        durationMin={debrief.duration_min}
        totalSets={debrief.total_sets}
      />
    );
  }

  if (!day) {
    return (
      <div className="text-center py-16">
        <p className="text-red-400">Could not load workout data.</p>
        <button
          onClick={() => router.push("/dashboard/program")}
          className="mt-4 text-brand hover:underline text-sm"
        >
          Back to Program
        </button>
      </div>
    );
  }

  // Focused view
  if (focusedExercise !== null) {
    const exercise = day.exercises[focusedExercise];
    return (
      <FocusedExercise
        exercise={exercise}
        exerciseIndex={focusedExercise}
        totalExercises={day.exercises.length}
        sessionId={sessionId}
        loggedSets={loggedSets}
        lastWeight={lastWeights[exercise.id] || 0}
        onSetLogged={handleSetLogged}
        onBack={() => setFocusedExercise(null)}
      />
    );
  }

  // Compact list view
  const exerciseCompletion = day.exercises.map((ex) => {
    const sets = loggedSets.filter((s) => s.exercise_id === ex.id);
    return { exercise: ex, completedSets: sets.length, totalSets: ex.sets };
  });

  const totalCompleted = exerciseCompletion.filter(
    (e) => e.completedSets >= e.totalSets
  ).length;

  const allDone = totalCompleted === day.exercises.length;

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.push("/dashboard/program")}
            className="text-xs text-[#888] hover:text-[#e0e0e0] mb-1 flex items-center gap-1 transition-colors"
          >
            <ArrowLeft size={12} /> Program
          </button>
          <p className="text-xs text-brand uppercase tracking-wider">
            {day.day_label}
          </p>
          <h1 className="text-xl font-heading font-bold text-[#e0e0e0]">
            {day.name}
          </h1>
        </div>
        <div className="bg-card border border-border rounded-lg px-3 py-1.5 text-sm text-[#888]">
          {totalCompleted} of {day.exercises.length} done
        </div>
      </div>

      {/* Exercise list */}
      <div className="space-y-2">
        {exerciseCompletion.map(({ exercise, completedSets, totalSets }, i) => {
          const isDone = completedSets >= totalSets;
          const maxWeight = loggedSets
            .filter((s) => s.exercise_id === exercise.id)
            .reduce((max, s) => Math.max(max, s.weight_kg), 0);
          const lastW = lastWeights[exercise.id] || 0;

          return (
            <motion.button
              key={exercise.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => setFocusedExercise(i)}
              className={`w-full text-left bg-card border rounded-xl p-4 transition-all ${
                isDone
                  ? "border-border opacity-60"
                  : "border-brand/30 hover:border-brand/50"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                      isDone
                        ? "bg-green-500 text-dark"
                        : "bg-brand/20 text-brand"
                    }`}
                  >
                    {isDone ? "✓" : i + 1}
                  </div>
                  <div>
                    <p
                      className={`font-semibold text-sm ${
                        isDone ? "text-[#888]" : "text-[#e0e0e0]"
                      }`}
                    >
                      {exercise.name}
                    </p>
                    <p className="text-xs text-[#888]">
                      {exercise.sets} sets · {exercise.rep_range} reps
                      {lastW > 0 && ` · Last: ${lastW}kg`}
                    </p>
                  </div>
                </div>
                {isDone && maxWeight > 0 && (
                  <span className="text-sm text-green-400 font-medium">
                    {maxWeight}kg ✓
                  </span>
                )}
                {!isDone && completedSets > 0 && (
                  <span className="text-xs text-brand">
                    {completedSets}/{totalSets} sets
                  </span>
                )}
              </div>
            </motion.button>
          );
        })}
      </div>

      {/* Complete workout button */}
      {allDone && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <button
            onClick={handleComplete}
            disabled={completing}
            className="w-full py-4 bg-brand text-dark font-bold rounded-xl text-lg hover:bg-brand/90 transition-colors disabled:opacity-50"
          >
            {completing ? "Getting coach debrief..." : "Complete Workout 🎉"}
          </button>
        </motion.div>
      )}
    </div>
  );
}
