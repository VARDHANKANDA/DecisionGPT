"""The actual DecisionGPT production path, driven through its real HTTP routes.

An isolated SQLite database is created under the run directory; a business is created with
POST /businesses; the evaluation data view is uploaded through the production upload endpoint
(products first, then sales) exactly as a user would; each question goes to POST /businesses/{id}/chat.
No production code is modified. The only evaluation-environment setting is an OPTIONAL fixed reference date, applied through
the production clock abstraction (``app.core.clock.reference_date``), because relative dates ("this month", "last 30 days") resolve
against the clock; production itself always uses the real date.
"""
from __future__ import annotations

import io
import time
from datetime import date
from pathlib import Path

import pandas as pd

from app.core import clock
from research.llm_evaluation.llm_instrument import LLMRecorder, summarize_calls


def products_csv(view: pd.DataFrame) -> bytes:
    """One row per product; selling_price (required by the canonical schema) = the modal observed unit price (derived, documented)."""
    mode = view.groupby("product")["unit_price"].agg(lambda s: s.mode().min())
    df = pd.DataFrame({"external_product_id": mode.index, "name": mode.index, "selling_price": mode.values})
    return df.to_csv(index=False).encode()


def sales_csv(view: pd.DataFrame) -> bytes:
    df = pd.DataFrame(
        {
            "sale_date": view["date"].dt.strftime("%Y-%m-%d"),
            "external_product_id": view["product"],
            "quantity": view["quantity"],
            "unit_price": view["unit_price"],
        }
    )
    return df.to_csv(index=False).encode()


class DecisionGPTSystem:
    name = "decisiongpt"

    def __init__(self, run_dir: Path, recorder: LLMRecorder):
        self.run_dir = Path(run_dir)
        self.recorder = recorder
        self.asof: date | None = None
        self.client = None
        self.business_id: str | None = None
        self.ingestion: dict = {}
        self._clock_cm = None

    # ------------------------------------------------------------------ setup / teardown
    def setup(self, view: pd.DataFrame) -> dict:
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        import app.models  # noqa: F401  (populate metadata)
        from app.core.config import get_settings
        from app.db.session import Base, get_db
        from app.main import app as fastapi_app

        get_settings().auth_enabled = False  # process-local: evaluation talks to an isolated DB
        self.run_dir.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{(self.run_dir / 'eval_decisiongpt.db').as_posix()}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        self._engine = engine
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        self._Session = Session

        def _get_db():
            db = Session()
            try:
                yield db
            finally:
                db.close()

        fastapi_app.dependency_overrides[get_db] = _get_db
        self._app, self._get_db = fastapi_app, get_db
        self.client = TestClient(fastapi_app)

        r = self.client.post("/api/v1/businesses", json={"name": "POS evaluation store", "industry": "retail",
                                                         "business_type": "retail", "business_size": "small"})
        r.raise_for_status()
        self.business_id = r.json()["id"]

        up = {}
        for label, payload, hint in (("products", products_csv(view), "products"), ("sales", sales_csv(view), "sales")):
            resp = self.client.post(f"/api/v1/businesses/{self.business_id}/data/upload", params={"data_type": hint},
                                    files={"file": (f"{label}.csv", io.BytesIO(payload), "text/csv")})
            resp.raise_for_status()
            job = resp.json()
            up[label] = {"status": job["status"], "rows_ingested": (job.get("summary_json") or {}).get("rows_ingested"),
                         "error": job.get("error_message")}
            if job["status"] != "completed":
                raise RuntimeError(f"production ingestion of {label} did not complete: {up[label]}")
        # verify the stored data equals the evaluation view (otherwise the ground truth would not describe what the system holds)
        from sqlalchemy import func

        from app.models.sale import Sale

        with Session() as db:
            n, qty, rev = db.query(func.count(Sale.id), func.sum(Sale.quantity), func.sum(Sale.revenue)).filter(Sale.business_id == self.business_id).one()
        self.ingestion = {"uploads": up, "stored_sales_rows": int(n), "stored_units": int(qty), "stored_revenue": round(float(rev), 2),
                          "view_rows": int(len(view)), "view_units": int(view["quantity"].sum()), "view_revenue": round(float(view["revenue"].sum()), 2)}
        self.ingestion["matches_view"] = (self.ingestion["stored_sales_rows"] == self.ingestion["view_rows"]
                                          and self.ingestion["stored_units"] == self.ingestion["view_units"]
                                          and abs(self.ingestion["stored_revenue"] - self.ingestion["view_revenue"]) < 0.5)
        if not self.ingestion["matches_view"]:
            raise RuntimeError(f"stored data differs from the evaluation view: {self.ingestion}")

        return self.ingestion

    def set_clock(self, asof: date | None) -> None:
        """Evaluation-environment setting: pin the production analytics clock (``app.core.clock``) to ``asof`` for subsequent
        questions, or restore the real clock. Scoped (a ContextVar), never a process-wide patch of ``datetime.date``."""
        self._restore_clock()
        if asof is not None:
            self._clock_cm = clock.reference_date(asof)
            self._clock_cm.__enter__()
        self.asof = asof

    def _restore_clock(self) -> None:
        if self._clock_cm is not None:
            self._clock_cm.__exit__(None, None, None)
            self._clock_cm = None
        self.asof = None

    def teardown(self) -> None:
        self._restore_clock()
        if getattr(self, "_app", None) is not None:
            self._app.dependency_overrides.pop(self._get_db, None)
        if getattr(self, "_engine", None) is not None:
            self._engine.dispose()

    # ------------------------------------------------------------------ audit trail of the last question
    def last_audit(self) -> dict | None:
        """The production audit record (``analytics_audit``) stored with the most recent chat row of this evaluation business,
        or None. Read-only; this is how the runner learns stage timings, the validation verdict and the fallback reason."""
        from app.models.memory import BusinessMemory

        with self._Session() as db:
            row = (db.query(BusinessMemory)
                   .filter(BusinessMemory.business_id == self.business_id, BusinessMemory.memory_type == "chat")
                   .order_by(BusinessMemory.created_at.desc()).first())
            md = (row.metadata_json or {}) if row is not None else {}
            return md.get("analytics_audit")

    # ------------------------------------------------------------------ one question
    def ask(self, question: str) -> dict:
        mark = self.recorder.mark()
        t0 = time.perf_counter()
        out: dict = {"system": self.name, "question": question}
        try:
            r = self.client.post(f"/api/v1/businesses/{self.business_id}/chat", json={"message": question})
            latency = time.perf_counter() - t0
            if r.status_code != 200:
                out.update(error=f"HTTP {r.status_code}: {r.text[:300]}")
            else:
                body = r.json()
                out.update(answer=body.get("answer"), intent=body.get("intent"), sufficient_evidence=body.get("sufficient_evidence"),
                           answer_type=body.get("answer_type"), path=body.get("path"), notice=body.get("notice"), sources=body.get("sources"), details_keys=sorted((body.get("details") or {}).keys()))
        except Exception as exc:  # noqa: BLE001 - recorded, never hidden
            latency = time.perf_counter() - t0
            out.update(error=f"{type(exc).__name__}: {exc}"[:300])
        calls = self.recorder.since(mark)
        out.update(latency_s=latency, llm_calls=calls, llm_summary=summarize_calls(calls))
        try:
            out["audit"] = self.last_audit()
        except Exception as exc:  # noqa: BLE001 - recorded, never hidden
            out["audit"] = None
            out["audit_error"] = f"{type(exc).__name__}: {exc}"[:200]
        return out
