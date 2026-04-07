"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Calendar,
  Activity,
  CalendarRange,
  Brain,
  RefreshCw,
  Moon,
  Heart,
  Footprints,
} from "lucide-react";
import { motion } from "framer-motion";
import StatsBar from "@/components/shared/StatsBar";
import TrendChart from "@/components/charts/TrendChart";
import SleepChart from "@/components/charts/SleepChart";
import HeartRateChart from "@/components/charts/HeartRateChart";
import ActivityChart from "@/components/charts/ActivityChart";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import {
  getStats,
  getChart,
  getSleepBreakdown,
  getActivities,
  syncData,
} from "@/lib/api";
import type {
  StatsResponse,
  ChartDataPoint,
  SleepBreakdown,
  ActivitySummary,
} from "@/lib/types";

const DAILY_METRICS = [
  { key: "steps", label: "Steps", color: "#4fc3f7" },
  { key: "calories", label: "Calories", color: "#ff8a65" },
  { key: "stress", label: "Stress", color: "#ffa726" },
  { key: "body_battery", label: "Body Battery", color: "#66bb6a" },
  { key: "spo2", label: "SpO2", color: "#42a5f5" },
];

const TIME_RANGES = [
  { days: 7, label: "7d" },
  { days: 14, label: "14d" },
  { days: 30, label: "30d" },
  { days: 60, label: "60d" },
  { days: 90, label: "90d" },
];

