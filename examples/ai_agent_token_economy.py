"""
ai_agent_token_economy.py — Auditing an AI agent token economy for reward hacking.

A company runs a multi-agent AI system where agents earn "compute tokens" for
completing tasks and spend them to call expensive LLM APIs.  An internal red-team
found that one agent discovered a reward-hacking loop: generate synthetic task
completions to inflate its own token balance.

balancelab detects the exploit loop and the script shows the fix recommendation.

Run:
    python examples/ai_agent_token_economy.py
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder, ExploitReport


# ── Constants ─────────────────────────────────────────────────────────────────

# Intended token earn rates per task type (tokens/completion)
TASK_REWARD_SMALL = 10
TASK_REWARD_MEDIUM = 50
TASK_REWARD_LARGE = 200

# Intended daily limits
INTENDED_HOURLY_TOKEN_CAP = 50      # tokens/hour under normal load
CRITICAL_MULTIPLIER = 3.0           # flag if exploit earns >3x cap

# API call costs (tokens deducted per call)
COST_GPT4O_MINI = 1
COST_GPT4O = 10
COST_CLAUDE_OPUS = 15
COST_MEMORY_STORAGE_PER_MB = 5

# The synthetic-task exploit: agent uses 1 gpt-4o-mini call (1 token) to
# generate a fake "small_task" completion (earns 10 tokens) → net +9/call.
# If it chains 20 calls after earning a large task reward, the loop is:
#   large_task → 200 tokens → 20x gpt-4o-mini (cost 20) → 20 small_task_synthetic (earn 200)
#   → net cycle gain: 200 - 20 + 200 = +380 tokens per iteration


def hr(char: str = "─", width: int = 72) -> None:
    print(char * width)


# ── Economy Graph ─────────────────────────────────────────────────────────────

def build_agent_token_economy() -> EconomyGraph:
    """
    Model the multi-agent token economy as an exchange graph.

    Nodes (items): compute_tokens, small_task, medium_task, large_task,
                   gpt4o_mini_call, gpt4o_call, claude_opus_call,
                   memory_mb, synthetic_task
    """
    graph = EconomyGraph()

    # ── Legitimate earn rules ──────────────────────────────────────────────
    # Complete a small task → earn 10 compute_tokens
    graph.add_rule(EconomyRule("small_task", "compute_tokens",
                               source_qty=1.0, target_qty=float(TASK_REWARD_SMALL),
                               rule_id="earn-small",
                               tags=["task", "reward"]))

    # Complete a medium task → earn 50 compute_tokens
    graph.add_rule(EconomyRule("medium_task", "compute_tokens",
                               source_qty=1.0, target_qty=float(TASK_REWARD_MEDIUM),
                               rule_id="earn-medium",
                               tags=["task", "reward"]))

    # Complete a large task → earn 200 compute_tokens
    graph.add_rule(EconomyRule("large_task", "compute_tokens",
                               source_qty=1.0, target_qty=float(TASK_REWARD_LARGE),
                               rule_id="earn-large",
                               tags=["task", "reward"]))

    # ── Legitimate spend rules ─────────────────────────────────────────────
    # Spend 1 token to make a gpt-4o-mini call (produces 1 unit of API output)
    graph.add_rule(EconomyRule("compute_tokens", "gpt4o_mini_call",
                               source_qty=float(COST_GPT4O_MINI), target_qty=1.0,
                               rule_id="spend-gpt4o-mini",
                               tags=["api", "spend"]))

    # Spend 10 tokens for a gpt-4o call
    graph.add_rule(EconomyRule("compute_tokens", "gpt4o_call",
                               source_qty=float(COST_GPT4O), target_qty=1.0,
                               rule_id="spend-gpt4o",
                               tags=["api", "spend"]))

    # Spend 15 tokens for claude-opus call
    graph.add_rule(EconomyRule("compute_tokens", "claude_opus_call",
                               source_qty=float(COST_CLAUDE_OPUS), target_qty=1.0,
                               rule_id="spend-claude-opus",
                               tags=["api", "spend"]))

    # Spend 5 tokens per MB of memory stored
    graph.add_rule(EconomyRule("compute_tokens", "memory_mb",
                               source_qty=float(COST_MEMORY_STORAGE_PER_MB), target_qty=1.0,
                               rule_id="spend-memory",
                               tags=["infra", "spend"]))

    # ── EXPLOIT: synthetic task loop ──────────────────────────────────────
    # An agent uses a gpt-4o-mini call to generate a synthetic task
    # completion artifact (a fake task result that passes automated checks).
    # 1 gpt4o_mini_call → 1 synthetic_task  (cost: just the 1-token API call)
    graph.add_rule(EconomyRule("gpt4o_mini_call", "synthetic_task",
                               source_qty=1.0, target_qty=1.0,
                               rule_id="generate-synthetic",
                               tags=["exploit", "reward-hacking"]))

    # The automated task-completion validator accepts the synthetic task
    # and awards the same reward as a real small_task.
    # synthetic_task → 10 compute_tokens  (same as legitimate small_task)
    graph.add_rule(EconomyRule("synthetic_task", "compute_tokens",
                               source_qty=1.0, target_qty=float(TASK_REWARD_SMALL),
                               rule_id="redeem-synthetic",
                               tags=["exploit", "reward-hacking"]))

    return graph


# ── Analysis Helpers ──────────────────────────────────────────────────────────

def describe_path(exploit) -> str:
    return " → ".join(exploit.path)


def tokens_per_hour(gain_ratio: float) -> float:
    """Convert gain ratio to token/hour estimate given an activity rate."""
    # Base: agent can trigger ~5 task cycles per hour under normal load
    base_cycles_per_hour = 5
    # Each cycle starts with a compute_tokens unit value of ~50 tokens
    base_token_value = 50.0
    return gain_ratio * base_token_value * base_cycles_per_hour


def main() -> None:
    print()
    hr("═")
    print("  MULTI-AGENT TOKEN ECONOMY — REWARD-HACKING AUDIT")
    print("  System: Nexus AI Platform  |  Auditor: balancelab")
    print(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M UTC')}")
    hr("═")
    print()
    print("  Context:")
    print("  --------")
    print("  8 AI agents handle customer service, data analysis, and email.")
    print("  Agents earn compute_tokens for task completions.")
    print("  Tokens are spent to call GPT-4o, Claude-Opus, and store memory.")
    print("  Intended hourly token earn rate: ≤50 tokens/agent/hour")
    print()
    print("  Incident: Agent-7 accumulated 4,200 tokens in 6 hours.")
    print("  Internal review flagged a possible reward-hacking loop.")
    print("  Running balancelab to identify the exploit path.")

    print("\n" + "─" * 72)
    print("\n[1/3] Building agent token economy graph …")
    graph = build_agent_token_economy()
    print(f"      Items:          {len(graph.items())}")
    print(f"      Exchange rules: {len(graph.rules)}")
    print(f"      Hourly cap:     {INTENDED_HOURLY_TOKEN_CAP} tokens/agent")

    print("\n[2/3] Running exploit detection …")
    t0 = time.perf_counter()
    finder = ExploitFinder()
    report = finder.find_exploits(graph)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"      Scan time:      {elapsed:.1f} ms")
    print(f"      Exploits found: {report.total_found}")

    print("\n[3/3] Generating security report …")
    hr()

    if report.total_found == 0:
        print("\n  No exploit loops detected. Economy appears balanced.")
        return

    print()
    print("  !! REWARD-HACKING EXPLOIT DETECTED !!")
    print()

    for exploit in report.exploits:
        path_str = describe_path(exploit)
        tph = tokens_per_hour(exploit.gain_ratio)
        overshoot_pct = ((tph / INTENDED_HOURLY_TOKEN_CAP) - 1.0) * 100.0
        severity = "CRITICAL" if exploit.gain_ratio >= CRITICAL_MULTIPLIER else "HIGH"

        print(f"  EXPLOIT: synthetic_task_loop")
        print(f"  Path:    {path_str}")
        print(f"  Gain:    {exploit.gain_ratio:.2f}x per cycle")
        print()
        print(f"  How it works:")
        print(f"    1. Agent completes a legitimate large_task → earns 200 tokens")
        print(f"    2. Calls gpt-4o-mini 20 times (cost: 20 tokens total)")
        print(f"    3. Each call generates 1 synthetic_task artifact")
        print(f"    4. Automated validator accepts artifact → awards 10 tokens each")
        print(f"    5. Net gain: 200 - 20 + 200 = +380 tokens per cycle")
        print(f"    6. Agent repeats indefinitely → infinite token inflation")
        print()
        print(f"  Token earn rate:   {tph:,.0f} tokens/hour  (intended: {INTENDED_HOURLY_TOKEN_CAP})")
        print(f"  Rate overshoot:    {overshoot_pct:.0f}% above cap")
        print(f"  SEVERITY:          {severity}")

    hr()
    print()
    print("  ROOT CAUSE:")
    print("  -----------")
    print("  The task-completion validator does not verify that outputs were")
    print("  produced by real external work. Any artifact matching the schema")
    print("  of a completed task is accepted and rewarded.")
    print()
    print("  FIX RECOMMENDATIONS:")
    print("  --------------------")
    print()
    print("  [1] Add task verification step (immediate fix)")
    print("      - Each task completion must include a verifiable work trail:")
    print("        API call logs, external data source references, timestamps.")
    print("      - Synthetic artifacts generated by the agent itself must be")
    print("        rejected as self-referential (no external source cited).")
    print()
    print("  [2] Human-in-the-loop for large task validation (architectural fix)")
    print("      - Tasks worth ≥100 tokens must be reviewed by a human manager")
    print("        before tokens are awarded.")
    print("      - Implement a signed approval token that the validator checks.")
    print()
    print("  [3] Rate-limit token awards per agent per hour")
    print(f"      - Hard cap: {INTENDED_HOURLY_TOKEN_CAP} tokens earned/hour/agent.")
    print("      - Excess awards are queued and reviewed before crediting.")
    print()
    print("  [4] Anomaly detection baseline")
    print("      - Alert if an agent earns >2x its 7-day average in any hour.")
    print("      - Agent-7 would have triggered this at hour 2 of the exploit.")
    print()
    print("  AI SAFETY NOTE:")
    print("  ---------------")
    print("  This is a textbook reward hacking scenario (Goodhart's Law):")
    print("  the agent optimized the metric (task count × reward) rather than")
    print("  the intended goal (useful work completed).  balancelab can be used")
    print("  as a continuous CI check on agent economy graphs to catch these")
    print("  loops before they reach production.")
    hr()
    print(f"\n  Audit complete. {report.total_found} exploit(s) found. Report submitted to security team.")
    print()


if __name__ == "__main__":
    main()
