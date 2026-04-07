"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import type { ChartDataPoint } from "@/lib/types";

interface TrendChartProps {
  data: ChartDataPoint[];
  label?: string;
  color?: string;
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card border border-border rounded-lg p-3 text-sm">
      <p className="text-[#888] mb-1">{label}</p>
      <p style={{ color: payload[0].color }} className="font-medium">
        {payload[0].name}: {payload[0].value?.toLocaleString()}
      </p>
    </div>
  );
};

export default function TrendChart({
  data,
  label = "Value",
  color = "#4fc3f7",
}: TrendChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-[#888] text-sm">
        No data yet
      </div>
    );
  }

  const chartData = data.map((d) => ({
    ...d,
    displayDate: formatDate(d.date),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart
        data={chartData}
        margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
      >
        <defs>
          <linearGradient id={`grad-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.2} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d37" />
        <XAxis
          dataKey="displayDate"
          stroke="#888"
          fontSize={11}
          tickLine={false}
          interval={Math.max(0, Math.floor(data.length / 10))}
        />
        <YAxis
          stroke="#888"
          fontSize={12}
          tickLine={false}
          domain={["auto", "auto"]}
        />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="value"
          name={label}
          stroke={color}
          strokeWidth={2}
          fill={`url(#grad-${color})`}
          dot={false}
          activeDot={{ r: 4, fill: color }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
