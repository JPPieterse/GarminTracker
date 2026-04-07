"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { SleepBreakdown } from "@/lib/types";

interface SleepChartProps {
  data: SleepBreakdown[];
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-lg p-3 text-sm">
      <p className="text-[#888] mb-2">{formatDate(label)}</p>
      {payload.map((entry: any) => (
        <p key={entry.name} style={{ color: entry.color }}>
          {entry.name}: {entry.value}h
        </p>
      ))}
      {payload[0]?.payload?.total && (
        <p className="text-[#e0e0e0] mt-1 pt-1 border-t border-border font-medium">
          Total: {payload[0].payload.total}h
        </p>
      )}
    </div>
  );
};

export default function SleepChart({ data }: SleepChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-[#888] text-sm">
        No sleep data yet
      </div>
    );
  }

  const chartData = data.map((d) => ({
    ...d,
    date: formatDate(d.date),
    rawDate: d.date,
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d37" />
        <XAxis
          dataKey="date"
          stroke="#888"
          fontSize={11}
          tickLine={false}
          interval={Math.max(0, Math.floor(data.length / 10))}
        />
        <YAxis
          stroke="#888"
          fontSize={12}
          tickLine={false}
          label={{ value: "Hours", angle: -90, position: "insideLeft", fill: "#888", fontSize: 12 }}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 12, color: "#888" }}
          iconType="square"
          iconSize={10}
        />
        <Bar dataKey="deep" name="Deep" stackId="sleep" fill="#7c4dff" radius={[0, 0, 0, 0]} />
        <Bar dataKey="light" name="Light" stackId="sleep" fill="#4fc3f7" radius={[0, 0, 0, 0]} />
        <Bar dataKey="rem" name="REM" stackId="sleep" fill="#ab47bc" radius={[0, 0, 0, 0]} />
        <Bar dataKey="awake" name="Awake" stackId="sleep" fill="#ff8a65" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
