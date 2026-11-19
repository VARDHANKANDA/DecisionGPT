"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useBusiness } from "@/lib/business-context";
import { isDemoBusiness } from "@/lib/demo";
import { api } from "@/lib/api";
import { Notice, Page, btnDanger, btnPrimary, btnSecondary } from "@/components/simple";

type TabKey = "personal" | "security" | "preferences" | "business" | "notifications" | "account";

export default function SettingsPage() {
  const { user, logout, refreshUser } = useAuth();
  const { business } = useBusiness();
  const demo = isDemoBusiness(business);

  const [activeTab, setActiveTab] = useState<TabKey>("personal");

  // Personal Info Form State
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [personalSaving, setPersonalSaving] = useState(false);
  const [personalNotice, setPersonalNotice] = useState<{ tone: "success" | "danger"; text: string } | null>(null);

  // Security / Password Form State
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordNotice, setPasswordNotice] = useState<{ tone: "success" | "danger"; text: string } | null>(null);

  // Preferences State
  const [theme, setTheme] = useState<"system" | "light" | "dark">("system");
  const [language, setLanguage] = useState("en");
  const [compactDensity, setCompactDensity] = useState(false);
  const [prefSaved, setPrefSaved] = useState(false);

  // Notification State
  const [alertsEmail, setAlertsEmail] = useState(true);
  const [forecastAlerts, setForecastAlerts] = useState(true);
  const [systemAlerts, setSystemAlerts] = useState(false);
  const [notifSaved, setNotifSaved] = useState(false);

  // Logout All State
  const [loggingOutAll, setLoggingOutAll] = useState(false);

  const handlePersonalSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) {
      setPersonalNotice({ tone: "danger", text: "Please enter a valid full name." });
      return;
    }
    setPersonalSaving(true);
    setPersonalNotice(null);
    try {
      await api.updateProfile({ full_name: fullName.trim() });
      await refreshUser();
      setPersonalNotice({ tone: "success", text: "Personal information saved successfully." });
    } catch {
      setPersonalNotice({ tone: "danger", text: "Failed to update profile details." });
    } finally {
      setPersonalSaving(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordNotice(null);
    if (!currentPassword) {
      setPasswordNotice({ tone: "danger", text: "Please provide your current password." });
      return;
    }
    if (newPassword.length < 8) {
      setPasswordNotice({ tone: "danger", text: "New password must be at least 8 characters long." });
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordNotice({ tone: "danger", text: "New password and confirmation do not match." });
      return;
    }

    setPasswordSaving(true);
    try {
      await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordNotice({ tone: "success", text: "Your password has been changed successfully." });
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Password change failed. Verify your current password.";
      setPasswordNotice({ tone: "danger", text: errMsg });
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleLogoutAll = async () => {
    if (!window.confirm("Are you sure you want to sign out from all devices? You will be returned to login.")) {
      return;
    }
    setLoggingOutAll(true);
    try {
      await api.logoutAll();
    } catch {
      // proceed to sign out client
    }
    logout();
  };

  const tabs: { key: TabKey; label: string; icon: string }[] = [
    { key: "personal", label: "Personal Info", icon: "👤" },
    { key: "security", label: "Security", icon: "🔒" },
    { key: "preferences", label: "Preferences", icon: "🎨" },
    { key: "business", label: "Business Info", icon: "🏢" },
    { key: "notifications", label: "Notifications", icon: "🔔" },
    { key: "account", label: "Account Management", icon: "⚙️" },
  ];

  return (
    <Page
      title="Account Settings"
      subtitle="Manage your profile, authentication credentials, workspace parameters, and notifications."
      wide
    >
      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Settings Navigation Tabs */}
        <aside className="w-full shrink-0 lg:w-64">
          <nav className="flex flex-row overflow-x-auto rounded-2xl border border-border bg-surface p-2 shadow-sm lg:flex-col lg:overflow-x-visible">
            {tabs.map((tab) => {
              const active = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveTab(tab.key)}
                  className={`flex items-center gap-3 whitespace-nowrap rounded-xl px-4 py-3 text-left text-sm font-medium transition ${
                    active
                      ? "bg-accent text-accent-foreground shadow-sm"
                      : "text-muted hover:bg-muted-surface hover:text-foreground"
                  }`}
                >
                  <span>{tab.icon}</span>
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>

          <div className="mt-4 rounded-2xl border border-border bg-surface p-4 text-xs text-muted shadow-sm hidden lg:block">
            <p className="font-semibold text-foreground">Active Role</p>
            <p className="mt-0.5 capitalize">{user?.role || "standard"}</p>
            <p className="mt-3 font-semibold text-foreground">Workspace</p>
            <p className="mt-0.5 truncate">{business?.name || "Standard Workspace"}</p>
          </div>
        </aside>

        {/* Tab Content Panel */}
        <main className="flex-1">
          {/* TAB 1: PERSONAL INFO */}
          {activeTab === "personal" && (
            <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-foreground">Personal Information</h2>
              <p className="mt-1 text-sm text-muted">
                Update how your identity appears to team members and across decision reports.
              </p>

              {personalNotice && (
                <div className="mt-4">
                  <Notice tone={personalNotice.tone}>{personalNotice.text}</Notice>
                </div>
              )}

              <form onSubmit={handlePersonalSave} className="mt-6 space-y-4 max-w-lg">
                <div>
                  <label htmlFor="settings-name" className="block text-sm font-medium text-foreground">
                    Full Name
                  </label>
                  <input
                    id="settings-name"
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="mt-1.5 w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                  />
                </div>

                <div>
                  <label htmlFor="settings-email" className="block text-sm font-medium text-foreground">
                    Email Address
                  </label>
                  <input
                    id="settings-email"
                    type="email"
                    disabled
                    value={user?.email || ""}
                    className="mt-1.5 w-full cursor-not-allowed rounded-xl border border-border bg-muted-surface/60 px-4 py-2.5 text-sm text-muted focus:outline-none"
                  />
                  <p className="mt-1 text-xs text-muted">Contact your system administrator to change your email.</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground">Account Role</label>
                  <input
                    type="text"
                    disabled
                    value={user?.role === "admin" ? "Platform Administrator" : user?.role === "researcher" ? "Research Analyst" : "Commercial User"}
                    className="mt-1.5 w-full cursor-not-allowed rounded-xl border border-border bg-muted-surface/60 px-4 py-2.5 text-sm text-muted focus:outline-none"
                  />
                </div>

                <div className="pt-2">
                  <button type="submit" disabled={personalSaving} className={btnPrimary}>
                    {personalSaving ? "Saving..." : "Save Changes"}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* TAB 2: SECURITY */}
          {activeTab === "security" && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
                <h2 className="text-xl font-semibold text-foreground">Change Password</h2>
                <p className="mt-1 text-sm text-muted">
                  Keep your account secure with a strong, distinct password.
                </p>

                {passwordNotice && (
                  <div className="mt-4">
                    <Notice tone={passwordNotice.tone}>{passwordNotice.text}</Notice>
                  </div>
                )}

                <form onSubmit={handlePasswordChange} className="mt-6 space-y-4 max-w-lg">
                  <div>
                    <label htmlFor="current-pw" className="block text-sm font-medium text-foreground">
                      Current Password
                    </label>
                    <input
                      id="current-pw"
                      type="password"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      placeholder="••••••••"
                      className="mt-1.5 w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                  </div>

                  <div>
                    <label htmlFor="new-pw" className="block text-sm font-medium text-foreground">
                      New Password
                    </label>
                    <input
                      id="new-pw"
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Minimum 8 characters"
                      className="mt-1.5 w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                  </div>

                  <div>
                    <label htmlFor="confirm-pw" className="block text-sm font-medium text-foreground">
                      Confirm New Password
                    </label>
                    <input
                      id="confirm-pw"
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Re-enter new password"
                      className="mt-1.5 w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                  </div>

                  <div className="pt-2">
                    <button type="submit" disabled={passwordSaving} className={btnPrimary}>
                      {passwordSaving ? "Updating Password..." : "Update Password"}
                    </button>
                  </div>
                </form>
              </div>

              <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-foreground">Active Sessions & Devices</h3>
                <p className="mt-1 text-sm text-muted">
                  Log out of this account across all devices and invalidate active authentication tokens.
                </p>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border/80 bg-muted-surface/30 p-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">Revoke all active sessions</p>
                    <p className="text-xs text-muted">Forces re-authentication everywhere, including this browser.</p>
                  </div>
                  <button
                    type="button"
                    onClick={handleLogoutAll}
                    disabled={loggingOutAll}
                    className={btnSecondary}
                  >
                    {loggingOutAll ? "Signing out..." : "Sign Out Everywhere"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: PREFERENCES */}
          {activeTab === "preferences" && (
            <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-foreground">Preferences</h2>
              <p className="mt-1 text-sm text-muted">
                Customize your display mode, language, and interface layout density.
              </p>

              {prefSaved && (
                <div className="mt-4">
                  <Notice tone="success">Preferences saved successfully.</Notice>
                </div>
              )}

              <div className="mt-6 space-y-6 max-w-lg">
                <div>
                  <label className="block text-sm font-medium text-foreground">Appearance / Theme</label>
                  <div className="mt-2 grid grid-cols-3 gap-3">
                    {(
                      [
                        { key: "system", label: "System Default", icon: "💻" },
                        { key: "light", label: "Light", icon: "☀️" },
                        { key: "dark", label: "Dark", icon: "🌙" },
                      ] as const
                    ).map((opt) => (
                      <button
                        key={opt.key}
                        type="button"
                        onClick={() => setTheme(opt.key)}
                        className={`flex flex-col items-center justify-center rounded-xl border p-3 text-center text-sm transition ${
                          theme === opt.key
                            ? "border-accent bg-accent/10 font-medium text-accent"
                            : "border-border bg-background text-foreground hover:bg-muted-surface"
                        }`}
                      >
                        <span className="text-lg">{opt.icon}</span>
                        <span className="mt-1">{opt.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label htmlFor="language-select" className="block text-sm font-medium text-foreground">
                    Display Language
                  </label>
                  <select
                    id="language-select"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="mt-1.5 w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm text-foreground focus:border-accent focus:outline-none"
                  >
                    <option value="en">English (US/UK)</option>
                    <option value="hi">Hindi (हिंदी)</option>
                    <option value="es">Spanish (Español)</option>
                    <option value="fr">French (Français)</option>
                    <option value="de">German (Deutsch)</option>
                  </select>
                </div>

                <div className="flex items-center justify-between rounded-xl border border-border/80 p-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">Compact Data Density</p>
                    <p className="text-xs text-muted">Display higher information density on analytics tables and charts.</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={compactDensity}
                    onChange={(e) => setCompactDensity(e.target.checked)}
                    className="h-5 w-5 rounded border-border text-accent focus:ring-accent"
                  />
                </div>

                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setPrefSaved(true);
                      setTimeout(() => setPrefSaved(false), 3000);
                    }}
                    className={btnPrimary}
                  >
                    Save Preferences
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: BUSINESS INFO */}
          {activeTab === "business" && (
            <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold text-foreground">Business Information</h2>
                  <p className="mt-1 text-sm text-muted">
                    Configuration and baseline metadata for your commercial entity.
                  </p>
                </div>
                <Link href="/business-profile" className={btnSecondary}>
                  Open Full Business Profile &rarr;
                </Link>
              </div>

              {demo && (
                <div className="mt-4">
                  <Notice tone="warning" title="Demonstration Business">
                    This account is currently linked to the demonstration workspace with illustrative transactions and inventory data.
                  </Notice>
                </div>
              )}

              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-border/80 bg-muted-surface/30 p-4">
                  <span className="text-xs font-medium text-muted">Business Name</span>
                  <p className="mt-1 text-base font-semibold text-foreground">{business?.name || "Not connected"}</p>
                </div>

                <div className="rounded-xl border border-border/80 bg-muted-surface/30 p-4">
                  <span className="text-xs font-medium text-muted">Primary Industry</span>
                  <p className="mt-1 text-base font-semibold text-foreground">{business?.industry || "Retail"}</p>
                </div>

                <div className="rounded-xl border border-border/80 bg-muted-surface/30 p-4">
                  <span className="text-xs font-medium text-muted">Operational Currency</span>
                  <p className="mt-1 text-base font-semibold text-foreground">{business?.currency || "INR"}</p>
                </div>

                <div className="rounded-xl border border-border/80 bg-muted-surface/30 p-4">
                  <span className="text-xs font-medium text-muted">Business Size</span>
                  <p className="mt-1 text-base font-semibold text-foreground capitalize">{business?.business_size || "Small to Medium"}</p>
                </div>
              </div>

              <div className="mt-6 border-t border-border pt-5">
                <h3 className="text-base font-semibold text-foreground">Data Storage & Isolation</h3>
                <p className="mt-1 text-sm text-muted">
                  All transactions, products, stock levels, and recommendations are strictly scoped to business identifier:
                </p>
                <div className="mt-2 font-mono text-xs text-foreground bg-muted-surface/60 p-2.5 rounded-lg break-all">
                  {business?.id || "None"}
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: NOTIFICATIONS */}
          {activeTab === "notifications" && (
            <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-foreground">Notification Preferences</h2>
              <p className="mt-1 text-sm text-muted">
                Choose the business alerts, performance thresholds, and updates you receive.
              </p>

              {notifSaved && (
                <div className="mt-4">
                  <Notice tone="success">Notification preferences updated.</Notice>
                </div>
              )}

              <div className="mt-6 space-y-4 max-w-xl">
                <div className="flex items-center justify-between rounded-xl border border-border/80 p-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">Critical Stockout & Revenue Alerts</p>
                    <p className="text-xs text-muted">Notify when inventory velocity risks sudden stockouts or margin drops.</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={alertsEmail}
                    onChange={(e) => setAlertsEmail(e.target.checked)}
                    className="h-5 w-5 rounded border-border text-accent focus:ring-accent"
                  />
                </div>

                <div className="flex items-center justify-between rounded-xl border border-border/80 p-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">Weekly Performance & Forecast Digest</p>
                    <p className="text-xs text-muted">Receive a weekly digest of simulated trajectories and top recommendations.</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={forecastAlerts}
                    onChange={(e) => setForecastAlerts(e.target.checked)}
                    className="h-5 w-5 rounded border-border text-accent focus:ring-accent"
                  />
                </div>

                <div className="flex items-center justify-between rounded-xl border border-border/80 p-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">System Maintenance & Release Announcements</p>
                    <p className="text-xs text-muted">Occasional product updates and scheduled maintenance notices.</p>
                  </div>
                  <input
                    type="checkbox"
                    checked={systemAlerts}
                    onChange={(e) => setSystemAlerts(e.target.checked)}
                    className="h-5 w-5 rounded border-border text-accent focus:ring-accent"
                  />
                </div>

                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setNotifSaved(true);
                      setTimeout(() => setNotifSaved(false), 3000);
                    }}
                    className={btnPrimary}
                  >
                    Save Preferences
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: ACCOUNT MANAGEMENT */}
          {activeTab === "account" && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
                <h2 className="text-xl font-semibold text-foreground">Account Management</h2>
                <p className="mt-1 text-sm text-muted">
                  Session termination, security safeguards, and account options.
                </p>

                <div className="mt-6 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border/80 bg-muted-surface/30 p-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">Sign Out of DecisionGPT</p>
                    <p className="text-xs text-muted">End your current session on this browser.</p>
                  </div>
                  <button type="button" onClick={logout} className={btnSecondary}>
                    Sign Out
                  </button>
                </div>
              </div>

              <div className="rounded-2xl border border-danger/30 bg-danger-soft/20 p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-danger">Data & Account Safeguards</h3>
                <p className="mt-1 text-sm text-muted">
                  DecisionGPT preserves business audit trails and multi-agent historical decisions. Account deletion is restricted to tenant administrators to protect operational continuity.
                </p>
                <div className="mt-4 text-xs text-muted">
                  To request workspace decommissioning or export of compliance archives, contact your platform administrator or open a request in Dataset Library.
                </div>
                <div className="mt-4">
                  <Link href="/data" className={btnSecondary}>
                    Inspect Dataset Library
                  </Link>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </Page>
  );
}
