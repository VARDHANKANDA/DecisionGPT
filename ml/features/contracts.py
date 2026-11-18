"""Feature contracts: the exact columns (names, order, numeric type) a model was trained on, checked again at inference.

A contract is derived from the SAME constant the training feature builder exposes, so training and serving cannot drift apart silently;
``validate`` fails loudly (never fills or reorders silently) when an inference frame does not match. The contract's name and version are
stored in the run metadata next to every model.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ml.features.churn_features import FEATURE_COLUMNS as CHURN_COLUMNS
from ml.features.forecasting_features import FEATURE_COLUMNS as FORECAST_COLUMNS


class FeatureContractError(ValueError):
    """The inference frame does not satisfy the model's feature contract. ``problems`` lists every violation."""

    def __init__(self, contract: str, problems: list[str]):
        super().__init__(f"feature contract {contract!r} violated: " + "; ".join(problems))
        self.contract = contract
        self.problems = problems


@dataclass(frozen=True)
class FeatureContract:
    name: str
    version: str
    columns: tuple[str, ...]
    allow_missing: frozenset[str] = field(default_factory=frozenset)

    def describe(self) -> dict:
        return {"name": self.name, "version": self.version, "columns": list(self.columns)}

    def validate(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Returns ``frame[columns]`` when it satisfies the contract, otherwise raises ``FeatureContractError`` (all problems at once)."""
        problems: list[str] = []
        missing = [c for c in self.columns if c not in frame.columns]
        if missing:
            problems.append(f"missing columns {missing}")
        extra = [c for c in frame.columns if c not in self.columns]
        if extra:
            problems.append(f"unexpected columns {extra}")
        if not missing:
            if list(frame.columns) != list(self.columns):
                problems.append("column order differs from training")
            for c in self.columns:
                col = frame[c]
                if not pd.api.types.is_numeric_dtype(col):
                    problems.append(f"column {c!r} is not numeric ({col.dtype})")
                    continue
                n_bad = int(col.isna().sum()) if c not in self.allow_missing else 0
                if n_bad:
                    problems.append(f"column {c!r} has {n_bad} missing value(s)")
                if (col.astype(float).abs() == float("inf")).any():
                    problems.append(f"column {c!r} has infinite values")
            if len(frame) == 0:
                problems.append("no rows")
        if problems:
            raise FeatureContractError(self.name, problems)
        return frame[list(self.columns)]


FORECASTING_V1 = FeatureContract("forecasting", "forecasting_v1", tuple(FORECAST_COLUMNS))
CHURN_V1 = FeatureContract("churn", "churn_v1", tuple(CHURN_COLUMNS))

CONTRACTS = {"forecasting_v1": FORECASTING_V1, "churn_v1": CHURN_V1}


def contract_for(feature_version: str) -> FeatureContract | None:
    return CONTRACTS.get(feature_version)
