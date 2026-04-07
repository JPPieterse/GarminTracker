"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  Brain,
  Shield,
  BarChart3,
  Mic,
  Share2,
} from "lucide-react";

const features = [
  {
    icon: Activity,
    title: "Wearable Sync",
    desc: "Automatically sync steps, heart rate, sleep, stress, and more from your device.",
  },
  {
    icon: Brain,
    title: "AI Health Insights",
    desc: "Ask questions about your health data and get intelligent answers.",
  },
  {
    icon: Mic,
    title: "Voice Interaction",
    desc: "Speak your questions and listen to answers hands-free.",
  },
  {
    icon: BarChart3,
    title: "Trend Charts",
    desc: "Visualize your health metrics over time with interactive charts.",
  },
  {
    icon: Share2,
    title: "Doctor Sharing",
    desc: "Securely share your health data with healthcare providers.",
  },
  {
    icon: Shield,
    title: "Privacy First",
    desc: "Your data is encrypted and you control who sees it.",
  },
];

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.5, ease: "easeOut" },
  }),
};

export default function LandingPage() {
  const { user, login, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) {
      router.replace("/dashboard");
    }
  }, [user, loading, router]);

  return (
    <div className="min-h-screen bg-dark flex flex-col gradient-bg">
      {/* Header */}
      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative z-10 flex items-center justify-between px-8 py-6 border-b border-border/50 backdrop-blur-sm"
      >
        <h1 className="text-2xl font-heading font-bold text-brand">
          ZEV
        </h1>
        <button
          onClick={login}
          className="px-6 py-2 bg-brand/10 text-brand font-semibold rounded-lg border border-brand/30 hover:bg-brand hover:text-dark transition-all duration-300"
        >
          Log in
        </button>
      </motion.header>

      {/* Hero */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-8 py-16">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          className="text-center max-w-2xl mb-16"
        >
          <p className="text-brand/80 font-medium text-sm tracking-widest uppercase mb-4">
            Zone Enhanced Vitals
          </p>
          <h2 className="text-5xl md:text-6xl font-heading font-bold text-[#e0e0e0] mb-6 leading-tight">
            Your Health,{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand to-[#ab47bc]">
              Understood
            </span>
          </h2>
          <p className="text-lg text-[#888] leading-relaxed max-w-xl mx-auto">
            Connect your fitness wearable, sync your data, and unlock AI-powered
            insights about your health and fitness journey.
          </p>
          <motion.button
            onClick={login}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.98 }}
            className="mt-8 px-8 py-3 bg-brand text-dark font-semibold rounded-lg text-lg hover:shadow-[0_0_30px_rgba(79,195,247,0.3)] transition-all duration-300"
          >
            Get Started
          </motion.button>
        </motion.div>

        {/* Feature cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl w-full">
          {features.map((f, i) => {
            const Icon = f.icon;
            return (
              <motion.div
                key={f.title}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true, margin: "-50px" }}
                variants={fadeUp}
                whileHover={{ y: -4, transition: { duration: 0.2 } }}
                className="bg-card/80 backdrop-blur-sm border border-border rounded-xl p-6 hover:border-brand/30 transition-colors duration-300 group"
              >
                <div className="w-10 h-10 rounded-lg bg-brand/10 flex items-center justify-center mb-4 group-hover:bg-brand/20 transition-colors duration-300">
                  <Icon className="text-brand" size={20} />
                </div>
                <h3 className="text-[#e0e0e0] font-heading font-semibold mb-2">
                  {f.title}
                </h3>
                <p className="text-sm text-[#888] leading-relaxed">
                  {f.desc}
                </p>
              </motion.div>
            );
          })}
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 text-center text-[#666] text-sm py-6 border-t border-border/50">
        ZEV &mdash; Zone Enhanced Vitals
      </footer>
    </div>
  );
}
