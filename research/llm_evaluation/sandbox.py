"""Restricted execution of LLM-written pandas snippets for the LLM+data-tool baseline (protocol B2).

Defence in depth, not a security boundary: AST allow-list -> separate process -> timeout -> scrubbed
environment (no API keys) -> temp working directory -> output cap. Only the evaluation DataFrame is available.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ALLOWED_IMPORTS = {"pandas", "numpy", "datetime", "math", "calendar", "re", "collections", "statistics"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "globals", "locals", "vars",
                   "getattr", "setattr", "delattr", "memoryview", "exit", "quit"}
FORBIDDEN_ATTRS = {"to_csv", "to_excel", "to_pickle", "to_parquet", "to_json", "to_sql", "to_hdf", "to_feather", "to_clipboard",
                   "read_csv", "read_excel", "read_pickle", "read_parquet", "read_json", "read_sql", "read_html", "read_clipboard",
                   "system", "popen", "remove", "unlink", "rmdir", "mkdir", "environ"}
MAX_OUTPUT = 4000


class SandboxViolation(ValueError):
    pass


def check_code(code: str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise SandboxViolation(f"syntax error: {exc.msg} (line {exc.lineno})") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    raise SandboxViolation(f"import of '{a.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                raise SandboxViolation(f"import from '{node.module}' is not allowed")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise SandboxViolation(f"use of '{node.id}' is not allowed")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") or node.attr in FORBIDDEN_ATTRS:
                raise SandboxViolation(f"attribute '{node.attr}' is not allowed")


_RUNNER = r"""
import json, sys, math, datetime, calendar, re, collections, statistics
import pandas as pd, numpy as np
df = pd.read_csv(sys.argv[1], parse_dates=["date"])
ns = {"df": df, "pd": pd, "np": np, "math": math, "datetime": datetime, "calendar": calendar, "re": re,
      "collections": collections, "statistics": statistics}
code = open(sys.argv[2], encoding="utf-8").read()
try:
    exec(compile(code, "<llm_snippet>", "exec"), ns)
    if "result" not in ns:
        raise NameError("the snippet did not assign a variable named `result`")
    r = ns["result"]
    if isinstance(r, (pd.DataFrame, pd.Series)):
        r = r.head(25).to_string()
    elif hasattr(r, "item") and callable(r.item):
        try:
            r = r.item()
        except Exception:
            pass
    print(json.dumps({"ok": True, "result": str(r)}, ensure_ascii=False, default=str))
except Exception as exc:
    print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
"""


def run_code(code: str, df: pd.DataFrame, *, timeout: int = 60) -> dict:
    """Execute a snippet over `df`. Returns {'ok': bool, 'result'|'error': str}. Never raises."""
    try:
        check_code(code)
    except SandboxViolation as exc:
        return {"ok": False, "error": f"rejected before execution: {exc}"}
    with tempfile.TemporaryDirectory(prefix="llm_eval_sbx_") as tmp:
        tmpd = Path(tmp)
        data = tmpd / "data.csv"
        df.assign(date=df["date"].dt.strftime("%Y-%m-%d")).to_csv(data, index=False)
        (tmpd / "snippet.py").write_text(code, encoding="utf-8")
        (tmpd / "runner.py").write_text(_RUNNER, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP")}
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            proc = subprocess.run([sys.executable, "runner.py", "data.csv", "snippet.py"], cwd=tmp, env=env, capture_output=True,
                                  text=True, encoding="utf-8", timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"timed out after {timeout}s"}
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
        if not lines:
            return {"ok": False, "error": (proc.stderr or "no output")[-500:]}
        out = json.loads(lines[-1])
        if out.get("ok"):
            out["result"] = out["result"][:MAX_OUTPUT]
        return out
