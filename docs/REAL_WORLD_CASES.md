# Real-world cases driving balancelab

Mined from farm_memory (Latency Arbitrage) and product AI-token/game economy use.

## Case SIGNAL-INVERT / PRICE-BOOK-ORDER / KILL-SWITCH (farm) — CRITICAL

**Source:** Qdrant `farm_memory` failures on **Latency Arbitrage** (Bybit ↔
Polymarket bot). eagle-eyes matrix: balancelab was **NONE** until this cycle.

### What failed

1. **SIGNAL-INVERT:** BTC DOWN used DOWN mid as YES price — every DOWN signal
   traded as UP.
2. **PRICE-BOOK-ORDER:** Polymarket REST returned worst-to-best; ``.first()``
   took the worst quote → wrong spreads.
3. **KILL-SWITCH:** Loss-limit tripped on every paper fill (worst-case spread
   model) → strategy unevaluable.
4. **Economics:** Edge negative ~45× (strategy invalid) — economy gate
   refuse-to-ship class.

### Product fix in this repo

| Control | API |
|---------|-----|
| Ship/no-ship economy | `gate_economy` / `gate_exploit_report` |
| Empty graph | FAIL_LOUD |
| Exploits / runaway loops | FAIL (NO-SHIP) |
| Price book order | `gate_price_book` |
| Binary signal polarity | `gate_binary_signal` |
| Kill-switch trip rate | `gate_kill_switch` |
| Raise forms | `assert_economy_shippable`, `assert_price_book_ok` |

**Tests:** `tests/test_closed_loop.py`

**Non-Ornament:** Call `gate_economy` in CI before ship; call price/signal/kill
gates in trading pre-flight — not write-only scan logs.

---

## Case AV-AIVAT — anytime-valid agent evaluation stopping (arXiv 2608.06362)

**Source:** Track B research (prior sessions + `20260808T201228Z` multi-agent /
agentic eval cluster) —
[AV-AIVAT: anytime-valid AIVAT evaluation stopping](https://arxiv.org/abs/2608.06362).

**What fails:**

1. Fixed-budget agent comparisons **keep paying** (games/inference cost) after
   the ranking is already settled.
2. Naive early stop with ordinary CIs **invalidates** coverage, or stops before
   agents can be told apart (precision unmet).
3. Token/game spend has no load-bearing continue/stop gate (budget runaway twin
   of economy NO-SHIP).

**Product in this repo:**

| Control | API |
|---------|-----|
| Observation | `EvalObservation` |
| Streaming CS snapshot | `summarize_confidence_sequence` → `ConfidenceSequenceState` |
| Gate | `gate_eval_stopping(decision=continue\|stop)` |
| Raise form | `assert_eval_stopping_ok` |
| Defaults | `DEFAULT_TARGET_PRECISION`, `DEFAULT_Z` |

**Rules (load-bearing):**

- Empty observations when required → **FAIL_LOUD**
- `continue` while sequence **decisive** → **FAIL** (settled waste)
- `stop` while **not decisive** → **FAIL** (premature stop)
- `continue` past `max_total_cost` → **FAIL**
- `stop` when decisive / `continue` when not → **PASS**

**Tests:** `tests/test_av_aivat.py`

**Non-Ornament:** Call `gate_eval_stopping` before each additional eval spend.
Pair with `gate_economy` / `gate_kill_switch` for ship and trip-rate.

---

## Related product story

AI token budget 26× loops (README) — same `gate_economy` NO-SHIP path;
AV-AIVAT gates *when* to stop spending on agent comparisons.
