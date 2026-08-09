"""AV-AIVAT - anytime-valid evaluation stopping (arXiv 2608.06362).

Refuse continue after evidence is decisive; refuse stop before decisive.
"""

from __future__ import annotations

import pytest

from balancelab.av_aivat import (
    EvalObservation,
    assert_eval_stopping_ok,
    gate_eval_stopping,
    summarize_confidence_sequence,
)
from balancelab.closed_loop import ClosedLoopError


def test_empty_fails_loud() -> None:
    out = gate_eval_stopping([], decision="continue")
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert "AV-AIVAT" in out.reason


def test_unknown_decision_fails_loud() -> None:
    out = gate_eval_stopping([1.0, 2.0], decision="maybe")  # type: ignore[arg-type]
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"


def test_continue_while_not_decisive_passes() -> None:
    # High variance / few samples → wide CI includes 0
    obs = [0.1, -0.1, 0.05, -0.05]
    state = summarize_confidence_sequence(obs, target_precision=0.01, min_n=10)
    assert state.decisive is False or state.n < 10
    out = gate_eval_stopping(
        obs,
        decision="continue",
        target_precision=0.01,
        min_n=50,
        sample_sd=2.0,
    )
    assert out.ok is True
    assert out.verdict == "PASS"
    assert "continue" in out.reason


def test_continue_when_decisive_fails() -> None:
    # Strong positive signal, low SD → sign settled
    obs = [5.0] * 20
    state = summarize_confidence_sequence(obs, target_precision=10.0, sample_sd=0.1)
    assert state.sign_settled is True
    out = gate_eval_stopping(
        obs,
        decision="continue",
        target_precision=10.0,
        sample_sd=0.1,
    )
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "decisive" in out.reason.lower() or "settled" in out.reason.lower()


def test_stop_when_not_decisive_fails() -> None:
    obs = [0.01, -0.02, 0.0]
    out = gate_eval_stopping(
        obs,
        decision="stop",
        target_precision=0.001,
        min_n=100,
        sample_sd=5.0,
    )
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "not decisive" in out.reason.lower() or "premature" in out.reason.lower()


def test_stop_when_decisive_passes() -> None:
    obs = [-3.0] * 15
    out = gate_eval_stopping(
        obs,
        decision="stop",
        target_precision=5.0,
        sample_sd=0.2,
    )
    assert out.ok is True
    assert out.verdict == "PASS"
    assert "stop" in out.reason


def test_budget_exhausted_on_continue() -> None:
    obs = [
        EvalObservation(0.1, cost=10.0),
        EvalObservation(-0.1, cost=10.0),
        EvalObservation(0.05, cost=10.0),
    ]
    out = gate_eval_stopping(
        obs,
        decision="continue",
        max_total_cost=25.0,
        target_precision=0.0001,
        min_n=1000,
        sample_sd=10.0,
    )
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "cost" in out.reason.lower() or "budget" in out.reason.lower()


def test_dict_and_float_observations() -> None:
    out = gate_eval_stopping(
        [{"value": 2.0, "cost": 1}, 2.1, EvalObservation(1.9, cost=1.0)],
        decision="stop",
        sample_sd=0.05,
        target_precision=1.0,
    )
    assert out.ok is True


def test_precision_met_is_decisive() -> None:
    # Many identical samples → tiny half-width
    obs = [1.0] * 50
    state = summarize_confidence_sequence(obs, target_precision=0.5, sample_sd=0.1, min_n=5)
    assert state.precision_met is True
    assert state.decisive is True


def test_assert_raises() -> None:
    with pytest.raises(ClosedLoopError):
        assert_eval_stopping_ok(
            [0.0, 0.0],
            decision="stop",
            sample_sd=10.0,
            min_n=100,
            target_precision=0.001,
        )


def test_arxiv_av_aivat_fixture() -> None:
    """End-to-end: fixed-budget waste vs anytime-valid stop."""
    # Pre-fix class: keep evaluating after A clearly beats B
    settled = [1.5] * 30
    waste = gate_eval_stopping(
        settled,
        decision="continue",
        sample_sd=0.15,
        target_precision=1.0,
    )
    assert waste.ok is False
    assert waste.verdict == "FAIL"

    # Correct: stop once decisive
    done = gate_eval_stopping(
        settled,
        decision="stop",
        sample_sd=0.15,
        target_precision=1.0,
    )
    assert done.ok is True

    # Early stop with noise refused
    noisy = [0.2, -0.3, 0.1, -0.05, 0.0]
    early = gate_eval_stopping(
        noisy,
        decision="stop",
        sample_sd=2.0,
        target_precision=0.1,
        min_n=50,
    )
    assert early.ok is False

    # Continue under noise ok
    cont = gate_eval_stopping(
        noisy,
        decision="continue",
        sample_sd=2.0,
        target_precision=0.1,
        min_n=50,
    )
    assert cont.ok is True
    st = summarize_confidence_sequence(settled, sample_sd=0.15)
    assert st.to_dict()["decisive"] is True
