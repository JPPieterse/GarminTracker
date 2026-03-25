"use client";

import type { ReactNode } from "react";

interface StatCard {
  label: string;
  value: string | number;
  icon: ReactNode;
}

export default function StatsBar({ stats }: { stats: StatCard[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="bg-card border border-border rounded-lg p-4 flex items-center gap-3"
        >
          <div className="text-brand">{stat.icon}</div>
          <div>
            <p className="text-sm text-[#888]">{stat.label}</p>
            <p className="text-lg font-semibold text-[#e0e0e0]">
              {stat.value}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
