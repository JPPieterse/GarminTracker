"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ClipboardList, Dumbbell, Play, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import { getActiveProgram, generateProgram, startWorkout } from "@/lib/workout-api";
import type { WorkoutProgram, ProgramDay } from "@/lib/types";

export default function ProgramPage() {
  const router = useRouter();
  const [program, setProgram] = useState<WorkoutProgram | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getActiveProgram()
      .then((data) => setProgram(data.program))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleGenerate = async () => {
    const coachId = localStorage.getItem("selectedCoach") || "aria";
    setGenerating(true);
    setError("");
    try {
      const data = await generateProgram(coachId);
      setProgram(data.program);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate program");
    } finally {
      setGenerating(false);
    }
  };

  const handleStartWorkout = async (dayId: string) => {
    setStarting(dayId);
    try {
      const data = await startWorkout(dayId);
      router.push(`/dashboard/program/workout/${data.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start workout");
      setStarting(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size={48} />
      </div>
    );
  }

  // Empty state
  if (!program) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <ClipboardList size={48} className="text-[#888] mx-auto mb-4" />
          <h1 className="text-2xl font-heading font-bold text-[#e0e0e0] mb-2">
            No Program Yet
          </h1>
          <p className="text-[#888] mb-6 max-w-md">
            Ask your coach to build a personalized training program based on
            your goals, experience, and schedule.
          </p>
          {error && (
            <p className="text-red-400 text-sm mb-4">{error}</p>
          )}
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="flex items-center gap-2 px-6 py-3 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors disabled:opacity-50 mx-auto"
          >
            {generating ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Dumbbell size={18} />
                Generate My Program
              </>
            )}
          </button>
        </motion.div>
      </div>
    );
  }

  // Program view
  const days: ProgramDay[] = program.program_data?.days || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-heading font-bold text-[#e0e0e0]">
            {program.name}
          </h1>
          <p className="text-sm text-[#888] mt-1">
            {days.length} training days · Created by your coach
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 text-sm border border-border text-[#888] rounded-lg hover:text-[#e0e0e0] hover:border-brand/30 transition-colors disabled:opacity-50"
        >
          {generating ? "Regenerating..." : "Regenerate Program"}
        </button>
      </div>

      {/* Coach's training note */}
      {program.coach_note && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-card border border-brand/20 rounded-xl p-5"
        >
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">💬</span>
            <p className="text-xs text-brand font-medium uppercase tracking-wider">
              Coach&apos;s Note
            </p>
          </div>
          <p className="text-sm text-[#ccc] leading-relaxed">
            {program.coach_note}
          </p>
        </motion.div>
      )}

      {error && (
        <p className="text-red-400 text-sm">{error}</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {days.map((day, i) => (
          <motion.div
            key={day.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="bg-card border border-border rounded-xl p-5 hover:border-brand/20 transition-colors"
          >
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-xs text-brand uppercase tracking-wider">
                  {day.day_label}
                </p>
                <h2 className="text-lg font-heading font-semibold text-[#e0e0e0]">
                  {day.name}
                </h2>
              </div>
            </div>

            <div className="space-y-1.5 mb-4">
              {day.exercises.map((ex) => (
                <div
                  key={ex.id}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-[#ccc] truncate flex-1">
                    {ex.name}
                  </span>
                  <span className="text-[#888] text-xs ml-2 whitespace-nowrap">
                    {ex.sets} sets · {ex.rep_range} reps
                  </span>
                </div>
              ))}
            </div>

            <button
              onClick={() => handleStartWorkout(day.id)}
              disabled={starting === day.id}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-brand/10 text-brand font-semibold rounded-lg border border-brand/20 hover:bg-brand hover:text-dark transition-all text-sm disabled:opacity-50"
            >
              {starting === day.id ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Play size={16} />
              )}
              {starting === day.id ? "Starting..." : "Start Workout"}
            </button>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
