"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
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

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2d37" />
        <XAxis
          dataKey="date"
          stroke="#888"
          fontSize={12}
          tickLine={false}
        />
        <YAxis stroke="#888" fontSize={12} tickLine={false} />
        <Tooltip
          contentStyle={{
            backgroundColor: "#1a1d27",
            border: "1px solid #2a2d37",
            borderRadius: 8,
            color: "#e0e0e0",
          }}
          labelStyle={{ color: "#888" }}
        />
        <Line
          type="monotone"
          dataKey="value"
          name={label}
          stroke={color}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: color }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
