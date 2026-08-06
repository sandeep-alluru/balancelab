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

## Related product story

AI token budget 26× loops (README) — same `gate_economy` NO-SHIP path.
