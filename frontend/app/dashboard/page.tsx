"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Calendar,
  Activity,
  CalendarRange,
  Brain,
  RefreshCw,
} from "lucide-react";
import StatsBar from "@/components/shared/StatsBar";
import TrendChart from "@/components/charts/TrendChart";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import { getStats, getChart, syncData } from "@/lib/api";
import type { StatsResponse, ChartDataPoint } from "@/lib/types";

const METRICS = [
  { key: "steps", label: "Steps", color: "#4fc3f7" },
  { key: "calories", label: "Calories", color: "#ff8a65" },
  { key: "heart_rate", label: "Heart Rate", color: "#ef5350" },
  { key: "sleep", label: "Sleep", color: "#ab47bc" },
  { key: "stress", label: "Stress", color: "#ffa726" },
];

export default function DashboardPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
  const [activeMetric, setActiveMetric] = useState(METRICS[0]);
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState("");
  const [error, setError] = useState("");

  const loadStats = useCallback(async () => {
    try {
      const data = await getStats();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load stats");
    }
  }, []);

  const loadChart = useCallback(async (metric: string) => {
    setChartLoading(true);
    try {
      const data = await getChart(metric, 30);
      setChartData(data);
    } catch {
      setChartData([]);
    } finally {
      setChartLoading(false);
    }
  }, []);

  useEffect(() => {
    Promise.all([loadStats(), loadChart(activeMetric.key)]).finally(() =>
      setLoading(false)
    );
  }, [loadStats, loadChart, activeMetric.key]);

  const handleSync = async () => {
    setSyncing(true);
    setSyncMessage("");
    try {
      const result = await syncData();
      setSyncMessage(
        result.message || `Synced ${result.records_synced} records`
      );
      await loadStats();
      await loadChart(activeMetric.key);
    } catch (err) {
      setSyncMessage(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const handleMetricChange = (metric: (typeof METRICS)[number]) => {
    setActiveMetric(metric);
    loadChart(metric.key);
  };

  if (loading) return <LoadingSpinner size={48} />;

  if (error) {
    return (
      <div className="text-center py-16">
        <p className="text-red-400 mb-2">Error</p>
        <p className="text-[#888] text-sm">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-[#e0e0e0]">Dashboard</h1>
      </div>

      {stats && (
        <StatsBar
          stats={[
            {
              label: "Days Tracked",
              value: stats.total_days,
              icon: <Calendar size={20} />,
            },
            {
              label: "Activities",
              value: stats.total_activities,
              icon: <Activity size={20} />,
            },
            {
              label: "Date Range",
              value: stats.date_range
                ? `${stats.date_range.start} - ${stats.date_range.end}`
                : "N/A",
              icon: <CalendarRange size={20} />,
            },
            {
              label: "AI Queries",
              value: stats.ai_queries,
              icon: <Brain size={20} />,
            },
          ]}
        />
      )}

      {/* Trend Charts */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-[#e0e0e0]">
            Health Trends
          </h2>
        </div>

        {/* Metric Tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto">
          {METRICS.map((m) => (
            <button
              key={m.key}
              onClick={() => handleMetricChange(m)}
              className={`px-4 py-2 rounded-lg text-sm whitespace-nowrap transition-colors ${
                activeMetric.key === m.key
                  ? "bg-brand/10 text-brand border border-brand/30"
                  : "text-[#888] hover:text-[#e0e0e0] border border-transparent hover:border-border"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {chartLoading ? (
          <LoadingSpinner />
        ) : (
          <TrendChart
            data={chartData}
            label={activeMetric.label}
            color={activeMetric.color}
          />
        )}
      </div>

      {/* Sync Section */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-[#e0e0e0]">
              Sync Data
            </h2>
            <p className="text-sm text-[#888] mt-1">
              Pull the latest data from your Garmin device
            </p>
          </div>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="flex items-center gap-2 px-4 py-2 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={16} className={syncing ? "animate-spin" : ""} />
            {syncing ? "Syncing..." : "Sync Now"}
          </button>
        </div>
        {syncMessage && (
          <p className="mt-3 text-sm text-[#888]">{syncMessage}</p>
        )}
      </div>
    </div>
  );
}