export default function DashboardPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [dailyData, setDailyData] = useState<ChartDataPoint[]>([]);
  const [activeMetric, setActiveMetric] = useState(DAILY_METRICS[0]);
  const [days, setDays] = useState(30);
  const [sleepData, setSleepData] = useState<SleepBreakdown[]>([]);
  const [hrResting, setHrResting] = useState<ChartDataPoint[]>([]);
  const [hrMax, setHrMax] = useState<ChartDataPoint[]>([]);
  const [hrMin, setHrMin] = useState<ChartDataPoint[]>([]);
  const [activities, setActivities] = useState<ActivitySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState("");

  const loadAll = useCallback(
    async (metric: string, numDays: number) => {
      const results = await Promise.allSettled([
        getStats(),
        getChart(metric, numDays),
        getSleepBreakdown(numDays),
        getChart("heart_rate", numDays),
        getChart("hr_max", numDays),
        getChart("hr_min", numDays),
        getActivities(numDays),
      ]);

      if (results[0].status === "fulfilled") setStats(results[0].value);
      if (results[1].status === "fulfilled") setDailyData(results[1].value);
      if (results[2].status === "fulfilled") setSleepData(results[2].value);
      if (results[3].status === "fulfilled") setHrResting(results[3].value);
      if (results[4].status === "fulfilled") setHrMax(results[4].value);
      if (results[5].status === "fulfilled") setHrMin(results[5].value);
      if (results[6].status === "fulfilled") setActivities(results[6].value);
    },
    []
  );

  useEffect(() => {
    loadAll(activeMetric.key, days).finally(() => setLoading(false));
  }, [loadAll, activeMetric.key, days]);

  const handleSync = async () => {
    setSyncing(true);
    setSyncMessage("");
    try {
      const result = await syncData();
      if (result.status === "FAILED" && result.error) {
        const msg =
          result.error.includes("429") || result.error.includes("Rate Limit")
            ? "Garmin is rate-limiting requests. Wait 15-30 minutes and try again."
            : result.error.includes("No Garmin credentials")
            ? "Connect your Garmin account first in Settings."
            : `Sync failed: ${result.error}`;
        setSyncMessage(msg);
      } else {
        setSyncMessage(`Synced ${result.records_synced} records successfully!`);
        await loadAll(activeMetric.key, days);
      }
    } catch (err) {
      setSyncMessage(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const handleMetricChange = async (metric: (typeof DAILY_METRICS)[number]) => {
    setActiveMetric(metric);
    const data = await getChart(metric.key, days);
    setDailyData(data);
  };

  const handleDaysChange = (numDays: number) => {
    setDays(numDays);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size={48} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header + Sync */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-heading font-bold text-[#e0e0e0]">
          Dashboard
        </h1>
        <div className="flex items-center gap-3">
          {/* Time range selector */}
          <div className="flex bg-card border border-border rounded-lg overflow-hidden">
            {TIME_RANGES.map((r) => (
              <button
                key={r.days}
                onClick={() => handleDaysChange(r.days)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  days === r.days
                    ? "bg-brand/10 text-brand"
                    : "text-[#888] hover:text-[#e0e0e0]"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center gap-2 px-4 py-2 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors disabled:opacity-50 text-sm"
          >
            <RefreshCw size={14} className={syncing ? "animate-spin" : ""} />
            {syncing ? "Syncing..." : "Sync"}
          </button>
        </div>
      </div>

      {syncMessage && (
        <p
          className={`text-sm ${
            syncMessage.includes("failed") ||
            syncMessage.includes("rate-limiting") ||
            syncMessage.includes("Connect your")
              ? "text-red-400"
              : "text-green-400"
          }`}
        >
          {syncMessage}
        </p>
      )}

      {/* Stats Bar */}
      {stats && (
        <StatsBar
          stats={[
            {
              label: "Days Tracked",
              value: stats.total_days,
              icon: <Calendar size={18} />,
            },
            {
              label: "Activities",
              value: stats.total_activities,
              icon: <Activity size={18} />,
            },
            {
              label: "Date Range",
              value: stats.date_range
                ? `${stats.date_range.start} — ${stats.date_range.end}`
                : "N/A",
              icon: <CalendarRange size={18} />,
            },
            {
              label: "AI Queries",
              value: stats.ai_queries,
              icon: <Brain size={18} />,
            },
          ]}
        />
      )}

      {/* Daily Metrics Chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="bg-card border border-border rounded-xl p-6"
      >
        <div className="flex items-center gap-3 mb-4">
          <Footprints size={20} className="text-brand" />
          <h2 className="text-lg font-heading font-semibold text-[#e0e0e0]">
            Daily Metrics
          </h2>
        </div>
        <div className="flex gap-2 mb-6 overflow-x-auto">
          {DAILY_METRICS.map((m) => (
            <button
              key={m.key}
              onClick={() => handleMetricChange(m)}
              className={`px-4 py-2 rounded-lg text-sm whitespace-nowrap transition-all duration-300 ${
                activeMetric.key === m.key
                  ? "bg-brand/10 text-brand border border-brand/30"
                  : "text-[#888] hover:text-[#e0e0e0] border border-transparent hover:border-border"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <TrendChart
          data={dailyData}
          label={activeMetric.label}
          color={activeMetric.color}
        />
      </motion.div>

      {/* Sleep & Heart Rate side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="bg-card border border-border rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-4">
            <Moon size={20} className="text-[#ab47bc]" />
            <h2 className="text-lg font-heading font-semibold text-[#e0e0e0]">
              Sleep Patterns
            </h2>
          </div>
          <SleepChart data={sleepData} />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
          className="bg-card border border-border rounded-xl p-6"
        >
          <div className="flex items-center gap-3 mb-4">
            <Heart size={20} className="text-[#ef5350]" />
            <h2 className="text-lg font-heading font-semibold text-[#e0e0e0]">
              Heart Rate
            </h2>
          </div>
          <HeartRateChart resting={hrResting} max={hrMax} min={hrMin} />
        </motion.div>
      </div>

      {/* Activities */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.2 }}
        className="bg-card border border-border rounded-xl p-6"
      >
        <div className="flex items-center gap-3 mb-4">
          <Activity size={20} className="text-[#66bb6a]" />
          <h2 className="text-lg font-heading font-semibold text-[#e0e0e0]">
            Activities
          </h2>
          <span className="text-sm text-[#888]">
            {activities.length} activities in the last {days} days
          </span>
        </div>

        {/* Activity scatter plot */}
        <ActivityChart data={activities} />

        {/* Recent activities list */}
        {activities.length > 0 && (
          <div className="mt-6 space-y-2">
            <h3 className="text-sm font-medium text-[#888] uppercase tracking-wide mb-3">
              Recent
            </h3>
            {activities
              .slice(-10)
              .reverse()
              .map((a, i) => (
                <div
                  key={`${a.date}-${a.type}-${i}`}
                  className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-dark/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{
                        backgroundColor:
                          {
                            running: "#4fc3f7",
                            cycling: "#66bb6a",
                            strength_training: "#ff8a65",
                            walking: "#ffa726",
                            meditation: "#ab47bc",
                          }[a.type] || "#888",
                      }}
                    />
                    <span className="text-sm text-[#e0e0e0]">
                      {a.name || a.type.replace("_", " ")}
                    </span>
                  </div>
                  <div className="flex items-center gap-6 text-xs text-[#888]">
                    <span>{a.date}</span>
                    <span>{a.duration_min} min</span>
                    {a.distance_km && <span>{a.distance_km} km</span>}
                    {a.calories && <span>{a.calories} cal</span>}
                    {a.avg_hr && <span>{a.avg_hr} bpm</span>}
                  </div>
                </div>
              ))}
          </div>
        )}
      </motion.div>
    </div>
  );
}
