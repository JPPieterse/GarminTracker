"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import LoadingSpinner from "@/components/shared/LoadingSpinner";

export default function CallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const hash = window.location.hash.substring(1);
    const params = new URLSearchParams(hash);
    const accessToken = params.get("access_token");

    if (accessToken) {
      localStorage.setItem("token", accessToken);
      router.replace("/dashboard");
    } else {
      console.error("No access_token found in URL hash");
      router.replace("/");
    }
  }, [router]);

  return (
    <div className="min-h-screen bg-dark flex flex-col items-center justify-center">
      <LoadingSpinner size={48} />
      <p className="mt-4 text-[#888]">Signing you in...</p>
    </div>
  );
}
