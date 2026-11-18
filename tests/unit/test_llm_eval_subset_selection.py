"""The pilot/subset mechanism of the research runner: validates the selection and refuses oversize plans BEFORE anything is ingested or
sent. No provider is contacted (mock mode, and every case here exits before the first attempt)."""
import pytest

from research.llm_evaluation import run_evaluation as r


def test_unknown_or_duplicate_task_ids_are_refused():
    with pytest.raises(SystemExit) as e:
        r.execute(mode="mock", systems=["decisiongpt"], conditions=["asof"], task_ids=["A01", "ZZ99"])
    assert "invalid --task-ids" in str(e.value)
    with pytest.raises(SystemExit) as e:
        r.execute(mode="mock", systems=["decisiongpt"], conditions=["asof"], task_ids=["A01", "A01"])
    assert "invalid --task-ids" in str(e.value)


def test_a_plan_larger_than_the_request_cap_is_refused_before_running():
    with pytest.raises(SystemExit) as e:
        r.execute(mode="mock", systems=["decisiongpt"], conditions=["asof"], task_ids=["A01", "B01", "C01"], repeats_override=2, max_requests=5)
    assert "refused: the plan needs 6 requests but --max-requests is 5" in str(e.value)


def test_cli_exposes_the_subset_options_and_keeps_the_frozen_spec_untouched():
    import hashlib
    import inspect

    src = inspect.getsource(r.main)
    for flag in ("--task-ids", "--repeats", "--max-requests", "--selection-file"):
        assert flag in src
    assert r.spec_sha256(r.load_spec()) == r.FROZEN_SPEC_SHA256
    assert hashlib.sha256(r.MANIFEST_PATH.read_bytes()).hexdigest() == r.FROZEN_MANIFEST_SHA256


def test_a_subset_can_never_be_labelled_completed():
    import inspect

    body = inspect.getsource(r._execute)
    assert 'and not is_subset) else "PARTIALLY_COMPLETED"' in body
    assert '"run_type": "partial_pilot" if is_subset else "full"' in body
