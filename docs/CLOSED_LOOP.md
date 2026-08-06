# Closed loop — `balancelab`

**Status:** reader wired (eagle-eyes / 2026-08-06) — **NO-SHIP + farm signal gates**  
**Owner loop:** Game/econ / trading pre-flight

## Load-bearing job

Economy exploit / balance red-team + trading quote/signal integrity

## Who reads the output?

- `gate_economy` / `assert_economy_shippable` — CI ship/no-ship
- `gate_price_book` / `gate_binary_signal` / `gate_kill_switch` — farm trading failures

## What outcome changes?

Empty graph → FAIL_LOUD. Exploit cycles → FAIL (NO-SHIP). Inverted quotes/signals
or always-trip kill switch → FAIL.

## When NOT to use (anti-ornament)

Irrelevant as default MCP on non-game agents

## Non-Ornament checklist

- [x] Reader implemented (`closed_loop` gates)
- [x] Empty/wrong output fails loudly
- [x] Not free MCP without gate
- [ ] Linked gap IDs in mem0 when improving

## Related failures (farm memory)

- 2026-07-22 MCP buffet trim: write-only tools removed from Foundry framework
- D-FOGHORN: misuse of append-only fact log as current state
- Dual-path mem0: never rely on MCP-only for critical memory

## Daily rotation note

This file exists so pillar **C (closed loop)** can rise with real wiring over time. Prefer small daily commits that move a checkbox toward done.

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2
