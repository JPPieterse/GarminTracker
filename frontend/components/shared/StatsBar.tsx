"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";

interface StatCard {
  label: string;
  value: string | number;
  icon: ReactNode;
}

export default function StatsBar({ stats }: { stats: StatCard[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {stats.map((stat, i) => (
        <motion.div
          key={stat.label}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.08, duration: 0.4, ease: "easeOut" }}
          whileHover={{ y: -2, transition: { duration: 0.2 } }}
          className="bg-card border border-border rounded-xl p-4 flex items-center gap-3 hover:border-brand/20 transition-colors duration-300"
        >
          <div className="w-9 h-9 rounded-lg bg-brand/10 flex items-center justify-center text-brand">
            {stat.icon}
          </div>
          <div>
            <p className="text-xs text-[#888] uppercase tracking-wide">
              {stat.label}
            </p>
            <p className="text-lg font-heading font-semibold text-[#e0e0e0]">
              {stat.value}
            </p>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
