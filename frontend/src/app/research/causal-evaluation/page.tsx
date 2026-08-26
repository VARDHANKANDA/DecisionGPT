"use client";

import { useEffect, useState } from "react";
import { researchApi, type CausalEvaluation } from "@/lib/research-api";
import {
  DataTable,
  EvalEmptyState,
  EvidenceBadge,
  Metric,
  Panel,
  PageIntro,
  StatGrid,
  fmt,
  fmtInt,
} from "@/components/research-ui";

export default function CausalEvaluationPage() {
  const [data, setData] = useState<CausalEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    researchApi.causalEvaluation().then(setData).catch((e) => setError(String(e?.message ?? e)));
  }, []);

  return (
    <div>
      <PageIntro
        title="Causal Graph Evaluation"
        subtitle="Real stored causal-graph data (versions, nodes, edges, evidence levels), the synthetic method-validation experiment (Granger recovery against a known ground truth), and the conservative outcome-feedback log. No ground-truth causal graph exists for any real business, so business-graph recovery accuracy is not reported."
      />

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {!data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : data.empty_state ? (
        <EvalEmptyState message={data.empty_state} />
      ) : (
        <div className="space-y-6">
          <StatGrid>
            <Metric label="Graph versions (all)" value={fmtInt(data.overview.total_graph_versions)} />
            <Metric label="Businesses with a graph" value={fmtInt(data.overview.businesses_with_a_graph)} />
            <Metric
              label="Data-supported edges"
              value={fmtInt(data.overview.evidence_counts_latest_per_business.data_supported ?? 0)}
              hint="latest graph per business"
            />
            <Metric
              label="Causally-validated edges"
              value={fmtInt(data.overview.evidence_counts_latest_per_business.causally_validated ?? 0)}
              hint="never assigned automatically"
            />
          </StatGrid>

          <Panel title="Evidence-level distribution (latest graph per business)">
            <div className="flex flex-wrap gap-4 text-sm">
              {(["assumed", "observational", "data_supported", "causally_validated"] as const).map((lvl) => (
                <div key={lvl} className="flex items-center gap-2">
                  <EvidenceBadge level={lvl} />
                  <span className="font-medium text-foreground">
                    {fmtInt(data.overview.evidence_counts_latest_per_business[lvl] ?? 0)}
                  </span>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Stored causal graphs">
            {data.graphs.map((g) => (
              <div key={g.graph_id} className="mb-4 rounded-xl border border-border p-4 last:mb-0">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-foreground">
                    Business {g.business_id.slice(0, 8)} · {g.version}
                  </p>
                  <p className="text-xs text-muted">
                    {g.node_count} nodes · {g.edge_count} edges · {g.method}
                  </p>
                </div>
                <div className="mt-3 overflow-x-auto">
                  <DataTable
                    headers={["Source", "→ Target", "Direction", "Evidence", "Strength", "Confidence", "Lag"]}
                    rows={g.edges.map((e) => [
                      e.source,
                      e.target,
                      e.relationship,
                      <EvidenceBadge key={e.source + e.target} level={e.evidence_type} />,
                      e.strength != null ? fmt(e.strength) : "—",
                      e.confidence != null ? fmt(e.confidence) : "—",
                      e.time_lag ?? "—",
                    ])}
                  />
                </div>
              </div>
            ))}
          </Panel>

          <Panel title="Method validation (synthetic ground truth)">
            {!data.method_validation ? (
              <p className="text-sm text-muted">
                No causal-recovery experiment has been run. Run one from Experiments (type &quot;causal&quot;).
              </p>
            ) : (
              <>
                <p className="mb-3 text-xs text-muted">
                  Experiment {data.method_validation.experiment_id.slice(0, 8)} · seed {data.method_validation.seed} ·{" "}
                  <span className="font-medium text-foreground">{data.method_validation.label}</span> — validates the
                  Granger method against a KNOWN A→B→C structure, not any business&apos;s graph.
                </p>
                <StatGrid>
                  <Metric label="Precision" value={fmt(data.method_validation.precision)} />
                  <Metric label="Recall" value={fmt(data.method_validation.recall)} />
                  <Metric label="F1" value={fmt(data.method_validation.f1)} />
                  <Metric label="SHD" value={fmtInt(data.method_validation.structural_hamming_distance)} />
                </StatGrid>
                <div className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
                  <EdgeList title="Recovered" edges={data.method_validation.recovered_edges} tone="text-success" />
                  <EdgeList title="Missing" edges={data.method_validation.missing_edges} tone="text-danger" />
                  <EdgeList title="Extra" edges={data.method_validation.extra_edges} tone="text-warning" />
                </div>
              </>
            )}
          </Panel>

          <Panel title="Ground-truth comparison">
            <p className="text-sm text-muted">{data.ground_truth_comparison.message}</p>
          </Panel>

          <Panel title="Outcome-feedback evidence updates">
            {data.evidence_feedback_log.length === 0 ? (
              <p className="text-sm text-muted">
                No edges have been updated from real outcomes yet. Edges are only lifted ASSUMED → OBSERVATIONAL
                after ≥3 recorded interventions moved the outcome in the predicted direction — and never further.
              </p>
            ) : (
              <DataTable
                headers={["Edge", "Change", "Graph ver.", "n", "Consistent", "Method", "When"]}
                rows={data.evidence_feedback_log.map((u) => [
                  u.edge,
                  <span key={u.id}>
                    <EvidenceBadge level={u.previous_evidence} /> → <EvidenceBadge level={u.new_evidence} />
                  </span>,
                  u.graph_version,
                  u.sample_size,
                  u.consistent_direction_count,
                  u.method,
                  u.created_at ? new Date(u.created_at).toLocaleDateString() : "—",
                ])}
              />
            )}
          </Panel>
        </div>
      )}
    </div>
  );
}

function EdgeList({ title, edges, tone }: { title: string; edges: string[][]; tone: string }) {
  return (
    <div className="rounded-xl border border-border p-3">
      <p className={`text-xs font-medium ${tone}`}>
        {title} ({edges.length})
      </p>
      <ul className="mt-1 space-y-0.5 text-xs text-muted">
        {edges.length === 0 ? <li>—</li> : edges.map((e, i) => <li key={i}>{e.join(" → ")}</li>)}
      </ul>
    </div>
  );
}
