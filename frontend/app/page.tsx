"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
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
    title: "Garmin Sync",
    desc: "Automatically sync steps, heart rate, sleep, stress, and more.",
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

export default function LandingPage() {
  const { user, login, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) {
      router.replace("/dashboard");
    }
  }, [user, loading, router]);

  return (
    <div className="min-h-screen bg-dark flex flex-col">
      <header className="flex items-center justify-between px-8 py-6 border-b border-border">
        <h1 className="text-2xl font-bold text-brand">GarminTracker</h1>
        <button
          onClick={login}
          className="px-6 py-2 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors"
        >
          Log in
        </button>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-8 py-16">
        <div className="text-center max-w-2xl mb-16">
          <h2 className="text-5xl font-bold text-[#e0e0e0] mb-4">
            Your Health, <span className="text-brand">Understood</span>
          </h2>
          <p className="text-lg text-[#888]">
            Connect your Garmin device, sync your data, and unlock AI-powered
            insights about your health and fitness journey.
          </p>
          <button
            onClick={login}
            className="mt-8 px-8 py-3 bg-brand text-dark font-semibold rounded-lg text-lg hover:bg-brand/90 transition-colors"
          >
            Get Started
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl w-full">
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className="bg-card border border-border rounded-lg p-6 hover:border-brand/30 transition-colors"
              >
                <Icon className="text-brand mb-3" size={28} />
                <h3 className="text-[#e0e0e0] font-semibold mb-1">
                  {f.title}
                </h3>
                <p className="text-sm text-[#888]">{f.desc}</p>
              </div>
            );
          })}
        </div>
      </main>

      <footer className="text-center text-[#888] text-sm py-6 border-t border-border">
        GarminTracker &mdash; AI-powered health insights
      </footer>
    </div>
  );
}
