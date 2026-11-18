"""ARCHITECTURE DRY-RUN of the Jev analytics path with a MOCKED Jev.   *** NOT RESEARCH RESULTS ***

What this shows: the 27 frozen questions can technically flow through
    question -> (mock) Jev typed decisions + deterministic extraction -> strict structured request -> validated query engine -> answer
using the real production route (POST /businesses/{id}/chat), the real ingestion of the evaluation view, the real query engine and the
real answer assembly. The mock "Jev" returns, for each question, the typed decisions a competent classifier would give in the closed
vocabulary of app.services.analytics_interpreter_service; periods, products and limits are extracted by production code from the question
text. It is given NO numbers and never sees the ground truth; every number in every answer comes from the deterministic engine. The engine
output is then compared with the independent pandas ground-truth engine ONLY to detect bugs in the engine / extractor. The real model may
classify differently (and will be measured separately, later); nothing here says how well Jev does, and nothing here may be reported as an
accuracy, latency or cost result.

    python -m research.llm_evaluation.audit.llm_path_dryrun        # writes audit/llm_path_dryrun.json
"""
from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from research.llm_evaluation.data_view import build_view
from research.llm_evaluation.ground_truth import compute_all
from research.llm_evaluation.llm_instrument import LLMRecorder
from research.llm_evaluation.scoring import score_answer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SPEC_PATH = ROOT / "research" / "llm_evaluation" / "tasks" / "tasks_v1.json"
OUT = HERE / "llm_path_dryrun.json"
ASOF = date(2025, 3, 31)

from research.llm_evaluation.mock_llm import INTERPRETATIONS  # noqa: E402  (shared with the mock readiness run)


class ScriptedLLM:
    """Stand-in for LLMService. ``decide`` returns the typed decisions the scripted interpretation implies, validated by the real
    response parser, so the mock cannot drift from the strict schema the client sends."""

    enabled = True

    def __init__(self, by_question: dict[str, dict]):
        self.by_question = by_question
        self.n_interpret = 0

    def decide(self, state, questions):
        from app.services.openai_client import DecisionResult, parse_answers
        from research.llm_evaluation.mock_llm import _openai_object, _typed_answers

        self.n_interpret += 1
        wire = {k: q.payload() for k, q in questions.items()}
        answers = parse_answers(_openai_object(_typed_answers(self.by_question[state], wire, None)), questions)
        return DecisionResult(True, answers, None, 0.0, "openai", "mock-openai", "mock-openai", None, 1)


def main() -> int:
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    from app.services import analytics_chat_service

    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    view, _ = build_view()
    truth = compute_all(spec, view)
    products = set(view["product"].unique())
    script = ScriptedLLM({t["natural_language_question"]: INTERPRETATIONS[t["task_id"]] for t in spec["tasks"]})

    from research.llm_evaluation.systems.decisiongpt import DecisionGPTSystem

    run_dir = Path(tempfile.mkdtemp(prefix="llm_path_dryrun_"))
    sysm = DecisionGPTSystem(run_dir, LLMRecorder())
    rows = []
    try:
        ingestion = sysm.setup(view)
        original = analytics_chat_service.get_llm
        analytics_chat_service.get_llm = lambda: script
        sysm.set_clock(ASOF)
        try:
            for t in spec["tasks"]:
                out = sysm.ask(t["natural_language_question"])
                tr = truth["answers"][t["task_id"]]["answer"]
                sc = score_answer(t, tr, out.get("answer"), system_error=out.get("error"), view_products=products)
                rows.append({"task_id": t["task_id"], "track": t["track"], "path": out.get("path"), "intent": out.get("intent"),
                             "flowed_through_llm_path": out.get("path") == "llm_analytics",
                             "engine_answered": out.get("intent") == "analytics_query" and bool(out.get("sufficient_evidence")),
                             "refused_as_unsupported": out.get("intent") == "analytics_unsupported",
                             "engine_matches_ground_truth_engine": bool(sc.get("correct")) if isinstance(sc, dict) else None,
                             "answer": out.get("answer")})
        finally:
            analytics_chat_service.get_llm = original
            sysm.set_clock(None)
    finally:
        sysm.teardown()

    prim = [r for r in rows if r["track"] == "primary"]
    supp = [r for r in rows if r["track"] == "supplementary"]
    summary = {
        "BANNER": "ARCHITECTURE DRY-RUN WITH A MOCKED PROVIDER - NOT RESEARCH RESULTS. No real model was called; no accuracy/latency/cost is claimed.",
        "research_result": False,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation_clock": ASOF.isoformat(),
        "frozen_spec_modified": False,
        "n_tasks": len(rows),
        "flowed_through_llm_analytics_path": sum(r["flowed_through_llm_path"] for r in rows),
        "primary": {"n": len(prim), "engine_produced_a_verified_answer": sum(r["engine_answered"] for r in prim),
                    "engine_matches_independent_ground_truth_engine": sum(bool(r["engine_matches_ground_truth_engine"]) for r in prim)},
        "supplementary_gst": {"n": len(supp), "correctly_refused_as_unsupported": sum(r["refused_as_unsupported"] for r in supp),
                              "note": "production data has no GST field; refusing is the correct production behaviour, not an answer"},
        "mock_llm_calls": {"interpreter": script.n_interpret},
        "ingestion_matches_view": ingestion.get("matches_view"),
        "tasks": rows,
    }
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"wrote {OUT}")
    print({k: v for k, v in summary.items() if k != "tasks"})
    for r in rows:
        flag = "ok " if (r["engine_matches_ground_truth_engine"] or r["refused_as_unsupported"]) else "?? "
        print(flag, r["task_id"], r["path"], r["intent"], "|", (r["answer"] or "")[:110].replace("\n", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
