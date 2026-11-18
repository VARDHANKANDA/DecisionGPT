"use client";

import { useState } from "react";

type DashboardTab = "overview" | "forecast" | "agents" | "decisions";

export function HeroDashboardVisual() {
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");

  return (
    <div className="relative mx-auto w-full max-w-2xl lg:max-w-none">
      {/* Background ambient lighting - restrained corporate glow */}
      <div
        className="pointer-events-none absolute -inset-1 rounded-3xl bg-gradient-to-r from-blue-600/15 via-indigo-600/10 to-slate-400/10 blur-xl"
        aria-hidden="true"
      />

      {/* Main SaaS Window Frame */}
      <div className="relative rounded-2xl border border-slate-200/90 bg-white shadow-[0_20px_50px_rgba(15,23,42,0.12)] ring-1 ring-slate-900/5 transition-all">
        {/* Window Chrome / Title Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50/80 px-4 py-2.5 rounded-t-2xl">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5" aria-hidden="true">
              <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
              <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
              <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
            </div>
            <span className="ml-2 hidden text-xs font-medium text-slate-500 sm:inline">
              app.decisiongpt.ai/workspace/overview
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200/70 px-2.5 py-0.5 text-[11px] font-medium text-emerald-700">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Deterministic Engine Active
            </span>
            <span className="text-[11px] text-slate-400 font-mono">Tenant #4829</span>
          </div>
        </div>

        {/* Dashboard Sub-header / Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-white px-4 py-3 sm:px-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-blue-700">Enterprise Workspace</span>
              <span className="text-slate-300">•</span>
              <span className="text-xs text-slate-500">Retail Dynamics Pvt Ltd</span>
            </div>
            <p className="text-sm font-bold text-slate-900">Decision Intelligence Control Plane</p>
          </div>

          {/* Interactive Navigation Pills */}
          <div className="flex flex-wrap items-center gap-1 rounded-lg bg-slate-100/80 p-1" role="tablist" aria-label="Dashboard views">
            <button
              role="tab"
              aria-selected={activeTab === "overview"}
              onClick={() => setActiveTab("overview")}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                activeTab === "overview"
                  ? "bg-white text-slate-900 shadow-xs font-semibold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Overview
            </button>
            <button
              role="tab"
              aria-selected={activeTab === "forecast"}
              onClick={() => setActiveTab("forecast")}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                activeTab === "forecast"
                  ? "bg-white text-slate-900 shadow-xs font-semibold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Forecasting
            </button>
            <button
              role="tab"
              aria-selected={activeTab === "agents"}
              onClick={() => setActiveTab("agents")}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                activeTab === "agents"
                  ? "bg-white text-slate-900 shadow-xs font-semibold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Multi-Agent
            </button>
            <button
              role="tab"
              aria-selected={activeTab === "decisions"}
              onClick={() => setActiveTab("decisions")}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                activeTab === "decisions"
                  ? "bg-white text-slate-900 shadow-xs font-semibold"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Decisions
            </button>
          </div>
        </div>

        {/* Dynamic Tab Body */}
        <div className="p-4 sm:p-6 space-y-5 bg-slate-50/40">
          {/* Top Performance Indicators / KPI Cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-slate-200/90 bg-white p-3.5 shadow-xs">
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Monthly Revenue</span>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="text-lg font-bold text-slate-900">₹28,45,200</span>
                <span className="text-[11px] font-semibold text-emerald-600">+14.2%</span>
              </div>
              <span className="text-[10px] text-slate-400">Sum of 1,420 transactions</span>
            </div>

            <div className="rounded-xl border border-slate-200/90 bg-white p-3.5 shadow-xs">
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Gross Margin</span>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="text-lg font-bold text-slate-900">38.6%</span>
                <span className="text-[11px] font-semibold text-blue-600">Stable</span>
              </div>
              <span className="text-[10px] text-slate-400">Recorded SKU costs</span>
            </div>

            <div className="rounded-xl border border-slate-200/90 bg-white p-3.5 shadow-xs">
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">28d Forecast</span>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="text-lg font-bold text-slate-900">18,420 u</span>
                <span className="text-[11px] font-semibold text-indigo-600">XGBoost</span>
              </div>
              <span className="text-[10px] text-slate-400">MAE 55.70 units</span>
            </div>

            <div className="rounded-xl border border-slate-200/90 bg-white p-3.5 shadow-xs">
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">Churn Risk</span>
              <div className="mt-1 flex items-baseline gap-1.5">
                <span className="text-lg font-bold text-slate-900">3.8%</span>
                <span className="text-[11px] font-semibold text-amber-600">Low Exposure</span>
              </div>
              <span className="text-[10px] text-slate-400">12 flagged accounts</span>
            </div>
          </div>

          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && (
            <div className="space-y-4">
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
                <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                      Revenue Trend &amp; Baseline Performance
                    </h4>
                    <p className="text-[11px] text-slate-500">Historical daily transactions vs 30-day baseline</p>
                  </div>
                  <div className="flex items-center gap-3 text-[11px]">
                    <span className="flex items-center gap-1 text-slate-600">
                      <span className="h-2 w-2 rounded-full bg-blue-600" /> Recorded Sales
                    </span>
                    <span className="flex items-center gap-1 text-slate-400">
                      <span className="h-2 w-2 rounded-full bg-slate-300" /> Baseline
                    </span>
                  </div>
                </div>

                {/* Realistic SVG Line Chart */}
                <div className="mt-4 h-36 w-full">
                  <svg className="h-full w-full overflow-visible" viewBox="0 0 500 130" fill="none">
                    {/* Grid lines */}
                    <line x1="0" y1="20" x2="500" y2="20" stroke="#f1f5f9" strokeWidth="1" />
                    <line x1="0" y1="55" x2="500" y2="55" stroke="#f1f5f9" strokeWidth="1" />
                    <line x1="0" y1="90" x2="500" y2="90" stroke="#f1f5f9" strokeWidth="1" />
                    <line x1="0" y1="125" x2="500" y2="125" stroke="#e2e8f0" strokeWidth="1" />

                    {/* Baseline dashed path */}
                    <path
                      d="M 10 95 Q 80 88 150 92 T 300 80 T 420 85 T 490 75"
                      stroke="#94a3b8"
                      strokeWidth="1.5"
                      strokeDasharray="4 4"
                      fill="none"
                    />

                    {/* Gradient under sales curve */}
                    <defs>
                      <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#2563eb" stopOpacity="0.20" />
                        <stop offset="100%" stopColor="#2563eb" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    <path
                      d="M 10 90 Q 75 70 140 75 T 260 48 T 380 40 T 490 28 L 490 125 L 10 125 Z"
                      fill="url(#revenueGradient)"
                    />

                    {/* Actual recorded revenue curve */}
                    <path
                      d="M 10 90 Q 75 70 140 75 T 260 48 T 380 40 T 490 28"
                      stroke="#2563eb"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      fill="none"
                    />

                    {/* Data Markers */}
                    <circle cx="140" cy="75" r="3.5" fill="#2563eb" className="animate-pulse" />
                    <circle cx="260" cy="48" r="3.5" fill="#2563eb" />
                    <circle cx="380" cy="40" r="3.5" fill="#2563eb" />
                    <circle cx="490" cy="28" r="4.5" fill="#1d4ed8" stroke="#ffffff" strokeWidth="2" />
                  </svg>
                </div>

                <div className="mt-2 flex justify-between text-[10px] text-slate-400 border-t border-slate-100 pt-1.5 font-mono">
                  <span>Day 1 (₹62k)</span>
                  <span>Day 10 (₹78k)</span>
                  <span>Day 20 (₹94k)</span>
                  <span>Day 30 (₹1,18k)</span>
                </div>
              </div>

              {/* Two Column Sub-Panels: Multi-Agent Quick Insight + Operational Risk */}
              <div className="grid gap-3 sm:grid-cols-2 text-xs">
                <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-xs">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                    <span className="font-semibold text-slate-800 flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-blue-600" />
                      Multi-Agent Coordination Status
                    </span>
                    <span className="rounded bg-blue-50 text-blue-700 font-semibold px-2 py-0.5 text-[10px]">Consensus Ready</span>
                  </div>
                  <p className="mt-2 text-slate-600 text-[11px] leading-relaxed">
                    Strategy Optimiser synthesized inputs from Business Analyst, Financial Advisor, and Risk Manager.
                    Recommended inventory adjustment for peak weekend volume.
                  </p>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-xs">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                    <span className="font-semibold text-slate-800 flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-emerald-500" />
                      Business Risk Radar
                    </span>
                    <span className="rounded bg-emerald-50 text-emerald-700 font-semibold px-2 py-0.5 text-[10px]">Optimal</span>
                  </div>
                  <div className="mt-2 space-y-1 text-[11px] text-slate-600">
                    <div className="flex justify-between">
                      <span>Stockout Probability:</span>
                      <span className="font-semibold text-slate-800">1.2% (Low)</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Working Capital Turnover:</span>
                      <span className="font-semibold text-slate-800">4.8x / quarter</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: FORECASTING */}
          {activeTab === "forecast" && (
            <div className="space-y-3">
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
                <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                      Multi-Horizon Demand Projections
                    </h4>
                    <p className="text-[11px] text-slate-500">Trained regression ensembles across 3 calendar horizons</p>
                  </div>
                  <span className="text-[11px] rounded bg-indigo-50 text-indigo-700 px-2 py-0.5 font-medium">
                    Trained ML Models
                  </span>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-3 text-xs">
                  <div className="rounded-lg border border-slate-200/80 bg-slate-50/50 p-3">
                    <p className="font-bold text-slate-900">Daily Demand Horizon</p>
                    <p className="text-[11px] text-slate-500 font-mono mt-0.5">HistGradientBoosting</p>
                    <p className="mt-2 text-sm font-semibold text-blue-700">480 ± 24 units/day</p>
                    <p className="text-[10px] text-slate-400 mt-1">MAE: 13.85 units</p>
                  </div>
                  <div className="rounded-lg border border-slate-200/80 bg-slate-50/50 p-3">
                    <p className="font-bold text-slate-900">14-Day Cumulative</p>
                    <p className="text-[11px] text-slate-500 font-mono mt-0.5">Random Forest Ensemble</p>
                    <p className="mt-2 text-sm font-semibold text-blue-700">6,850 ± 190 units</p>
                    <p className="text-[10px] text-slate-400 mt-1">MAE: 58.64 units</p>
                  </div>
                  <div className="rounded-lg border border-slate-200/80 bg-slate-50/50 p-3">
                    <p className="font-bold text-slate-900">28-Day Cumulative</p>
                    <p className="text-[11px] text-slate-500 font-mono mt-0.5">XGBoost Regressor</p>
                    <p className="mt-2 text-sm font-semibold text-blue-700">13,920 ± 340 units</p>
                    <p className="text-[10px] text-slate-400 mt-1">MAE: 55.70 units</p>
                  </div>
                </div>

                <div className="mt-3 rounded-lg bg-blue-50/60 p-2.5 text-[11px] text-blue-900">
                  <p>
                    <strong>Validation Method:</strong> Time-series rolling cross-validation against recorded receipts.
                    Confidence bands adapt dynamically to observed weekly demand seasonality.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: MULTI-AGENT */}
          {activeTab === "agents" && (
            <div className="space-y-3">
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
                <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                      Coordinated Multi-Agent Review
                    </h4>
                    <p className="text-[11px] text-slate-500">Autonomous perspectives evaluating candidate decision #402</p>
                  </div>
                  <span className="text-[11px] rounded bg-slate-100 text-slate-700 px-2 py-0.5 font-medium">
                    5 Specialized Agents
                  </span>
                </div>

                <div className="mt-3 space-y-2 text-xs">
                  <div className="flex items-start gap-2.5 rounded-lg border border-slate-100 bg-slate-50/60 p-2.5">
                    <span className="text-base" aria-hidden="true">📊</span>
                    <div className="flex-1">
                      <div className="flex justify-between items-baseline">
                        <span className="font-semibold text-slate-900">Business Analyst</span>
                        <span className="text-[10px] text-slate-400">Sales &amp; Velocity Audit</span>
                      </div>
                      <p className="text-[11px] text-slate-600 mt-0.5">
                        Identified steady 14.2% expansion in Category A; inventory velocity indicates immediate reorder window.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2.5 rounded-lg border border-slate-100 bg-slate-50/60 p-2.5">
                    <span className="text-base" aria-hidden="true">💰</span>
                    <div className="flex-1">
                      <div className="flex justify-between items-baseline">
                        <span className="font-semibold text-slate-900">Financial Advisor</span>
                        <span className="text-[10px] text-slate-400">Operating Margin Check</span>
                      </div>
                      <p className="text-[11px] text-slate-600 mt-0.5">
                        Current gross margin of 38.6% supports safety-stock expansion without impacting working capital liquidity.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2.5 rounded-lg border border-slate-100 bg-slate-50/60 p-2.5">
                    <span className="text-base" aria-hidden="true">🛡️</span>
                    <div className="flex-1">
                      <div className="flex justify-between items-baseline">
                        <span className="font-semibold text-slate-900">Risk Manager</span>
                        <span className="text-[10px] text-slate-400">Downside Exposure</span>
                      </div>
                      <p className="text-[11px] text-slate-600 mt-0.5">
                        Flagged 4-day supplier delivery variance during month-end; recommends early purchase order release.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: DECISIONS */}
          {activeTab === "decisions" && (
            <div className="space-y-3">
              <div className="rounded-xl border border-blue-200/90 bg-blue-50/30 p-4 shadow-xs">
                <div className="flex items-center justify-between border-b border-blue-100 pb-2.5">
                  <span className="text-xs font-bold uppercase tracking-wider text-blue-900">
                    Ranked Strategic Decision Card
                  </span>
                  <span className="rounded bg-blue-600 text-white font-medium px-2 py-0.5 text-[10px]">
                    Rank #1 Option
                  </span>
                </div>

                <div className="mt-3">
                  <h5 className="text-sm font-bold text-slate-900">
                    Reallocate Working Capital to Fast-Rotating High-Margin Inventory
                  </h5>
                  <p className="mt-1 text-xs text-slate-600 leading-relaxed">
                    Shift budget from slow-moving Category C products into Category A leading SKUs to satisfy forecasted 28-day demand surge.
                  </p>

                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded-lg bg-white p-2.5 border border-slate-200">
                      <span className="text-[10px] uppercase font-semibold text-slate-400">Projected Margin Lift</span>
                      <p className="text-sm font-bold text-emerald-700">+₹1,84,000</p>
                    </div>
                    <div className="rounded-lg bg-white p-2.5 border border-slate-200">
                      <span className="text-[10px] uppercase font-semibold text-slate-400">Downside Risk Check</span>
                      <p className="text-sm font-bold text-slate-800">Controlled (Low)</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Audit & Disclaimer footer */}
          <div className="flex items-center justify-between border-t border-slate-200/80 pt-2 text-[10px] text-slate-400">
            <span>Illustrative interface preview</span>
            <span>Real metrics strictly scoped by business_id</span>
          </div>
        </div>
      </div>
    </div>
  );
}
