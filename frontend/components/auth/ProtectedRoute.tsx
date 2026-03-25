"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import LoadingSpinner from "@/components/shared/LoadingSpinner";

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/");
    }
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-dark flex items-center justify-center">
        <LoadingSpinner size={48} />
      </div>
    );
  }

  if (!user) return null;

  return <>{children}</>;
}
