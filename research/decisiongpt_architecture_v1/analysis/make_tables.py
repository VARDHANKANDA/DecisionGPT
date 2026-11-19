"""LaTeX tables and number macros for the paper, generated only from results/*.json.

    python research/decisiongpt_architecture_v1/analysis/make_tables.py

Writes overleaf/architecture_paper_v1/tables/{tab_rq2_contrasts,tab_rq4_cost,tab_family_r1}.tex and tables/numbers.tex (\\newcommand macros used by the text).
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
RES = REPO / "research" / "decisiongpt_architecture_v1" / "results"
TAB = REPO / "overleaf" / "architecture_paper_v1" / "tables"
TAB.mkdir(parents=True, exist_ok=True)

NAMES = {"B_vs_A": "B $-$ A", "C_vs_B": "C $-$ B", "D_vs_C": "D $-$ C", "D_vs_B": "D $-$ B", "D_vs_A": "D $-$ A", "D_vs_greedy": "D $-$ greedy$^*$", "D_vs_classical": "D $-$ classical$^*$", "D_vs_naive": "D $-$ naive"}
M: dict[str, str] = {}
PFX = {"r1": "RR", "upgraded_v1": "UU"}   # letters only: valid LaTeX macro names


def sg(x, d=3):
    return f"{x:+.{d}f}".replace("-", "$-$")


def pv(p):
    if p is None:
        return "--"
    if p < 1e-4:
        return "$<10^{-4}$"
    return f"{p:.3f}" if p >= 0.001 else f"{p:.4f}"


def macro(name, val):
    M[name] = ("$-$" + val[1:]) if val[:1] == "-" and val[1:2].isdigit() else val


def main():
    dq = json.loads((RES / "decision_quality.json").read_text(encoding="utf-8"))
    rows = []
    for key, lab in (("r1", "R1 locked (408 scenarios, 12 families)"), ("upgraded_v1", "Upgraded v1 locked (80 scenarios, 4 families)")):
        st = dq["studies"][key]
        rows.append([f"\\multicolumn{{6}}{{l}}{{\\emph{{{lab}}}}}"])
        for c in ("B_vs_A", "C_vs_B", "D_vs_C", "D_vs_B", "D_vs_A", "D_vs_greedy", "D_vs_classical", "D_vs_naive"):
            x = st["contrasts"][c]
            holm = x.get("holm_p_over_primary_four")
            rows.append([NAMES[c], sg(x["mean_diff_a_minus_b"]), f"[{sg(x['ci95'][0])}, {sg(x['ci95'][1])}]", pv(holm) if holm is not None else "(desc.)", sg(x["rank_biserial_a_vs_b"], 2), f"{x['a_better_(lower)']}/{x['ties']}/{x['a_worse_(higher)']}"])
            pre = PFX[key]
            tag = c.replace("_vs_", "")
            macro(f"{pre}{tag}", f"{x['mean_diff_a_minus_b']:+.3f}")
            macro(f"{pre}{tag}lo", f"{x['ci95'][0]:+.3f}")
            macro(f"{pre}{tag}hi", f"{x['ci95'][1]:+.3f}")
            macro(f"{pre}{tag}p", pv(x["wilcoxon_p"]))
            macro(f"{pre}{tag}holm", pv(holm) if holm is not None else "--")
            macro(f"{pre}{tag}W", str(x["a_better_(lower)"]))
            macro(f"{pre}{tag}T", str(x["ties"]))
            macro(f"{pre}{tag}L", str(x["a_worse_(higher)"]))
            macro(f"{pre}{tag}rb", f"{x['rank_biserial_a_vs_b']:+.2f}")
        for pol in ("A", "B", "C", "D", "greedy", "classical", "naive"):
            mm = st["mean_regret_by_policy"][pol]
            macro(f"{PFX[key]}mean{pol}", f"{mm['mean']:.3f}")
        macro(f"{PFX[key]}nsc", str(st["n_scenarios"]))
        # family counts
        bf = st["by_family"]
        worse = sum(1 for f in bf.values() if f["D_vs_B"]["ci95"][0] > 0)
        better = sum(1 for f in bf.values() if f["D_vs_B"]["ci95"][1] < 0)
        macro(f"{PFX[key]}famworse", str(worse))
        macro(f"{PFX[key]}fambetter", str(better))
        macro(f"{PFX[key]}famn", str(len(bf)))
    lines = [r"\begin{table*}[t]", r"\centering", r"\caption{RQ2/RQ3: paired scenario-level differences in normalised regret (first minus second; negative favours the first). Each row is the mean over scenarios of the "
             r"per-scenario mean over 10 seeds, with a 95\% percentile cluster-bootstrap interval over scenarios (10\,000 resamples), Holm-adjusted Wilcoxon $p$ over the four contrasts B$-$A, C$-$B, D$-$C, D$-$B "
             r"(other rows descriptive), matched-pairs rank-biserial effect (positive: first is higher/worse) and win/tie/loss counts for the first condition (lower regret = win). "
             r"$^*$Informed references: they see the ground-truth objective.}", r"\label{tab:rq2}", r"\footnotesize",
             r"\begin{tabular}{lccccc}", r"\toprule", r"Contrast & Mean diff. & 95\% CI & Holm $p$ & Rank-biserial & W/T/L \\", r"\midrule"]
    for r in rows:
        lines.append(r[0] + r" \\" if len(r) == 1 else " & ".join(r) + r" \\")
        if len(r) == 1 and "Upgraded" in r[0]:
            pass
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    (TAB / "tab_rq2_contrasts.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # family table (R1)
    bf = dq["studies"]["r1"]["by_family"]
    fam_rows = []
    for f in sorted(bf, key=lambda f: bf[f]["D_vs_B"]["mean_diff_a_minus_b"], reverse=True):
        d = bf[f]["D_vs_B"]
        fam_rows.append([f.replace("_", " "), sg(d["mean_diff_a_minus_b"]), f"[{sg(d['ci95'][0])}, {sg(d['ci95'][1])}]", f"{d['a_better_(lower)']}/{d['ties']}/{d['a_worse_(higher)']}"])
    lines = [r"\begin{table}[t]", r"\centering", r"\caption{Exploratory, no multiplicity control: D $-$ B regret by R1 scenario family (34 scenarios per family; cluster bootstrap over scenarios).}", r"\label{tab:family}", r"\footnotesize",
             r"\begin{tabular}{lccc}", r"\toprule", r"Family & D $-$ B & 95\% CI & W/T/L (D) \\", r"\midrule"] + [" & ".join(r) + r" \\" for r in fam_rows] + [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (TAB / "tab_family_r1.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


    # stored mechanism / robustness diagnostics of the locked R1 run (read-only)
    mech = json.loads((REPO / "experiments" / "r1" / "mechanism_results.json").read_text(encoding="utf-8"))
    a = mech["action_change_vs_improvement"]
    n = a["n"]
    macro("mechN", str(n))
    macro("mechChanged", str(a["D_changed_action_vs_B"]))
    macro("mechChangedPct", f"{100 * a['D_changed_action_vs_B'] / n:.0f}")
    macro("mechImproved", str(a["D_changed_and_improved"]))
    macro("mechWorsened", str(a["D_changed_and_worsened"]))
    o = mech["dt_vs_ground_truth_action_match"]
    macro("mechBoracle", f"{100 * o['B_action_eq_oracle'] / o['n']:.1f}")
    macro("mechDoracle", f"{100 * o['D_action_eq_oracle'] / o['n']:.1f}")
    rob = json.loads((REPO / "experiments" / "r1" / "robustness_results.json").read_text(encoding="utf-8"))
    macro("robRuns", f"{rob['n_runs']:,}".replace(",", "\\,"))
    macro("robTypes", str(len(rob["curves"])))
    macro("robErrors", str(rob["n_errors"]))
    macro("robChange", "did not change" if not rob["primary_conclusion_changes"] else "changed")

    sp = RES / "sensitivity.json"
    if sp.exists():
        sv = json.loads(sp.read_text(encoding="utf-8"))
        macro("fbInst", str(sv["fallback_instances"]))
        macro("fbPct", f"{100 * sv['fallback_instances'] / sv['n_instances']:.1f}")
        macro("fbScen", str(sv["scenarios_with_any_fallback"]))
        s1 = sv["S1_excluding_fallback_instances"]["D_vs_B"]
        macro("sOneDB", f"{s1['mean_diff']:+.3f}")
        macro("sOneDBlo", f"{s1['ci95'][0]:+.3f}")
        macro("sOneDBhi", f"{s1['ci95'][1]:+.3f}")
        s2 = sv["S2_first_seed_only"]["D_vs_B"]
        macro("sTwoDB", f"{s2['mean_diff']:+.3f}")
        macro("sTwoDBlo", f"{s2['ci95'][0]:+.3f}")
        macro("sTwoDBhi", f"{s2['ci95'][1]:+.3f}")
        macro("sTwoCBp", f"{sv['S2_first_seed_only']['C_vs_B']['wilcoxon_p']:.3f}")
        macro("sThreeMin", f"{sv['S3_summary']['min']:+.3f}")
        macro("sThreeMax", f"{sv['S3_summary']['max']:+.3f}")
        no = sv["S4_near_optimal_share"]
        for thr, tag in (("0.05", "Five"), ("0.1", "Ten"), ("0.2", "Twenty")):
            for k in ("A", "B", "C", "D"):
                macro(f"near{tag}{k}", f"{no[thr][k]:.2f}")

    rp = RES / "rq1_summary.json"
    if rp.exists():
        rq = json.loads(rp.read_text(encoding="utf-8"))
        ft = rq["f1"]["test"]
        macro("mfiveCat", f"{ft['catboost:depth6']['wape']:.3f}")
        macro("mfiveSN", f"{ft['baseline:seasonal_naive_28']['wape']:.3f}")
        macro("mfiveWD", f"{ft['baseline:same_weekday_mean4']['wape']:.3f}")
        macro("mfiveLin", f"{ft['linear:ols']['wape']:.3f}")
        macro("mfiveXgb", f"{ft['xgboost:depth6']['wape']:.3f}")
        macro("mfiveCatAgg", f"{ft['catboost:depth6']['aggregate_daily_wape']:.3f}")
        macro("mfiveWDAgg", f"{ft['baseline:same_weekday_mean4']['aggregate_daily_wape']:.3f}")
        macro("mfiveXgbAgg", f"{ft['xgboost:depth6']['aggregate_daily_wape']:.3f}")
        d = rq["f1"]["catboost_vs_seasonal_naive"]
        macro("mfiveDiff", f"{d['diff']:+.3f}")
        macro("mfiveDifflo", f"{d['ci95'][0]:+.3f}")
        macro("mfiveDiffhi", f"{d['ci95'][1]:+.3f}")
        macro("mfiveN", f"{rq['f1']['n_points']:,}".replace(",", "\\,"))
        f2 = rq["f2b"]["test"]
        macro("retLgbm", f"{f2['lightgbm:tweedie']['wape']:.3f}")
        macro("retSN", f"{f2['baseline:seasonal_naive']['wape']:.3f}")
        macro("retCat", f"{f2['catboost:depth8']['wape']:.3f}")
        ch = rq["churn"]
        rfm = ch["c1"]["random_forest"]
        macro("chRFauc", f"{rfm['roc_auc']:.3f}")
        macro("chLRauc", f"{ch['c1']['logistic_regression']['roc_auc']:.3f}")
        macro("chRFece", f"{rfm['ece']:.3f}")
        macro("chBrierBase", f"{ch['c1_brier_prevalence_baseline']:.3f}")
        macro("chRFbrier", f"{rfm['brier']:.3f}")
        reg = {(r["model"], r["version"]): r for r in rq["registry_rescoring"]}
        macro("regXgbWape", f"{reg[('sales_forecast_xgboost', 'v1')]['wape']:.3f}")
        macro("regBaseWape", f"{reg[('sales_forecast_xgboost', 'v1')]['baseline_wape']:.3f}")
        macro("regXgbImp", f"{reg[('sales_forecast_xgboost', 'v1')]['improvement']['wape_pct']:.0f}")
        macro("regLinImp", f"{reg[('sales_forecast_linear', 'v1')]['improvement']['wape_pct']:.0f}")
    cp = RES / "cost_summary.json"
    if cp.exists():
        cs = json.loads(cp.read_text(encoding="utf-8"))
        e = cs["end_to_end_seconds"]
        cnt = cs["counts_per_decision"]
        qc = cs["quality_cost"]["policies"]
        no = cs["near_optimal"]["0.1"]

        def sec(d):
            return f"{d['median']:.2f} [{d['iqr'][0]:.2f}, {d['iqr'][1]:.2f}]"

        def med(k):
            return f"{cnt[k]['median']:.0f}"
        rows = [["A", "0", "0", "0", "0", "0", f"{qc['A']['mean_regret']:.3f}", f"{no['A']['share_near_optimal']:.2f}", "--"],
                ["B", sec(e["B"]), f"{e['B']['p95']:.2f}", med("sim_calls_shared_(B,C)"), med("forecast_model_runs_shared_(B,C)"), "0", f"{qc['B']['mean_regret']:.3f}", f"{no['B']['share_near_optimal']:.2f}", f"{no['B']['seconds_per_near_optimal_decision']:.1f}"],
                ["C", sec(e["C"]), f"{e['C']['p95']:.2f}", med("sim_calls_shared_(B,C)"), med("forecast_model_runs_shared_(B,C)"), med("agent_single_C_pick"), f"{qc['C']['mean_regret']:.3f}", f"{no['C']['share_near_optimal']:.2f}", f"{no['C']['seconds_per_near_optimal_decision']:.1f}"],
                ["D", sec(e["D"]), f"{e['D']['p95']:.2f}", med("sim_calls_D"), med("forecast_model_runs_D"), f"{cnt['agent_BA_D']['median'] + cnt['agent_FA_D']['median'] + cnt['agent_RM_D']['median']:.0f}", f"{qc['D']['mean_regret']:.3f}", f"{no['D']['share_near_optimal']:.2f}", f"{no['D']['seconds_per_near_optimal_decision']:.1f}"]]
        lines = [r"\begin{table*}[t]", r"\centering", r"\caption{RQ4: measured cost per decision on the 408 locked R1 scenarios (first locked seed; scratch in-memory database; one machine). End-to-end: B = shared simulation + selection, "
                 r"C = shared simulation + one-agent selection, D = full pipeline. A recommends nothing and has no decision cost. Model requests (language model) are 0 for every workflow. Time: median [IQR] and 95th percentile (seconds). "
                 r"Regret and the near-optimal share (regret $\le0.10$) are from the stored locked run (mean over its 10 seeds) for the same scenarios; the last column divides mean end-to-end seconds by the near-optimal share (compute seconds, not money).}",
                 r"\label{tab:cost}", r"\footnotesize", r"\begin{tabular}{lcccccccc}", r"\toprule",
                 r"Workflow & Seconds & p95 & Sim.\ calls & Forecast runs & Agent evals & Mean regret & Near-opt.\ share & s / near-opt.\ decision \\", r"\midrule"] + [" & ".join(r) + r" \\" for r in rows] + [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
        (TAB / "tab_rq4_cost.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
        for k in ("B", "C", "D"):
            macro(f"sec{k}", f"{e[k]['median']:.2f}")
            macro(f"secp{k}", f"{e[k]['p95']:.2f}")
        r_ = cs["ratios"]
        macro("ratioDB", f"{r_['D_over_B']['median_ratio']:.2f}")
        macro("ratioDBlo", f"{r_['D_over_B']['ci95'][0]:.2f}")
        macro("ratioDBhi", f"{r_['D_over_B']['ci95'][1]:.2f}")
        macro("ratioCB", f"{r_['C_over_B']['median_ratio']:.3f}")
        macro("nCost", str(cs["n_main"]))
        macro("ovhD", f"{cs['components_seconds']['D_overhead']['median']:.2f}")
        macro("ovhShare", f"{100 * cs['D_orchestration_overhead_share_of_D']['median']:.0f}")
        macro("detmatch", f"{cs['determinism_matches_stored']['match']}")
        macro("detchecked", f"{cs['determinism_matches_stored']['checked']}")
        macro("costerrors", str(cs["n_errors"]))
        macro("simcallsD", med("sim_calls_D"))
        macro("fcrunsD", med("forecast_model_runs_D"))
        macro("agentevalsD", f"{cnt['agent_BA_D']['median'] + cnt['agent_FA_D']['median'] + cnt['agent_RM_D']['median']:.0f}")
        rr = cs["rerun_on_new_date"]
        macro("rerunDB", f"{rr['contrasts']['D_vs_B']['new_run_mean']:+.3f}")
        macro("rerunDBlo", f"{rr['contrasts']['D_vs_B']['new_run_ci95'][0]:+.3f}")
        macro("rerunDBhi", f"{rr['contrasts']['D_vs_B']['new_run_ci95'][1]:+.3f}")
        macro("rerunDBstored", f"{rr['contrasts']['D_vs_B']['stored_first_seed_mean']:+.3f}")
        macro("rerunDiffD", str(rr["conditions_differing"]["D"]))
        macro("rerunDiffABC", str(rr["conditions_differing"]["A"] + rr["conditions_differing"]["B"] + rr["conditions_differing"]["C"]))
        macro("cvMedD", f"{100 * cs['repeat_cv']['D']['median']:.0f}")
        macro("cvMedB", f"{100 * cs['repeat_cv']['B']['median']:.0f}")
        macro("repN", str(cs["n_scenarios_with_3_repeats"]))
        macro("ratioRep", f"{cs['D_over_B_repeat_median_by_scenario']['median']:.2f}")
        macro("ratioRepIqrLo", f"{cs['D_over_B_repeat_median_by_scenario']['iqr'][0]:.2f}")
        macro("ratioRepIqrHi", f"{cs['D_over_B_repeat_median_by_scenario']['iqr'][1]:.2f}")
        macro("shareDslower", f"{100 * cs['ratios']['D_over_B']['share_D_slower']:.0f}")
        macro("detmismatch", str(cs["determinism_matches_stored"]["mismatch"]))
        macro("detmismatchPct", f"{100 * cs['determinism_matches_stored']['mismatch'] / cs['determinism_matches_stored']['checked']:.1f}")
        macro("domD", "dominated" if cs["quality_cost"]["policies"]["D"]["dominated"] else "not dominated")
        macro("llmreq", str(max(cnt["llm_network_requests_attempted_all"]["max"], 0)))
    out = ["% generated by analysis/make_tables.py -- do not edit"] + [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(M.items())]
    (TAB / "numbers.tex").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(len(M), "macros;", sorted(p.name for p in TAB.glob("*.tex")))


if __name__ == "__main__":
    main()
