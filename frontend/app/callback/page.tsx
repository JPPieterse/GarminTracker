"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import LoadingSpinner from "@/components/shared/LoadingSpinner";

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const token = searchParams.get("token");

    if (token) {
      localStorage.setItem("token", token);
      // Small delay to ensure localStorage is written before redirect
      window.location.href = "/dashboard";
    } else {
      console.error("No token found in callback URL");
      router.replace("/");
    }
  }, [router, searchParams]);

  return null;
}

export default function CallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-dark flex flex-col items-center justify-center">
          <LoadingSpinner size={48} />
          <p className="mt-4 text-[#888]">Signing you in...</p>
        </div>
      }
    >
      <div className="min-h-screen bg-dark flex flex-col items-center justify-center">
        <LoadingSpinner size={48} />
        <p className="mt-4 text-[#888]">Signing you in...</p>
      </div>
      <CallbackHandler />
    </Suspense>
  );
}
