"use client";

import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { ActivitySummary } from "@/lib/types";

interface ActivityChartProps {
  data: ActivitySummary[];
}

const ACTIVITY_COLORS: Record<string, string> = {
  running: "#4fc3f7",
  cycling: "#66bb6a",
  strength_training: "#ff8a65",
  walking: "#ffa726",
  swimming: "#42a5f5",
  hiking: "#8d6e63",
  meditation: "#ab47bc",
  other: "#888",
};

function getColor(type: string) {
  return ACTIVITY_COLORS[type] || ACTIVITY_COLORS.other;
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-card border border-border rounded-lg p-3 text-sm min-w-[180px]">
      <p className="text-[#e0e0e0] font-medium mb-1">{d.name || d.type}</p>
      <p className="text-[#888]">{d.date}</p>
      <div className="mt-2 space-y-1">
        <p className="text-[#e0e0e0]">Duration: {d.duration_min} min</p>
        {d.distance_km && <p className="text-[#e0e0e0]">Distance: {d.distance_km} km</p>}
        {d.calories && <p className="text-[#e0e0e0]">Calories: {d.calories}</p>}
        {d.avg_hr && <p className="text-[#e0e0e0]">Avg HR: {d.avg_hr} bpm</p>}
      </div>
    </div>
  );
};

export default function ActivityChart({ data }: ActivityChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-[#888] text-sm">
        No activities yet
      </div>
    );
  }

  // Group by activity type
  const types = Array.from(new Set(data.map((d) => d.type)));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <ScatterChart margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d37" />
        <XAxis
          dataKey="duration_min"
          name="Duration"
          unit=" min"
          stroke="#888"
          fontSize={12}
          tickLine={false}
          label={{ value: "Duration (min)", position: "insideBottom", offset: -5, fill: "#888", fontSize: 12 }}
        />
        <YAxis
          dataKey="calories"
          name="Calories"
          stroke="#888"
          fontSize={12}
          tickLine={false}
          label={{ value: "Calories", angle: -90, position: "insideLeft", fill: "#888", fontSize: 12 }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ fontSize: 12, color: "#888" }} iconType="circle" iconSize={8} />
        {types.map((type) => (
          <Scatter
            key={type}
            name={type.replace("_", " ")}
            data={data.filter((d) => d.type === type)}
            fill={getColor(type)}
            opacity={0.8}
          />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
