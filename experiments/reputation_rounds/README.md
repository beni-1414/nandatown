# Experiment: NANDA Town Assessment – MIT AI Studio Fall 2026

One setting changed, `task.config.rounds`, from the `reputation.yaml` baseline (5) to 10 and 20. Everything else (agents, layers, `failures.message_drop: 0.0`, seed 42) remained untouched.

## Files

- `reputation_rounds10.yaml`, `reputation_rounds20.yaml` — the two variant scenarios.
- `seed_sweep.py` — reruns baseline/10/20 across 5 seeds in-process and prints validator results.
- `traces/` — generated JSONL traces, not committed

## Reproduce

```bash
uv sync
uv run nest doctor                                   # 7/7 checks

# Baseline (rounds=5, seed 42) -- ships with the repo, unmodified
uv run nest run scenarios/reputation.yaml -o experiments/reputation_rounds/traces/baseline.jsonl

# The two changed-rounds variants
cd experiments/reputation_rounds
uv run --project ../.. nest run reputation_rounds10.yaml -o traces/reputation_rounds10.jsonl
uv run --project ../.. nest run reputation_rounds20.yaml -o traces/reputation_rounds20.jsonl

# Validate any trace
uv run --project ../.. python -c "
from pathlib import Path
from nest_core.validators import validate_trace
for r in validate_trace(Path('traces/reputation_rounds10.jsonl'), 'reputation'):
    print(('PASS' if r.passed else 'FAIL'), r.name, '-', r.detail)
"

# 5-seed sweep across rounds in {5,10,20} (seeds 1-5, edit SEEDS in the script to change)
uv run python seed_sweep.py
```

Same seed -> identical trace (Tier 1 is deterministic), so these commands reproduce the exact numbers below. To try other seeds, edit `config.seed` in the YAML, or `SEEDS`/`ROUNDS` at the top of `seed_sweep.py`.

## Findings

**Baseline (rounds=5, seed 42) fails `reputation_scoring`.** `malicious-3` cheated once, but the only agent it cheated against was `malicious-1` — and only *honest* initiators report outcomes to the observer. This means a malicious-on-malicious cheat is structurally invisible to the reputation system, independent of any failure injection (`message_drop` was 0.0 throughout).

**Raising `rounds` flips this to PASS** (seed 42: rounds=10 and rounds=20 both PASS, "checked 4 cheaters, 20 agents scored"). A separate 5-seed sweep (seeds 1-5) shows the same pattern recurring under different randomness rather than being a one-off: one seed (4) also fails at rounds=5 and flips to PASS by rounds=10, while the other four already pass at rounds=5.

**Monotonic increase:** the `report:` event sequence for rounds 1-5 is identical between a seed's rounds=5 run and its rounds=10 run (verified by diffing the traces). Extending `rounds` only *adds* more trade attempts, it never changes earlier ones. Since a validator failure requires a cheater to go permanently unreported, and more rounds only ever gives more chances to report someone, the process is monotonic: a seed that already passes at rounds=5 cannot regress, and only a seed that starts failing has room to improve. That's exactly the shape of the observed data (4/5 seeds were already fine; only the failing one flipped).

**`reputation_warnings` has a blind spot:** at rounds=20 (seed 42) it PASSED, but its detail string read "4 warnings issued, 3 needed" — `malicious-2` was warned the instant its live score first hit -3, then recovered to -2 by the run's end from later honest trades, and the validator only reconstructs who *should* be warned from the final score, checking for missing warnings but never for extra ones. The same pattern shows up at every rounds value tested (1/5, 3/5, 1/5 seeds), so it isn't affected by number of rounds in these settings. The sample is too small to say more than that.

## AI disclaimer

Claude Code (Sonnet 5) was used throughout this assignment: exploring the NANDA Town docs and scenario source to understand how `reputation` actually works, running the baseline and the 5-seed robustness sweep (`seed_sweep.py`), and drafting this README. I chose the scenario, the setting to change, and the hypothesis; reviewed every claim in this document against the actual trace and validator output; and corrected several inaccuracies that came up in earlier drafts (a wrong seed-attribution claim, an overstated bug framing for a validator quirk that turned out to be working as documented).