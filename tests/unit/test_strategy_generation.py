"""Phase 1.1 — goal-aware candidate strategy generation."""
import pytest

from app.services import strategy_generation_service as sg


class _Goal:
    def __init__(self, objective, constraints=None, gid="G1"):
        self.id = gid
        self.objective = objective
        self.constraints_json = constraints or []


class _FakeQuery:
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, _name):
        # filter / order_by / join / distinct / ... -> chainable no-ops
        return lambda *a, **k: self

    def all(self):
        return []

    def first(self):
        return None

    def one_or_none(self):
        return None

    def count(self):
        return 0

    def scalar(self):
        return None


class _FakeDB:
    """Minimal stand-in — strategy_generation only calls kpi_service (which
    only queries Sale/MarketingCampaign/Product) and _current_inventory_units."""

    def query(self, *a, **k):
        return _FakeQuery()


@pytest.fixture()
def db():
    return _FakeDB()


def test_revenue_goal_has_no_data_excludes_marketing_and_inventory(db):
    result = sg.generate_candidates(db, "b1", _Goal("increase_revenue"))
    names = [c.name for c in result.candidates]
    # No marketing / inventory data on the fake DB -> those families are dropped.
    assert names, result
    assert all("Marketing" not in n for n in names)
    assert all("Inventory" not in n for n in names)
    assert any("marketing" in e.lower() for e in result.excluded)
    # Every surviving candidate is a price move with a rationale + targets.
    for c in result.candidates:
        assert c.actions and all(a["type"] == "price_change" for a in c.actions)
        assert c.rationale and c.goal_alignment and c.targets


def test_profit_goal_produces_price_up_candidates(db):
    result = sg.generate_candidates(db, "b1", _Goal("increase_profit"))
    price_up = [c for c in result.candidates if any(a["type"] == "price_change" and a["value"] > 0 for a in c.actions)]
    assert price_up, [c.name for c in result.candidates]


def test_profit_and_revenue_goals_generate_different_sets(db):
    rev = {c.name for c in sg.generate_candidates(db, "b1", _Goal("increase_revenue")).candidates}
    prof = {c.name for c in sg.generate_candidates(db, "b1", _Goal("increase_profit")).candidates}
    assert rev != prof


def test_marketing_roi_goal_without_marketing_data_is_insufficient_evidence(db):
    result = sg.generate_candidates(db, "b1", _Goal("improve_marketing_roi"))
    assert result.candidates == []
    assert result.excluded  # states why


def test_inventory_risk_goal_without_inventory_data_is_insufficient_evidence(db):
    result = sg.generate_candidates(db, "b1", _Goal("reduce_inventory_risk"))
    assert result.candidates == []
    assert result.excluded


def test_no_price_increase_constraint_filters_price_up_candidates(db):
    result = sg.generate_candidates(db, "b1", _Goal("increase_profit", constraints=["no_price_increase"]))
    assert "no_price_increase" in result.constraints_applied
    for c in result.candidates:
        assert all(not (a["type"] == "price_change" and a["value"] > 0) for a in c.actions)


def test_churn_goal_generates_candidates_with_retention_caveat(db):
    result = sg.generate_candidates(db, "b1", _Goal("reduce_churn"))
    assert result.candidates
    # Retention effect is explicitly flagged as not simulated.
    assert any("retention" in n.lower() for c in result.candidates for n in c.assumptions)


def test_every_candidate_action_is_within_digital_twin_bounds(db):
    for objective in ("increase_revenue", "increase_profit", "increase_sales", "reduce_churn"):
        result = sg.generate_candidates(db, "b1", _Goal(objective))
        for c in result.candidates:
            assert sg._within_bounds(c.actions), (objective, c.name)
