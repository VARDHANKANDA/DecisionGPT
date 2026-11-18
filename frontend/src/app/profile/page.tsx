"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useBusiness } from "@/lib/business-context";
import { isDemoBusiness } from "@/lib/demo";
import { api } from "@/lib/api";
import { Page, Notice, btnPrimary, btnSecondary } from "@/components/simple";

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const { business } = useBusiness();
  const demo = isDemoBusiness(business);

  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);

  const initials = (user?.full_name || user?.email || "U")
    .split(" ")
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const formattedDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "Active member";

  const roleLabel =
    user?.role === "admin"
      ? "Administrator"
      : user?.role === "researcher"
      ? "Research Analyst"
      : demo
      ? "Business Owner (Demo)"
      : "Business Decision Maker";

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) {
      setMessage({ tone: "danger", text: "Please enter your full name." });
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      await api.updateProfile({ full_name: fullName.trim() });
      await refreshUser();
      setMessage({ tone: "success", text: "Your profile has been successfully updated." });
    } catch {
      setMessage({ tone: "danger", text: "Could not update profile. Please try again." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Page
      title="My Profile"
      subtitle="View and manage your account identity, organization context, and personal preferences."
    >
      {message ? (
        <div className="mb-6">
          <Notice tone={message.tone}>{message.text}</Notice>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Profile Card */}
        <div className="rounded-2xl border border-border bg-surface p-6 text-center lg:col-span-1 shadow-sm">
          <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-tr from-accent/20 to-accent text-2xl font-bold text-accent shadow-inner">
            {initials}
          </div>
          <h2 className="mt-4 text-xl font-semibold text-foreground">
            {user?.full_name || "Account Member"}
          </h2>
          <p className="text-sm text-muted">{user?.email}</p>
          <div className="mt-3 inline-flex items-center rounded-full bg-accent/10 px-3 py-1 text-xs font-semibold text-accent">
            {roleLabel}
          </div>

          <div className="mt-6 border-t border-border pt-5 text-left text-xs text-muted space-y-2">
            <div className="flex justify-between">
              <span>Account ID</span>
              <span className="font-mono text-foreground text-[11px] truncate max-w-[150px]">{user?.id}</span>
            </div>
            <div className="flex justify-between">
              <span>Member Since</span>
              <span className="text-foreground">{formattedDate}</span>
            </div>
            <div className="flex justify-between">
              <span>Account Status</span>
              <span className="inline-flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span> Active
              </span>
            </div>
          </div>

          <div className="mt-6 pt-2">
            <Link href="/settings" className={`${btnSecondary} w-full text-xs`}>
              Open Account Settings
            </Link>
          </div>
        </div>

        {/* Profile Details & Form */}
        <div className="space-y-6 lg:col-span-2">
          {/* Editable personal info */}
          <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
            <h3 className="text-lg font-semibold text-foreground">Personal Information</h3>
            <p className="mt-1 text-sm text-muted">
              Update your name and personal details as they appear across DecisionGPT.
            </p>

            <form onSubmit={handleSave} className="mt-5 space-y-4">
              <div>
                <label htmlFor="fullName" className="block text-sm font-medium text-foreground">
                  Full Name
                </label>
                <input
                  id="fullName"
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Jane Doe"
                  className="mt-1.5 w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                />
              </div>

              <div>
                <label htmlFor="email" className="block text-sm font-medium text-foreground">
                  Email Address
                </label>
                <input
                  id="email"
                  type="email"
                  disabled
                  value={user?.email ?? ""}
                  className="mt-1.5 w-full cursor-not-allowed rounded-xl border border-border bg-muted-surface/60 px-4 py-2.5 text-sm text-muted focus:outline-none"
                />
                <p className="mt-1 text-xs text-muted">Email is managed by your organization identity.</p>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setFullName(user?.full_name ?? "")}
                  disabled={saving || fullName === (user?.full_name ?? "")}
                  className={btnSecondary}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving || !fullName.trim() || fullName === (user?.full_name ?? "")}
                  className={btnPrimary}
                >
                  {saving ? "Saving..." : "Save Changes"}
                </button>
              </div>
            </form>
          </section>

          {/* Connected Organization / Business Details */}
          <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-lg font-semibold text-foreground">Organization Context</h3>
                <p className="mt-1 text-sm text-muted">
                  The commercial workspace and dataset isolation environment assigned to your account.
                </p>
              </div>
              <Link href="/business-profile" className="text-xs font-medium text-accent hover:underline">
                Edit Profile &rarr;
              </Link>
            </div>

            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-border/80 bg-muted-surface/30 p-4">
                <div className="text-xs font-medium uppercase tracking-wider text-muted">Business Name</div>
                <div className="mt-1 text-base font-semibold text-foreground">{business?.name || "Workspace"}</div>
                {demo ? (
                  <span className="mt-1 inline-block text-xs text-amber-600 dark:text-amber-400">
                    Demonstration Business
                  </span>
                ) : null}
              </div>

              <div className="rounded-xl border border-border/80 bg-muted-surface/30 p-4">
                <div className="text-xs font-medium uppercase tracking-wider text-muted">Industry & Currency</div>
                <div className="mt-1 text-base font-semibold text-foreground">
                  {business?.industry || "Retail"} ({business?.currency || "INR"})
                </div>
                <div className="mt-1 text-xs text-muted">{business?.business_type || "Commercial"}</div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </Page>
  );
}

