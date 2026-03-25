"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Users, Plus, Mail, Check } from "lucide-react";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import { getDoctorPatients, invitePatient } from "@/lib/api";
import type { PatientSummary } from "@/lib/types";

const PERMISSION_OPTIONS = [
  { key: "steps", label: "Steps" },
  { key: "heart_rate", label: "Heart Rate" },
  { key: "sleep", label: "Sleep" },
  { key: "stress", label: "Stress" },
  { key: "calories", label: "Calories" },
  { key: "activities", label: "Activities" },
];

export default function DoctorPage() {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Invite form
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [invitePermissions, setInvitePermissions] = useState<string[]>([]);
  const [inviting, setInviting] = useState(false);
  const [inviteMessage, setInviteMessage] = useState("");

  useEffect(() => {
    getDoctorPatients()
      .then(setPatients)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load patients")
      )
      .finally(() => setLoading(false));
  }, []);

  const togglePermission = (key: string) => {
    setInvitePermissions((prev) =>
      prev.includes(key) ? prev.filter((p) => p !== key) : [...prev, key]
    );
  };

  const handleInvite = async () => {
    if (!inviteEmail.trim() || invitePermissions.length === 0) return;
    setInviting(true);
    setInviteMessage("");
    try {
      await invitePatient(inviteEmail.trim(), invitePermissions);
      setInviteMessage("Invitation sent successfully");
      setInviteEmail("");
      setInvitePermissions([]);
      // Refresh list
      const updated = await getDoctorPatients();
      setPatients(updated);
    } catch (err) {
      setInviteMessage(
        err instanceof Error ? err.message : "Failed to send invite"
      );
    } finally {
      setInviting(false);
    }
  };

  if (loading) return <LoadingSpinner size={48} />;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users className="text-brand" size={24} />
          <h1 className="text-2xl font-bold text-[#e0e0e0]">Patients</h1>
        </div>
        <button
          onClick={() => setShowInvite(!showInvite)}
          className="flex items-center gap-2 px-4 py-2 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors text-sm"
        >
          <Plus size={16} />
          Invite Patient
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Invite Form */}
      {showInvite && (
        <div className="bg-card border border-border rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold text-[#e0e0e0]">
            Invite a Patient
          </h2>

          <div>
            <label className="block text-sm text-[#888] mb-1">
              Patient Email
            </label>
            <div className="flex items-center gap-2">
              <Mail size={16} className="text-[#888]" />
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="patient@example.com"
                className="flex-1 bg-dark border border-border rounded-lg px-3 py-2 text-[#e0e0e0] placeholder-[#888] focus:outline-none focus:border-brand text-sm"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm text-[#888] mb-2">
              Data Permissions
            </label>
            <div className="flex flex-wrap gap-2">
              {PERMISSION_OPTIONS.map((perm) => (
                <button
                  key={perm.key}
                  onClick={() => togglePermission(perm.key)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                    invitePermissions.includes(perm.key)
                      ? "bg-brand/10 border-brand/30 text-brand"
                      : "border-border text-[#888] hover:text-[#e0e0e0]"
                  }`}
                >
                  {invitePermissions.includes(perm.key) && (
                    <Check size={14} />
                  )}
                  {perm.label}
                </button>
              ))}
            </div>
          </div>

          {inviteMessage && (
            <p className="text-sm text-brand">{inviteMessage}</p>
          )}

          <button
            onClick={handleInvite}
            disabled={
              inviting ||
              !inviteEmail.trim() ||
              invitePermissions.length === 0
            }
            className="px-4 py-2 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors disabled:opacity-50 text-sm"
          >
            {inviting ? "Sending..." : "Send Invitation"}
          </button>
        </div>
      )}

      {/* Patient List */}
      {patients.length === 0 ? (
        <div className="text-center py-16">
          <Users className="text-[#888] mx-auto mb-3" size={40} />
          <p className="text-[#888]">No patients yet</p>
          <p className="text-sm text-[#888] mt-1">
            Invite patients to start monitoring their health data.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {patients.map((patient) => (
            <Link
              key={patient.id}
              href={`/doctor/${patient.id}`}
              className="block bg-card border border-border rounded-lg p-4 hover:border-brand/30 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[#e0e0e0] font-medium">
                    {patient.name}
                  </p>
                  <p className="text-sm text-[#888]">{patient.email}</p>
                </div>
                <div className="text-right">
                  <div className="flex gap-1 flex-wrap justify-end">
                    {patient.permissions.map((p) => (
                      <span
                        key={p}
                        className="px-2 py-0.5 bg-brand/10 text-brand rounded text-xs"
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                  {patient.last_sync && (
                    <p className="text-xs text-[#888] mt-1">
                      Last sync: {patient.last_sync}
                    </p>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
