"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import LoadingSpinner from "@/components/shared/LoadingSpinner";

export default function DoctorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) {
      if (!user) {
        router.replace("/");
      } else if (user.role !== "doctor") {
        router.replace("/dashboard");
      }
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-dark flex items-center justify-center">
        <LoadingSpinner size={48} />
      </div>
    );
  }

  if (!user || user.role !== "doctor") return null;

  return (
    <div className="min-h-screen bg-dark">
      <header className="flex items-center justify-between px-8 py-4 border-b border-border">
        <h1 className="text-xl font-bold text-brand">
          GarminTracker — Doctor Portal
        </h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-[#888]">{user.name}</span>
          <a
            href="/dashboard"
            className="text-sm text-brand hover:underline"
          >
            My Dashboard
          </a>
        </div>
      </header>
      <main className="p-8">{children}</main>
    </div>
  );
}
