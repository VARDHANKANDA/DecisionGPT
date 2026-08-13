"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type CausalEdge, type CausalGraph } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { Card, EmptyState, PageHeader, PrimaryButton, SecondaryLink } from "@/components/ui";

const NODE_LABELS: Record<string, string> = {
  marketing_spend: "Marketing Spend",
  website_traffic: "Website Traffic",
  conversion_rate: "Conversion Rate",
  orders: "Orders",
  revenue: "Revenue",
  profit: "Profit",
  price: "Price",
  demand: "Demand",
  sales: "Sales",
  customer_experience: "Customer Experience",
  retention: "Retention",
  repeat_purchases: "Repeat Purchases",
  inventory: "Inventory",
  availability: "Availability",
};

const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  marketing_spend: { x: 70, y: 60 },
  website_traffic: { x: 250, y: 60 },
  conversion_rate: { x: 430, y: 60 },
  orders: { x: 610, y: 60 },

  price: { x: 70, y: 170 },
  demand: { x: 250, y: 170 },
  sales: { x: 430, y: 170 },

  customer_experience: { x: 70, y: 280 },
  retention: { x: 250, y: 280 },
  repeat_purchases: { x: 430, y: 280 },

  inventory: { x: 70, y: 390 },
  availability: { x: 250, y: 390 },

  revenue: { x: 790, y: 170 },
  profit: { x: 940, y: 170 },
};

const EVIDENCE_STYLES: Record<string, { color: string; label: string; width: number; dashed: boolean }> = {
  assumed: { color: "var(--muted)", label: "Assumed", width: 1.5, dashed: true },
  observational: { color: "var(--accent)", label: "Observational", width: 2, dashed: false },
  data_supported: { color: "var(--success)", label: "Data-supported", width: 2.5, dashed: false },
  causally_validated: { color: "#7c3aed", label: "Causally validated", width: 3, dashed: false },
};

export default function CausalGraphPage() {
  const { business, loading: businessLoading } = useBusiness();
  const [graph, setGraph] = useState<CausalGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<CausalEdge | null>(null);

  useEffect(() => {
    if (!business) return;
    api
      .getCausalGraph(business.id)
      .then(setGraph)
      .catch(() => setGraph(null))
      .finally(() => setLoading(false));
  }, [business]);

  async function build() {
    if (!business) return;
    setBuilding(true);
    setError(null);
    try {
      const result = await api.buildCausalGraph(business.id);
      setGraph(result);
      setSelected(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not build the causal graph right now.");
    } finally {
      setBuilding(false);
      setLoading(false);
    }
  }

  if (!businessLoading && !business) {
    return (
      <div className="mx-auto max-w-xl px-6 py-24 text-center">
        <p className="text-muted">Set up your business first.</p>
        <div className="mt-4">
          <SecondaryLink href="/onboarding">Go to onboarding</SecondaryLink>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeader
          title="Dynamic Causal Graph"
          subtitle="Domain hypotheses about your business, upgraded to real evidence only where your data supports it."
        />
        <PrimaryButton onClick={build} disabled={building}>
          {building ? "Building…" : graph ? "Rebuild from latest data" : "Build graph"}
        </PrimaryButton>
      </div>
      {error ? <p className="mb-4 text-sm text-danger">{error}</p> : null}

      {loading ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : !graph ? (
        <EmptyState
          title="No causal graph yet"
          description="Build one from your uploaded data — edges start as domain hypotheses and are upgraded to real evidence only where your data statistically supports it."
        />
      ) : (
        <>
          <p className="mb-4 text-sm text-muted">
            {graph.evidence_summary} (version {graph.version})
          </p>

          <Card className="overflow-x-auto">
            <svg viewBox="0 0 1020 460" className="w-full min-w-[900px]" style={{ height: 460 }}>
              <defs>
                {Object.entries(EVIDENCE_STYLES).map(([key, style]) => (
                  <marker
                    key={key}
                    id={`arrow-${key}`}
                    viewBox="0 0 10 10"
                    refX="9"
                    refY="5"
                    markerWidth="7"
                    markerHeight="7"
                    orient="auto-start-reverse"
                  >
                    <path d="M0,0 L10,5 L0,10 z" fill={style.color} />
                  </marker>
                ))}
              </defs>

              {graph.edges.map((edge) => {
                const from = NODE_POSITIONS[edge.source_node];
                const to = NODE_POSITIONS[edge.target_node];
                if (!from || !to) return null;
                const style = EVIDENCE_STYLES[edge.evidence_type] ?? EVIDENCE_STYLES.assumed;
                const isSelected = selected?.source_node === edge.source_node && selected?.target_node === edge.target_node;
                return (
                  <line
                    key={`${edge.source_node}-${edge.target_node}`}
                    x1={from.x + 80}
                    y1={from.y + 16}
                    x2={to.x}
                    y2={to.y + 16}
                    stroke={style.color}
                    strokeWidth={isSelected ? style.width + 1.5 : style.width}
                    strokeDasharray={style.dashed ? "5 4" : undefined}
                    markerEnd={`url(#arrow-${edge.evidence_type})`}
                    className="cursor-pointer"
                    opacity={isSelected ? 1 : 0.85}
                    onClick={() => setSelected(edge)}
                  />
                );
              })}

              {Object.entries(NODE_POSITIONS).map(([node, pos]) => (
                <g key={node}>
                  <rect
                    x={pos.x}
                    y={pos.y}
                    width={160}
                    height={32}
                    rx={16}
                    fill="var(--surface)"
                    stroke="var(--border)"
                  />
                  <text
                    x={pos.x + 80}
                    y={pos.y + 20}
                    textAnchor="middle"
                    fontSize="11"
                    fill="var(--foreground)"
                    fontWeight={500}
                  >
                    {NODE_LABELS[node] ?? node}
                  </text>
                </g>
              ))}
            </svg>

            <div className="mt-4 flex flex-wrap gap-4 border-t border-border pt-4">
              {Object.entries(EVIDENCE_STYLES).map(([key, style]) => (
                <div key={key} className="flex items-center gap-2 text-xs text-muted">
                  <span
                    className="inline-block h-0.5 w-6"
                    style={{ backgroundColor: style.color, opacity: key === "assumed" ? 0.6 : 1 }}
                  />
                  {style.label}
                </div>
              ))}
            </div>
          </Card>

          <div className="mt-6">
            {selected ? (
              <Card>
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium text-foreground">
                    {NODE_LABELS[selected.source_node]} → {NODE_LABELS[selected.target_node]}
                  </h3>
                  <span
                    className="rounded-full px-3 py-1 text-xs font-medium"
                    style={{
                      color: (EVIDENCE_STYLES[selected.evidence_type] ?? EVIDENCE_STYLES.assumed).color,
                      backgroundColor: "var(--muted-surface)",
                    }}
                  >
                    {(EVIDENCE_STYLES[selected.evidence_type] ?? EVIDENCE_STYLES.assumed).label}
                  </span>
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <div>
                    <dt className="text-xs text-muted">Direction</dt>
                    <dd className="capitalize text-foreground">{selected.relationship}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Strength</dt>
                    <dd className="text-foreground">{selected.strength ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Confidence</dt>
                    <dd className="text-foreground">{selected.confidence ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Time lag</dt>
                    <dd className="text-foreground">{selected.time_lag !== null ? `${selected.time_lag} day(s)` : "—"}</dd>
                  </div>
                </dl>
                {selected.note ? <p className="mt-3 text-sm text-muted">{selected.note}</p> : null}
              </Card>
            ) : (
              <p className="text-sm text-muted">Click any edge in the diagram to see its evidence.</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
