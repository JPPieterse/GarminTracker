"use client";

import Sidebar from "@/components/shared/Sidebar";
import ProtectedRoute from "@/components/auth/ProtectedRoute";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute>
      <div className="flex min-h-screen bg-dark">
        <Sidebar />
        <main className="flex-1 p-8 overflow-y-auto">{children}</main>
      </div>
    </ProtectedRoute>
  );
}
