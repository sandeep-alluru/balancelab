"""AV-AIVAT anytime-valid evaluation stopping (arXiv 2608.06362).

Public case: Fixed-budget agent comparisons either **keep paying after the
result is settled** or **stop before agents can be told apart**. Naive optional
stopping with ordinary CIs invalidates coverage. AV-AIVAT pairs variance-reduced
values with continuously monitored confidence sequences so evaluation may stop
as soon as evidence suffices - with the guarantee intact.

Product role in balancelab (economy twin of kill-switch / budget NO-SHIP):
  Gate the **decision to continue or stop** an agent evaluation run given
  streaming outcome scores and a simple anytime-valid confidence sequence.

Non-Ornament:
  Call ``gate_eval_stopping`` before each additional game / inference spend.
  Pair with ``gate_economy`` for ship/no-ship and ``gate_kill_switch`` for
  trip-rate collapse.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from balancelab.closed_loop import ClosedLoopError, GateOutcome

Decision = Literal["continue", "stop"]

# Nominal two-sided z for ~95% Gaussian CS plug-in (paper uses formal CS;
# this library exposes the *gate policy* around a streaming bound, not a
# research-grade CS estimator).
DEFAULT_Z: float = 1.96
DEFAULT_TARGET_PRECISION: float = 1.0  # ±1 unit (paper: ±1 BB)


@dataclass(frozen=True)
class EvalObservation:
    """One paired evaluation outcome (agent A minus agent B, or signed score)."""

    value: float
    cost: float = 1.0
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "cost": self.cost, "label": self.label}


@dataclass(frozen=True)
class ConfidenceSequenceState:
    """Streaming anytime-valid style bounds on mean value.

    Attributes:
        n: Number of observations.
        mean: Sample mean of values.
        half_width: ± half-width of the sequence at this n.
        lower / upper: mean ± half_width.
        total_cost: Sum of observation costs.
        decisive: True when 0 is outside [lower, upper] (sign settled) **or**
            half_width ≤ target_precision and n ≥ min_n (precision met).
        precision_met: half_width ≤ target_precision (with enough samples).
        sign_settled: lower > 0 or upper < 0.
    """

    n: int
    mean: float
    half_width: float
    lower: float
    upper: float
    total_cost: float
    decisive: bool
    precision_met: bool
    sign_settled: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "mean": self.mean,
            "half_width": self.half_width,
            "lower": self.lower,
            "upper": self.upper,
            "total_cost": self.total_cost,
            "decisive": self.decisive,
            "precision_met": self.precision_met,
            "sign_settled": self.sign_settled,
        }


def _as_obs(item: EvalObservation | dict[str, Any] | float | int) -> EvalObservation:
    if isinstance(item, EvalObservation):
        return item
    if isinstance(item, (int, float)):
        return EvalObservation(value=float(item))
    if not isinstance(item, dict):
        raise TypeError(f"observation must be EvalObservation|dict|number, got {type(item)!r}")
    if "value" not in item and "score" not in item and "delta" not in item:
        raise ValueError("observation missing value")
    val = item.get("value", item.get("score", item.get("delta")))
    if val is None:
        raise ValueError("observation value is None")
    return EvalObservation(
        value=float(val),
        cost=float(item.get("cost") or 1.0),
        label=str(item.get("label") or item.get("id") or ""),
    )


def summarize_confidence_sequence(
    observations: Sequence[EvalObservation | dict[str, Any] | float | int],
    *,
    target_precision: float = DEFAULT_TARGET_PRECISION,
    z: float = DEFAULT_Z,
    min_n: int = 2,
    sample_sd: float | None = None,
) -> ConfidenceSequenceState:
    """Compute a streaming Gaussian-style confidence sequence snapshot.

    Uses ``half_width = z * s / sqrt(n)`` with sample SD (or provided
    ``sample_sd``). This is a **gate-facing** plug-in CS, not a claim of
    exact AV-AIVAT AIVAT corrections - those reduce variance upstream; the
    gate consumes the resulting stream of values.
    """
    if target_precision < 0:
        raise ValueError("target_precision must be >= 0")
    if z <= 0:
        raise ValueError("z must be > 0")

    obs = [_as_obs(x) for x in observations]
    n = len(obs)
    if n == 0:
        return ConfidenceSequenceState(
            n=0,
            mean=0.0,
            half_width=float("inf"),
            lower=float("-inf"),
            upper=float("inf"),
            total_cost=0.0,
            decisive=False,
            precision_met=False,
            sign_settled=False,
        )

    values = [o.value for o in obs]
    mean = sum(values) / n
    total_cost = sum(o.cost for o in obs)

    if n == 1:
        s = abs(sample_sd) if sample_sd is not None else abs(values[0]) or 1.0
    elif sample_sd is not None:
        s = abs(float(sample_sd))
    else:
        var = sum((v - mean) ** 2 for v in values) / max(n - 1, 1)
        s = math.sqrt(var) if var > 0 else 0.0
        # floor SD so empty variance still widens early stops
        if s == 0.0:
            s = 1e-9

    half = z * s / math.sqrt(n)
    lower = mean - half
    upper = mean + half
    sign_settled = lower > 0.0 or upper < 0.0
    precision_met = n >= min_n and half <= target_precision
    decisive = sign_settled or precision_met

    return ConfidenceSequenceState(
        n=n,
        mean=mean,
        half_width=half,
        lower=lower,
        upper=upper,
        total_cost=total_cost,
        decisive=decisive,
        precision_met=precision_met,
        sign_settled=sign_settled,
    )


def gate_eval_stopping(
    observations: Sequence[EvalObservation | dict[str, Any] | float | int] | None,
    *,
    decision: Decision,
    target_precision: float = DEFAULT_TARGET_PRECISION,
    z: float = DEFAULT_Z,
    min_n: int = 2,
    sample_sd: float | None = None,
    max_total_cost: float | None = None,
    require_observations: bool = True,
) -> GateOutcome:
    """Refuse wasteful continue or premature stop (AV-AIVAT class).

    Rules:

    * No observations when required → **FAIL_LOUD**
    * ``decision=continue`` while sequence is **decisive** → **FAIL**
      (keep paying after result settled - paper failure mode)
    * ``decision=stop`` while sequence is **not decisive** → **FAIL**
      (stop before agents can be told apart / precision unmet)
    * ``max_total_cost`` exceeded and still continuing → **FAIL**
    * continue while not decisive (and under budget) → **PASS**
    * stop while decisive → **PASS**

    Args:
        observations: Stream of paired eval values so far.
        decision: Proposed next action for the evaluation loop.
        target_precision: Half-width goal (paper ±1 BB class).
        z: Critical value for the plug-in CS half-width.
        min_n: Minimum samples before precision_met can fire.
        sample_sd: Optional known SD (else sample).
        max_total_cost: Optional hard budget ceiling on continue.
        require_observations: Empty stream → FAIL_LOUD when True.
    """
    dec = (decision or "").strip().lower()
    if dec not in {"continue", "stop"}:
        return GateOutcome(
            ok=False,
            verdict="FAIL_LOUD",
            reason=(f"AV-AIVAT: unknown decision={decision!r} (use continue|stop)"),
            exit_code=2,
            human_required=True,
        )

    if not observations:
        if require_observations:
            return GateOutcome(
                ok=False,
                verdict="FAIL_LOUD",
                reason=(
                    "AV-AIVAT: no evaluation observations - cannot decide "
                    "continue/stop without a streaming score inventory "
                    "(arXiv 2608.06362)"
                ),
                exit_code=2,
                human_required=True,
            )
        if dec == "stop":
            return GateOutcome(
                ok=True,
                verdict="PASS",
                reason="AV-AIVAT: no observations required; stop allowed",
                exit_code=0,
                human_required=False,
            )
        return GateOutcome(
            ok=False,
            verdict="FAIL_LOUD",
            reason="AV-AIVAT: continue with empty stream refused",
            exit_code=2,
            human_required=True,
        )

    try:
        state = summarize_confidence_sequence(
            observations,
            target_precision=target_precision,
            z=z,
            min_n=min_n,
            sample_sd=sample_sd,
        )
    except (TypeError, ValueError) as exc:
        return GateOutcome(
            ok=False,
            verdict="FAIL_LOUD",
            reason=f"AV-AIVAT: invalid observations: {exc}",
            exit_code=2,
            human_required=True,
        )

    if max_total_cost is not None and state.total_cost > max_total_cost and dec == "continue":
        return GateOutcome(
            ok=False,
            verdict="FAIL",
            reason=(
                f"AV-AIVAT: total_cost={state.total_cost:.3f} exceeds "
                f"max_total_cost={max_total_cost:.3f} while decision=continue - "
                "budget exhausted (token/game spend runaway)"
            ),
            exit_code=1,
            human_required=True,
            rule_count=state.n,
            max_gain_ratio=state.mean,
        )

    if dec == "continue" and state.decisive:
        return GateOutcome(
            ok=False,
            verdict="FAIL",
            reason=(
                f"AV-AIVAT: decision=continue but sequence already decisive "
                f"(n={state.n} mean={state.mean:.4f} "
                f"CI=[{state.lower:.4f},{state.upper:.4f}] "
                f"sign_settled={state.sign_settled} "
                f"precision_met={state.precision_met}) - refuse keep-paying "
                "after result settled (arXiv 2608.06362 fixed-budget waste)"
            ),
            exit_code=1,
            human_required=False,
            rule_count=state.n,
            max_gain_ratio=state.mean,
        )

    if dec == "stop" and not state.decisive:
        return GateOutcome(
            ok=False,
            verdict="FAIL",
            reason=(
                f"AV-AIVAT: decision=stop but sequence not decisive "
                f"(n={state.n} mean={state.mean:.4f} "
                f"half_width={state.half_width:.4f} "
                f"target={target_precision}) - refuse premature stop before "
                "agents can be told apart / precision unmet"
            ),
            exit_code=1,
            human_required=True,
            rule_count=state.n,
            max_gain_ratio=state.mean,
        )

    if dec == "stop":
        return GateOutcome(
            ok=True,
            verdict="PASS",
            reason=(
                f"AV-AIVAT ok: stop with decisive sequence n={state.n} "
                f"mean={state.mean:.4f} half_width={state.half_width:.4f} "
                f"cost={state.total_cost:.3f}"
            ),
            exit_code=0,
            human_required=False,
            rule_count=state.n,
            max_gain_ratio=state.mean,
        )

    # continue, not decisive
    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=(
            f"AV-AIVAT ok: continue n={state.n} mean={state.mean:.4f} "
            f"half_width={state.half_width:.4f} target={target_precision} "
            f"cost={state.total_cost:.3f}"
        ),
        exit_code=0,
        human_required=False,
        rule_count=state.n,
        max_gain_ratio=state.mean,
    )


def assert_eval_stopping_ok(
    observations: Sequence[EvalObservation | dict[str, Any] | float | int] | None,
    **kwargs: Any,
) -> GateOutcome:
    """Raise :class:`ClosedLoopError` unless :func:`gate_eval_stopping` is ok."""
    outcome = gate_eval_stopping(observations, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome
