"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, FileText, Plus } from "lucide-react";
import Link from "next/link";
import TrendChart from "@/components/charts/TrendChart";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import { getPatientData } from "@/lib/api";
import type { PatientDetail } from "@/lib/types";

const METRIC_LABELS: Record<string, { label: string; color: string }> = {
  steps: { label: "Steps", color: "#4fc3f7" },
  heart_rate: { label: "Heart Rate", color: "#ef5350" },
  sleep: { label: "Sleep", color: "#ab47bc" },
  stress: { label: "Stress", color: "#ffa726" },
  calories: { label: "Calories", color: "#ff8a65" },
  activities: { label: "Activities", color: "#66bb6a" },
};

export default function PatientDetailPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [annotationText, setAnnotationText] = useState("");
  const [annotationMetric, setAnnotationMetric] = useState("");
  const [showAnnotationForm, setShowAnnotationForm] = useState(false);

  useEffect(() => {
    if (!patientId) return;
    getPatientData(patientId)
      .then(setPatient)
      .catch((err) =>
        setError(
          err instanceof Error ? err.message : "Failed to load patient data"
        )
      )
      .finally(() => setLoading(false));
  }, [patientId]);

  const handleAddAnnotation = () => {
    if (!annotationText.trim()) return;
    // In a real app, this would call an API endpoint
    if (patient) {
      setPatient({
        ...patient,
        annotations: [
          ...patient.annotations,
          {
            id: Date.now().toString(),
            text: annotationText,
            created_at: new Date().toISOString(),
            metric: annotationMetric || undefined,
          },
        ],
      });
    }
    setAnnotationText("");
    setAnnotationMetric("");
    setShowAnnotationForm(false);
  };

  if (loading) return <LoadingSpinner size={48} />;

  if (error) {
    return (
      <div className="max-w-4xl mx-auto">
        <Link
          href="/doctor"
          className="flex items-center gap-2 text-brand hover:underline mb-6"
        >
          <ArrowLeft size={16} /> Back to Patients
        </Link>
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">
          {error}
        </div>
      </div>
    );
  }

  if (!patient) return null;

  const availableMetrics = Object.keys(patient.chart_data);

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <Link
          href="/doctor"
          className="flex items-center gap-2 text-brand hover:underline mb-4 text-sm"
        >
          <ArrowLeft size={16} /> Back to Patients
        </Link>
        <h1 className="text-2xl font-bold text-[#e0e0e0]">{patient.name}</h1>
        <p className="text-[#888]">{patient.email}</p>
        <div className="flex gap-1 mt-2">
          {patient.permissions.map((p) => (
            <span
              key={p}
              className="px-2 py-0.5 bg-brand/10 text-brand rounded text-xs"
            >
              {p}
            </span>
          ))}
        </div>
      </div>

      {/* Health Charts by Permission */}
      {availableMetrics.length === 0 ? (
        <div className="text-center py-16 text-[#888]">
          No data available for this patient.
        </div>
      ) : (
        availableMetrics.map((metric) => {
          const info = METRIC_LABELS[metric] || {
            label: metric,
            color: "#4fc3f7",
          };
          return (
            <div
              key={metric}
              className="bg-card border border-border rounded-lg p-6"
            >
              <h2 className="text-lg font-semibold text-[#e0e0e0] mb-4">
                {info.label}
              </h2>
              <TrendChart
                data={patient.chart_data[metric]}
                label={info.label}
                color={info.color}
              />
            </div>
          );
        })
      )}

      {/* Annotations */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileText className="text-brand" size={20} />
            <h2 className="text-lg font-semibold text-[#e0e0e0]">
              Clinical Notes
            </h2>
          </div>
          <button
            onClick={() => setShowAnnotationForm(!showAnnotationForm)}
            className="flex items-center gap-1 px-3 py-1.5 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors text-sm"
          >
            <Plus size={14} />
            Add Note
          </button>
        </div>

        {showAnnotationForm && (
          <div className="mb-4 p-4 bg-dark rounded-lg space-y-3">
            <div>
              <label className="block text-sm text-[#888] mb-1">
                Related Metric (optional)
              </label>
              <select
                value={annotationMetric}
                onChange={(e) => setAnnotationMetric(e.target.value)}
                className="bg-card border border-border rounded-lg px-3 py-2 text-[#e0e0e0] text-sm focus:outline-none focus:border-brand"
              >
                <option value="">General</option>
                {availableMetrics.map((m) => (
                  <option key={m} value={m}>
                    {METRIC_LABELS[m]?.label || m}
                  </option>
                ))}
              </select>
            </div>
            <textarea
              value={annotationText}
              onChange={(e) => setAnnotationText(e.target.value)}
              placeholder="Add a clinical note..."
              rows={3}
              className="w-full bg-card border border-border rounded-lg px-3 py-2 text-[#e0e0e0] placeholder-[#888] focus:outline-none focus:border-brand text-sm resize-none"
            />
            <button
              onClick={handleAddAnnotation}
              disabled={!annotationText.trim()}
              className="px-4 py-2 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors disabled:opacity-50 text-sm"
            >
              Save Note
            </button>
          </div>
        )}

        {patient.annotations.length === 0 ? (
          <p className="text-sm text-[#888]">No notes yet.</p>
        ) : (
          <div className="space-y-3">
            {patient.annotations.map((ann) => (
              <div key={ann.id} className="p-3 bg-dark rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  {ann.metric && (
                    <span className="px-2 py-0.5 bg-brand/10 text-brand rounded text-xs">
                      {METRIC_LABELS[ann.metric]?.label || ann.metric}
                    </span>
                  )}
                  <span className="text-xs text-[#888]">
                    {new Date(ann.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="text-sm text-[#e0e0e0]">{ann.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
