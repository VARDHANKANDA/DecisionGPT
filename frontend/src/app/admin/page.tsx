"use client";

import { useEffect, useState } from "react";
import { api, type AdminUser, type SystemMonitoring, type SystemSettings } from "@/lib/api";

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [monitoring, setMonitoring] = useState<SystemMonitoring | null>(null);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  async function loadData() {
    setError(null);
    try {
      const [u, m, s] = await Promise.all([
        api.adminListUsers(),
        api.adminGetMonitoring(),
        api.adminGetSettings(),
      ]);
      setUsers(u);
      setMonitoring(m);
      setSettings(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load administrative telemetry.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  async function toggleUserStatus(user: AdminUser) {
    setUpdatingId(user.id);
    setStatusMessage(null);
    setError(null);
    try {
      const newStatus = !user.is_active;
      const updated = await api.adminUpdateUserStatus(user.id, newStatus);
      setUsers((prev) => (prev ? prev.map((u) => (u.id === updated.id ? updated : u)) : prev));
      setStatusMessage(
        `User ${updated.email} successfully ${updated.is_active ? "activated" : "deactivated"}. Any active sessions invalidated.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user status.");
    } finally {
      setUpdatingId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent"></div>
          <p className="text-sm text-muted">Loading administrative platform data…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Title & System Status Banner */}
      <div className="rounded-2xl border border-border bg-gradient-to-r from-surface via-surface to-muted-surface/30 p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                ● Infrastructure Operational
              </span>
              <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-medium text-accent">
                Admin Control Plane
              </span>
            </div>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-foreground">
              Administrative Dashboard &amp; User Management
            </h1>
            <p className="mt-1 text-sm text-muted max-w-2xl">
              System monitoring, active user account management, role-based authorization controls, and server telemetry.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setLoading(true);
              void loadData();
            }}
            className="self-start rounded-full border border-border bg-surface px-4 py-2 text-xs font-medium text-foreground hover:bg-muted-surface transition shadow-sm"
          >
            ↻ Refresh Telemetry
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-xl bg-danger-soft p-4 text-sm text-danger" role="alert">
          {error}
        </div>
      ) : null}

      {statusMessage ? (
        <div className="rounded-xl bg-success-soft p-4 text-sm text-success" role="status">
          ✓ {statusMessage}
        </div>
      ) : null}

      {/* KPI Stat Grid */}
      {monitoring ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
          <div className="rounded-xl border border-border bg-surface p-4">
            <span className="text-xs font-medium text-muted">Total Users</span>
            <p className="mt-1 text-2xl font-bold text-foreground">{monitoring.counts.total_users}</p>
            <span className="text-[11px] text-muted">{monitoring.counts.active_users} active</span>
          </div>

          <div className="rounded-xl border border-border bg-surface p-4">
            <span className="text-xs font-medium text-muted">Admin Role</span>
            <p className="mt-1 text-2xl font-bold text-foreground">{monitoring.users_by_role["admin"] || 0}</p>
            <span className="text-[11px] text-muted">Platform admins</span>
          </div>

          <div className="rounded-xl border border-border bg-surface p-4">
            <span className="text-xs font-medium text-muted">Researcher Role</span>
            <p className="mt-1 text-2xl font-bold text-foreground">{monitoring.users_by_role["researcher"] || 0}</p>
            <span className="text-[11px] text-muted">Research console</span>
          </div>

          <div className="rounded-xl border border-border bg-surface p-4">
            <span className="text-xs font-medium text-muted">SME Users</span>
            <p className="mt-1 text-2xl font-bold text-foreground">{monitoring.users_by_role["sme"] || 0}</p>
            <span className="text-[11px] text-muted">Business operators</span>
          </div>

          <div className="rounded-xl border border-border bg-surface p-4">
            <span className="text-xs font-medium text-muted">Businesses</span>
            <p className="mt-1 text-2xl font-bold text-foreground">{monitoring.counts.businesses}</p>
            <span className="text-[11px] text-muted">Tenants scoped</span>
          </div>

          <div className="rounded-xl border border-border bg-surface p-4">
            <span className="text-xs font-medium text-muted">ML Models</span>
            <p className="mt-1 text-2xl font-bold text-foreground">{monitoring.counts.registered_models}</p>
            <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
              {monitoring.counts.active_models} active
            </span>
          </div>
        </div>
      ) : null}

      {/* User Management Section */}
      <section id="users" className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
        <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-bold text-foreground">User Management</h2>
            <p className="text-xs text-muted">
              Manage authentication states, verify role assignments, and toggle access permissions across all registered accounts.
            </p>
          </div>
          <span className="text-xs text-muted">
            {users ? `${users.length} accounts registered` : ""}
          </span>
        </div>

        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-muted-surface/50 text-xs text-muted">
              <tr>
                <th className="px-4 py-3 font-semibold">User / Email</th>
                <th className="px-4 py-3 font-semibold">Role</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Token Version</th>
                <th className="px-4 py-3 font-semibold">Created Date</th>
                <th className="px-4 py-3 text-right font-semibold">Account Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {users && users.length > 0 ? (
                users.map((u) => {
                  const isUpdating = updatingId === u.id;
                  return (
                    <tr key={u.id} className="hover:bg-muted-surface/30 transition">
                      <td className="px-4 py-3.5">
                        <div className="font-medium text-foreground">{u.full_name || "—"}</div>
                        <div className="font-mono text-xs text-muted">{u.email}</div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                            u.role === "admin"
                              ? "bg-purple-500/10 text-purple-600 dark:text-purple-400"
                              : u.role === "researcher"
                              ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                              : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                          }`}
                        >
                          {u.role.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3.5">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                            u.is_active
                              ? "bg-success-soft text-success"
                              : "bg-danger-soft text-danger"
                          }`}
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              u.is_active ? "bg-success" : "bg-danger"
                            }`}
                          ></span>
                          {u.is_active ? "Active" : "Suspended"}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 font-mono text-xs text-muted">
                        v{u.token_version}
                      </td>
                      <td className="px-4 py-3.5 text-xs text-muted">
                        {new Date(u.created_at).toLocaleDateString("en-IN", {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        })}
                      </td>
                      <td className="px-4 py-3.5 text-right">
                        <button
                          type="button"
                          disabled={isUpdating}
                          onClick={() => void toggleUserStatus(u)}
                          className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 ${
                            u.is_active
                              ? "border-danger/30 text-danger hover:bg-danger-soft"
                              : "border-success/30 text-success hover:bg-success-soft"
                          }`}
                        >
                          {isUpdating
                            ? "Updating…"
                            : u.is_active
                            ? "Suspend Access"
                            : "Activate Account"}
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-muted">
                    No users found in database.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* System Monitoring & Telemetry Details */}
      {monitoring ? (
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Platform Resource Counts */}
          <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
            <h2 className="text-base font-bold text-foreground">Database Records &amp; Storage Entities</h2>
            <p className="mt-0.5 text-xs text-muted">
              Active ground-truth records across multi-tenant businesses.
            </p>
            <div className="mt-4 divide-y divide-border text-sm">
              <div className="flex items-center justify-between py-2">
                <span className="text-muted">Total Sales Transactions</span>
                <span className="font-semibold text-foreground">
                  {monitoring.counts.sales_transactions.toLocaleString("en-IN")}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-muted">Registered Catalog Products</span>
                <span className="font-semibold text-foreground">
                  {monitoring.counts.products.toLocaleString("en-IN")}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-muted">Customers Profiles</span>
                <span className="font-semibold text-foreground">
                  {monitoring.counts.customers.toLocaleString("en-IN")}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-muted">Inventory SKU Items</span>
                <span className="font-semibold text-foreground">
                  {monitoring.counts.inventory_items.toLocaleString("en-IN")}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-muted">Business Memory &amp; Decision Logs</span>
                <span className="font-semibold text-foreground">
                  {monitoring.counts.business_memories.toLocaleString("en-IN")}
                </span>
              </div>
            </div>
          </div>

          {/* Infrastructure Specs */}
          <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
            <h2 className="text-base font-bold text-foreground">Runtime Environment &amp; Engine Specs</h2>
            <p className="mt-0.5 text-xs text-muted">
              Underlying execution environment and configuration parameters.
            </p>
            <div className="mt-4 divide-y divide-border text-sm">
              <div className="flex items-center justify-between py-2">
                <span className="text-muted">Python Runtime</span>
                <span className="font-mono text-xs font-semibold text-foreground">
                  Python {monitoring.system_info.python_version}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-muted">Host Platform</span>
                <span className="font-mono text-xs text-foreground truncate max-w-[240px]">
                  {monitoring.system_info.platform}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-muted">Database Engine</span>
                <span className="font-mono text-xs uppercase font-semibold text-foreground">
                  {monitoring.system_info.database_type}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-muted">Security &amp; Auth Mode</span>
                <span className="rounded bg-accent-soft px-2 py-0.5 text-xs font-bold text-accent">
                  {monitoring.system_info.server_mode}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-muted">Server Telemetry Timestamp</span>
                <span className="font-mono text-xs text-muted">
                  {new Date(monitoring.timestamp).toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {/* Security & Settings Section */}
      {settings ? (
        <section id="security" className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <h2 className="text-base font-bold text-foreground">Security Policies &amp; Role-Based Access Control</h2>
          <p className="mt-0.5 text-xs text-muted">
            Hard boundaries enforced across backend microservices and API gateways.
          </p>

          <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-border bg-muted-surface/30 p-4">
              <span className="font-semibold text-sm text-foreground">Admin Role</span>
              <p className="mt-1 text-xs text-muted">
                Full administrative dashboard access, user lifecycle management, application telemetry, and research console inspection.
              </p>
              <ul className="mt-3 space-y-1 text-xs text-muted">
                {settings.role_hierarchy["admin"]?.map((p) => (
                  <li key={p} className="flex items-center gap-1.5">
                    <span className="text-success">✓</span> {p.replace(/_/g, " ")}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-xl border border-border bg-muted-surface/30 p-4">
              <span className="font-semibold text-sm text-foreground">Researcher Role</span>
              <p className="mt-1 text-xs text-muted">
                Full access to Research Console, ML model comparisons, evaluation metrics, scientific benchmarks, and dataset validation.
              </p>
              <ul className="mt-3 space-y-1 text-xs text-muted">
                {settings.role_hierarchy["researcher"]?.map((p) => (
                  <li key={p} className="flex items-center gap-1.5">
                    <span className="text-success">✓</span> {p.replace(/_/g, " ")}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-xl border border-border bg-muted-surface/30 p-4">
              <span className="font-semibold text-sm text-foreground">Standard User (SME)</span>
              <p className="mt-1 text-xs text-muted">
                Dedicated business workspace, deterministic analytics chat, multi-agent debates, what-if simulations, and 5-language voice interface.
              </p>
              <ul className="mt-3 space-y-1 text-xs text-muted">
                {settings.role_hierarchy["sme"]?.map((p) => (
                  <li key={p} className="flex items-center gap-1.5">
                    <span className="text-success">✓</span> {p.replace(/_/g, " ")}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
