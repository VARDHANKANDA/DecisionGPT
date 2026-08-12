"""SHAP-based global feature importance — docs/AI_MODULE_SPECIFICATION.md §7.

Computed offline, inside a training script, against real held-out platform
data. This must never run inside the runtime app: ml/pipeline/loaders.py's
platform datasets are explicitly off-limits to SME-facing code (AGENTS.md
"Data isolation"). The training script calls this once, and only the
resulting aggregate importance values (never a single raw training row)
get written into the model's metrics — see ml/pipeline/registry.py — which
is what the runtime app reads at request time via the model registry.

Only tree ensembles are supported (shap.TreeExplainer needs no background
data and is fast enough to run per training run); linear/naive models are
the caller's responsibility to skip.
"""
import numpy as np
import pandas as pd
import shap


def tree_shap_global_importance(model, X_sample: pd.DataFrame) -> dict[str, float]:
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)
    mean_abs = np.abs(shap_values).mean(axis=0)
    return {col: round(float(v), 6) for col, v in zip(X_sample.columns, mean_abs)}
