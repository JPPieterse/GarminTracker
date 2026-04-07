"use client";

import { useState, useEffect } from "react";
import {
  Watch,
  CreditCard,
  Download,
  Trash2,
  Link as LinkIcon,
  ExternalLink,
  AlertTriangle,
  Brain,
} from "lucide-react";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import { useAuth } from "@/lib/auth";
import {
  connectGarmin,
  disconnectGarmin,
  getSubscription,
  createCheckout,
  cancelSubscription,
  exportData,
  getSharingLinks,
  revokeLink,
  deleteAccount,
  getProfile,
  updateProfile,
} from "@/lib/api";
import type { SubscriptionInfo, SharingLink } from "@/lib/types";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(
    null
  );
  const [sharingLinks, setSharingLinks] = useState<SharingLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [garminLoading, setGarminLoading] = useState(false);
  const [garminEmail, setGarminEmail] = useState("");
  const [garminPassword, setGarminPassword] = useState("");
  const [showGarminForm, setShowGarminForm] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [message, setMessage] = useState("");
  const [profileContext, setProfileContext] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);

  useEffect(() => {
    Promise.all([
      getSubscription().catch(() => null),
      getSharingLinks().catch(() => []),
      getProfile().catch(() => ({ context: "" })),
    ])
      .then(([sub, links, profile]) => {
        setSubscription(sub);
        setSharingLinks(links);
        setProfileContext(profile?.context || "");
      })
      .finally(() => setLoading(false));
  }, []);

  const handleConnectGarmin = async () => {
    if (!garminEmail || !garminPassword) {
      setMessage("Please enter your Garmin email and password.");
      return;
    }
    setGarminLoading(true);
    try {
      await connectGarmin(garminEmail, garminPassword);
      setMessage("Garmin connected successfully!");
      setShowGarminForm(false);
      setGarminEmail("");
      setGarminPassword("");
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Failed to connect Garmin"
      );
    } finally {
      setGarminLoading(false);
    }
  };

  const handleSaveProfile = async () => {
    setProfileSaving(true);
    setProfileSaved(false);
    try {
      await updateProfile(profileContext);
      setProfileSaved(true);
      setTimeout(() => setProfileSaved(false), 3000);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setProfileSaving(false);
    }
  };

  const handleDisconnectGarmin = async () => {
    setGarminLoading(true);
    try {
      await disconnectGarmin();
      setMessage("Garmin disconnected successfully");
      window.location.reload();
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Failed to disconnect Garmin"
      );
    } finally {
      setGarminLoading(false);
    }
  };

  const handleUpgrade = async (tier: string) => {
    try {
      const result = await createCheckout(tier);
      window.location.href = result.checkout_url;
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to upgrade");
    }
  };

  const handleCancelSubscription = async () => {
    try {
      await cancelSubscription();
      setMessage("Subscription cancelled");
      const sub = await getSubscription().catch(() => null);
      setSubscription(sub);
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Failed to cancel subscription"
      );
    }
  };

  const handleExport = async (format: string) => {
    setExportLoading(true);
    try {
      const blob = await exportData(format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `garmin-data.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExportLoading(false);
    }
  };

  const handleRevokeLink = async (linkId: string) => {
    try {
      await revokeLink(linkId);
      setSharingLinks((prev) => prev.filter((l) => l.id !== linkId));
      setMessage("Sharing link revoked");
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Failed to revoke link"
      );
    }
  };

  const handleDeleteAccount = async () => {
    try {
      await deleteAccount();
      logout();
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Failed to delete account"
      );
    }
  };

  if (loading) return <LoadingSpinner size={48} />;

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-[#e0e0e0]">Settings</h1>

      {message && (
        <div className="bg-brand/10 border border-brand/30 rounded-lg p-3 text-brand text-sm">
          {message}
        </div>
      )}

      {/* Garmin Connection */}
      <section className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <Watch className="text-brand" size={22} />
          <h2 className="text-lg font-semibold text-[#e0e0e0]">
            Garmin Connection
          </h2>
        </div>
        <p className="text-sm text-[#888] mb-4">
          {user?.garmin_connected
            ? "Your Garmin account is connected."
            : "Connect your Garmin account to sync health data."}
        </p>
        {user?.garmin_connected ? (
          <button
            onClick={handleDisconnectGarmin}
            disabled={garminLoading}
            className="px-4 py-2 border border-red-500/30 text-red-400 rounded-lg hover:bg-red-500/10 transition-colors disabled:opacity-50 text-sm"
          >
            {garminLoading ? "Disconnecting..." : "Disconnect Garmin"}
          </button>
        ) : showGarminForm ? (
          <div className="space-y-3">
            <input
              type="email"
              placeholder="Garmin email"
              value={garminEmail}
              onChange={(e) => setGarminEmail(e.target.value)}
              className="w-full px-3 py-2 bg-dark border border-border rounded-lg text-[#e0e0e0] text-sm placeholder-[#666] focus:border-brand/50 focus:outline-none transition-colors"
            />
            <input
              type="password"
              placeholder="Garmin password"
              value={garminPassword}
              onChange={(e) => setGarminPassword(e.target.value)}
              className="w-full px-3 py-2 bg-dark border border-border rounded-lg text-[#e0e0e0] text-sm placeholder-[#666] focus:border-brand/50 focus:outline-none transition-colors"
            />
            <div className="flex gap-2">
              <button
                onClick={handleConnectGarmin}
                disabled={garminLoading}
                className="px-4 py-2 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors disabled:opacity-50 text-sm"
              >
                {garminLoading ? "Connecting..." : "Connect"}
              </button>
              <button
                onClick={() => setShowGarminForm(false)}
                className="px-4 py-2 border border-border text-[#888] rounded-lg hover:text-[#e0e0e0] transition-colors text-sm"
              >
                Cancel
              </button>
            </div>
            <p className="text-xs text-[#666]">
              Your credentials are encrypted and stored securely.
            </p>
          </div>
        ) : (
          <button
            onClick={() => setShowGarminForm(true)}
            className="px-4 py-2 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors text-sm"
          >
            Connect Garmin
          </button>
        )}
      </section>

      {/* Health Profile — AI Context */}
      <section className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center gap-3 mb-2">
          <Brain className="text-brand" size={22} />
          <h2 className="text-lg font-semibold text-[#e0e0e0]">
            Your Health Profile
          </h2>
        </div>
        <p className="text-sm text-[#888] mb-4">
          Tell the AI about yourself in your own words. This context is included
          in every AI conversation so it always knows who you are, what you're
          working towards, and how to help you. Write as much or as little as
          you want.
        </p>
        <textarea
          value={profileContext}
          onChange={(e) => setProfileContext(e.target.value)}
          placeholder={`Write anything you want the AI to always know about you. For example:

• I'm 32, male, 82kg. I run 3-4x per week and do strength training 2x.
• My goal is to run a sub-50 min 10K by December.
• I have a recurring left knee issue from an old rugby injury.
• I usually sleep around 11pm, wake at 6am. I track with a Garmin Venu 3.
• I follow a high-protein diet, trying to stay around 2200 cal/day.
• I'm training for the Comrades Marathon in 2027.
• My resting heart rate has been trending up — I want to understand why.

The more context you give, the more personalized and useful the AI becomes.`}
          rows={12}
          className="w-full px-4 py-3 bg-dark border border-border rounded-lg text-[#e0e0e0] text-sm placeholder-[#555] focus:border-brand/50 focus:outline-none transition-colors resize-y leading-relaxed"
        />
        <div className="flex items-center gap-3 mt-3">
          <button
            onClick={handleSaveProfile}
            disabled={profileSaving}
            className="px-5 py-2 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors disabled:opacity-50 text-sm"
          >
            {profileSaving ? "Saving..." : "Save Profile"}
          </button>
          {profileSaved && (
            <span className="text-sm text-green-400">Saved! The AI will use this context in all future conversations.</span>
          )}
        </div>
      </section>

      {/* Subscription */}
      <section className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <CreditCard className="text-brand" size={22} />
          <h2 className="text-lg font-semibold text-[#e0e0e0]">
            Subscription
          </h2>
        </div>
        {subscription ? (
          <>
            <div className="flex items-center gap-3 mb-4">
              <span className="px-3 py-1 bg-brand/10 text-brand rounded-full text-sm font-medium capitalize">
                {subscription.tier}
              </span>
              <span className="text-sm text-[#888]">
                {subscription.status}
              </span>
            </div>
            {subscription.features.length > 0 && (
              <ul className="text-sm text-[#888] space-y-1 mb-4">
                {subscription.features.map((f) => (
                  <li key={f}>- {f}</li>
                ))}
              </ul>
            )}
            <div className="flex gap-2">
              {subscription.tier !== "premium" && (
                <button
                  onClick={() =>
                    handleUpgrade(
                      subscription.tier === "free" ? "pro" : "premium"
                    )
                  }
                  className="flex items-center gap-2 px-4 py-2 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors text-sm"
                >
                  <ExternalLink size={14} />
                  Upgrade to{" "}
                  {subscription.tier === "free" ? "Pro" : "Premium"}
                </button>
              )}
              {subscription.tier !== "free" && (
                <button
                  onClick={handleCancelSubscription}
                  className="px-4 py-2 border border-border text-[#888] rounded-lg hover:text-[#e0e0e0] transition-colors text-sm"
                >
                  Cancel Subscription
                </button>
              )}
            </div>
          </>
        ) : (
          <p className="text-sm text-[#888]">
            No subscription information available.
          </p>
        )}
      </section>

      {/* Data Export */}
      <section className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <Download className="text-brand" size={22} />
          <h2 className="text-lg font-semibold text-[#e0e0e0]">
            Export Data
          </h2>
        </div>
        <p className="text-sm text-[#888] mb-4">
          Download your health data in your preferred format.
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => handleExport("json")}
            disabled={exportLoading}
            className="px-4 py-2 border border-border text-[#e0e0e0] rounded-lg hover:border-brand/30 transition-colors disabled:opacity-50 text-sm"
          >
            Export JSON
          </button>
          <button
            onClick={() => handleExport("csv")}
            disabled={exportLoading}
            className="px-4 py-2 border border-border text-[#e0e0e0] rounded-lg hover:border-brand/30 transition-colors disabled:opacity-50 text-sm"
          >
            Export CSV
          </button>
        </div>
      </section>

      {/* Doctor Sharing Links */}
      <section className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <LinkIcon className="text-brand" size={22} />
          <h2 className="text-lg font-semibold text-[#e0e0e0]">
            Doctor Sharing
          </h2>
        </div>
        {sharingLinks.length === 0 ? (
          <p className="text-sm text-[#888]">
            No active sharing links. Doctors can invite you to share data.
          </p>
        ) : (
          <div className="space-y-3">
            {sharingLinks.map((link) => (
              <div
                key={link.id}
                className="flex items-center justify-between p-3 bg-dark rounded-lg"
              >
                <div>
                  <p className="text-sm text-[#e0e0e0]">
                    {link.doctor_email}
                  </p>
                  <p className="text-xs text-[#888]">
                    {link.permissions.join(", ")} &middot;{" "}
                    <span className="capitalize">{link.status}</span>
                  </p>
                </div>
                <button
                  onClick={() => handleRevokeLink(link.id)}
                  className="text-xs text-red-400 hover:text-red-300 transition-colors"
                >
                  Revoke
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Delete Account */}
      <section className="bg-card border border-red-500/20 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <Trash2 className="text-red-400" size={22} />
          <h2 className="text-lg font-semibold text-red-400">
            Delete Account
          </h2>
        </div>
        <p className="text-sm text-[#888] mb-4">
          Permanently delete your account and all associated data. This action
          cannot be undone.
        </p>
        {deleteConfirm ? (
          <div className="flex items-center gap-3">
            <AlertTriangle className="text-red-400" size={18} />
            <span className="text-sm text-red-400">Are you sure?</span>
            <button
              onClick={handleDeleteAccount}
              className="px-4 py-2 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600 transition-colors"
            >
              Yes, delete my account
            </button>
            <button
              onClick={() => setDeleteConfirm(false)}
              className="px-4 py-2 border border-border text-[#888] rounded-lg text-sm hover:text-[#e0e0e0] transition-colors"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setDeleteConfirm(true)}
            className="px-4 py-2 border border-red-500/30 text-red-400 rounded-lg hover:bg-red-500/10 transition-colors text-sm"
          >
            Delete Account
          </button>
        )}
      </section>
    </div>
  );
}
