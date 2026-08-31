# SPDX-License-Identifier: Apache-2.0
"""Small seed sweep: does rounds=10/20 reliably fix reputation_scoring,
and does the warn-then-recover pattern (rounds=20) reproduce?

Not a formal study -- 5 seeds x 3 rounds values, in-process, to check the
single-seed (42) result isn't a coincidence. Run with:

    uv run python experiments/reputation_rounds/seed_sweep.py
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from nest_core.runner import ScenarioRunner
from nest_core.scenario import ScenarioConfig
from nest_core.validators import validate_trace

SEEDS = [1, 2, 3, 4, 5]
ROUNDS = [5, 10, 20]
BASE_YAML = Path("scenarios/reputation.yaml")


def _warn_then_recover(trace_path: Path) -> list[str]:
    """Agents that were warned mid-run but ended with score > -3."""
    events = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
    scores: dict[str, int] = {}
    warned: set[str] = set()
    for ev in events:
        if ev.get("kind") not in ("send", "broadcast"):
            continue
        msg = next(
            (v for v in ev.values() if isinstance(v, str) and v.startswith(("report:", "warning:"))),
            None,
        )
        if msg is None:
            continue
        if msg.startswith("report:"):
            _, _, agent, outcome = msg.split(":")
            scores[agent] = scores.get(agent, 0) + (1 if outcome == "good" else -2)
        elif msg.startswith("warning:"):
            _, _, agent, _ = msg.split(":")
            warned.add(agent)
    return sorted(a for a in warned if scores.get(a, 0) > -3)


async def run_one(rounds: int, seed: int, trace_path: Path) -> tuple[bool, list[str]]:
    config = ScenarioConfig.from_yaml(BASE_YAML)
    config.task.config["rounds"] = rounds
    config.seed = seed
    config.output.trace = str(trace_path)
    await ScenarioRunner(config).run()
    results = validate_trace(trace_path, "reputation")
    scoring_passed = next(r.passed for r in results if r.name == "reputation_scoring")
    recovered = _warn_then_recover(trace_path)
    return scoring_passed, recovered


async def main() -> None:
    print(f"{'rounds':>6} {'seed':>5}  scoring  warned-then-recovered")
    with tempfile.TemporaryDirectory() as tmp:
        tally: dict[int, list[bool]] = {r: [] for r in ROUNDS}
        for rounds in ROUNDS:
            for seed in SEEDS:
                trace_path = Path(tmp) / f"r{rounds}_s{seed}.jsonl"
                passed, recovered = await run_one(rounds, seed, trace_path)
                tally[rounds].append(passed)
                print(f"{rounds:>6} {seed:>5}  {'PASS' if passed else 'FAIL':>7}  {recovered}")
        print()
        for rounds in ROUNDS:
            n_pass = sum(tally[rounds])
            print(f"rounds={rounds}: {n_pass}/{len(SEEDS)} seeds PASS reputation_scoring")


if __name__ == "__main__":
    asyncio.run(main())
