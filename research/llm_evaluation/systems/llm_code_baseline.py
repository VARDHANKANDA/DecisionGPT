"""Protocol B2 baseline: the SAME configured LLM client + read-only access to the SAME data view via a sandboxed pandas snippet.

No DecisionGPT routing, analytics services or templates are involved. Per question: (1) the model writes a pandas snippet
(<=1 repair attempt on failure), (2) the snippet runs in the sandbox on the view, (3) the model phrases the executed result.
The baseline is never shown the ground truth, task metadata, or tolerances.
"""
from __future__ import annotations

import re
import time

import pandas as pd

from research.llm_evaluation import prompts
from research.llm_evaluation.llm_instrument import LLMRecorder, summarize_calls
from research.llm_evaluation.sandbox import run_code

_BLOCK = re.compile(r"```(?:python)?\s*(.*?)```", re.S | re.I)


def extract_code(text: str) -> str | None:
    m = _BLOCK.search(text or "")
    if m:
        return m.group(1).strip()
    t = (text or "").strip()
    return t if "result" in t and "=" in t else None


class LLMCodeBaseline:
    name = "llm_code_baseline"

    def __init__(self, recorder: LLMRecorder):
        self.recorder = recorder
        self._view: pd.DataFrame | None = None

    def setup(self, view: pd.DataFrame) -> dict:
        # This reference system asks the model to WRITE a pandas snippet and then to phrase the result. It is not implemented for the
# OpenAI provider in this version and is never replaced by another provider behind the scenes.
        raise RuntimeError(
            "llm_code_baseline (a model writing pandas code) is not implemented for this provider, so this reference system was not run. "
            "It is not executed and no other provider is used."
        )
        self._view = view
        return {"columns_default": ["date", "product", "quantity", "unit_price", "revenue"], "prompt_version": prompts.PROMPT_VERSION}

    def teardown(self) -> None:
        pass

    def _frame_for(self, task: dict) -> tuple[pd.DataFrame, list[str]]:
        cols = ["date", "product", "quantity", "unit_price", "revenue"]
        if "gst_pct" in task["required_fields"]:  # supplementary track only
            cols.append("gst_pct")
        return self._view[cols], cols

    def ask(self, task: dict) -> dict:  # pragma: no cover - unreachable: setup() refuses
        question = task["natural_language_question"]
        df, cols = self._frame_for(task)
        schema = prompts.schema_description(cols, str(df["date"].min().date()), str(df["date"].max().date()), df.head(5).to_csv(index=False))
        mark = self.recorder.mark()
        t0 = time.perf_counter()
        out: dict = {"system": self.name, "question": question, "columns": cols}
        try:
            raw = self._client.complete(prompts.CODE_SYSTEM, prompts.code_user(schema, question), max_tokens=900)
            code = extract_code(raw)
            out["code_attempts"] = []
            exec_result = {"ok": False, "error": "model returned no code block"}
            if code:
                exec_result = run_code(code, df)
                out["code_attempts"].append({"code": code, **exec_result})
                if not exec_result["ok"]:  # single pre-registered repair attempt
                    raw2 = self._client.complete(prompts.CODE_SYSTEM, prompts.repair_user(schema, question, code, exec_result["error"]), max_tokens=900)
                    code2 = extract_code(raw2)
                    if code2:
                        exec_result = run_code(code2, df)
                        out["code_attempts"].append({"code": code2, **exec_result})
            result_text = exec_result.get("result") if exec_result.get("ok") else f"The calculation failed: {exec_result.get('error')}"
            out["executed_result"] = result_text
            out["answer"] = self._client.complete(prompts.ANSWER_SYSTEM, prompts.answer_user(question, result_text), max_tokens=300)
            out["tool_ok"] = bool(exec_result.get("ok"))
        except Exception as exc:  # noqa: BLE001 - provider/API errors are recorded as failures, never hidden
            out["error"] = f"{type(exc).__name__}: {exc}"[:300]
        latency = time.perf_counter() - t0
        calls = self.recorder.since(mark)
        out.update(latency_s=latency, llm_calls=calls, llm_summary=summarize_calls(calls))
        return out
