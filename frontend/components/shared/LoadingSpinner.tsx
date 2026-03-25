"use client";

export default function LoadingSpinner({ size = 40 }: { size?: number }) {
  return (
    <div className="flex items-center justify-center p-8">
      <div
        className="animate-spin rounded-full border-2 border-brand border-t-transparent"
        style={{ width: size, height: size }}
      />
    </div>
  );
}
