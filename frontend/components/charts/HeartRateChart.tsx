"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { ChartDataPoint } from "@/lib/types";

interface HeartRateChartProps {
  resting: ChartDataPoint[];
  max: ChartDataPoint[];
  min: ChartDataPoint[];
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-lg p-3 text-sm">
      <p className="text-[#888] mb-2">{label}</p>
      {payload.map((entry: any) => (
        <p key={entry.name} style={{ color: entry.stroke || entry.color }}>
          {entry.name}: {entry.value} bpm
        </p>
      ))}
    </div>
  );
};

export default function HeartRateChart({ resting, max, min }: HeartRateChartProps) {
  if (resting.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-[#888] text-sm">
        No heart rate data yet
      </div>
    );
  }

  // Merge all three series by date
  const dateMap = new Map<string, { date: string; resting?: number; max?: number; min?: number }>();
  for (const d of resting) {
    const entry = dateMap.get(d.date) || { date: d.date };
    entry.resting = d.value;
    dateMap.set(d.date, entry);
  }
  for (const d of max) {
    const entry = dateMap.get(d.date) || { date: d.date };
    entry.max = d.value;
    dateMap.set(d.date, entry);
  }
  for (const d of min) {
    const entry = dateMap.get(d.date) || { date: d.date };
    entry.min = d.value;
    dateMap.set(d.date, entry);
  }

  const chartData = [...dateMap.values()]
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((d) => ({ ...d, displayDate: formatDate(d.date) }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d37" />
        <XAxis
          dataKey="displayDate"
          stroke="#888"
          fontSize={11}
          tickLine={false}
          interval={Math.max(0, Math.floor(chartData.length / 10))}
        />
        <YAxis
          stroke="#888"
          fontSize={12}
          tickLine={false}
          domain={["auto", "auto"]}
          label={{ value: "BPM", angle: -90, position: "insideLeft", fill: "#888", fontSize: 12 }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ fontSize: 12, color: "#888" }} iconType="line" />
        <Area
          type="monotone"
          dataKey="max"
          name="Max HR"
          stroke="#ef5350"
          fill="#ef5350"
          fillOpacity={0.08}
          strokeWidth={1.5}
          dot={false}
        />
        <Area
          type="monotone"
          dataKey="resting"
          name="Resting HR"
          stroke="#4fc3f7"
          fill="#4fc3f7"
          fillOpacity={0.15}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#4fc3f7" }}
        />
        <Area
          type="monotone"
          dataKey="min"
          name="Min HR"
          stroke="#66bb6a"
          fill="#66bb6a"
          fillOpacity={0.08}
          strokeWidth={1.5}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
