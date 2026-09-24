#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""A/B benchmark two commands (or two sample files) and check their outputs match.

`run` executes a baseline command (A) and a candidate command (B) in randomized
interleaved rounds, so drift from thermals, other load, or cache state hits
both sides equally. Each run records wall time and CPU time (user+sys,
including every descendant process), and hashes stdout. The report gives
median/p95 per metric and a bootstrap 95% confidence interval for the B/A
median ratio, with a verdict: faster, slower, or no detectable difference.

`compare` applies the same statistics to two files of per-iteration samples
(one number per line, any unit) emitted by an in-process harness.

Exit codes: 0 report printed; 1 a command failed or bad input; 3 A and B
stdout differ (first differing outputs are saved for diffing); 4 A's own
output varies between runs, so equality can't be checked (normalize it, e.g.
`| sort` or strip timestamps, or pass --no-check-output and prove equivalence
another way).

Output checking covers stdout only. When the program writes files, make the
command print them, e.g. `./prog -o out.bin && sha256sum out.bin`.
"""

import argparse
import hashlib
import os
import random
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BOOTSTRAP_ITERATIONS = 5000


def run_once(cmd: str) -> tuple[float, float, bytes, str]:
    """Return (wall_ms, cpu_ms, stdout_bytes, sha256) for one run."""
    start = time.perf_counter_ns()
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    assert proc.stdout is not None
    out = proc.stdout.read()
    _, status, usage = os.wait4(proc.pid, 0)
    wall_ms = (time.perf_counter_ns() - start) / 1e6
    proc.returncode = os.waitstatus_to_exitcode(status)
    if proc.returncode != 0:
        sys.exit(f"error: command exited {proc.returncode}: {cmd}")
    cpu_ms = (usage.ru_utime + usage.ru_stime) * 1000
    return wall_ms, cpu_ms, out, hashlib.sha256(out).hexdigest()


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def ratio_ci(a: list[float], b: list[float], rng: random.Random) -> tuple[float, float, float]:
    """Median ratio B/A with a percentile-bootstrap 95% confidence interval."""
    point = statistics.median(b) / statistics.median(a)
    ratios = sorted(
        statistics.median(rng.choices(b, k=len(b))) / statistics.median(rng.choices(a, k=len(a)))
        for _ in range(BOOTSTRAP_ITERATIONS)
    )
    return point, ratios[int(0.025 * BOOTSTRAP_ITERATIONS)], ratios[int(0.975 * BOOTSTRAP_ITERATIONS) - 1]


def report(metric: str, a: list[float], b: list[float], unit: str, rng: random.Random) -> None:
    point, lo, hi = ratio_ci(a, b, rng)
    if hi < 1:
        verdict = f"FASTER by {(1 - point) * 100:.1f}% (CI {(1 - hi) * 100:.1f}%..{(1 - lo) * 100:.1f}%)"
    elif lo > 1:
        verdict = f"SLOWER by {(point - 1) * 100:.1f}% (CI {(lo - 1) * 100:.1f}%..{(hi - 1) * 100:.1f}%)"
    else:
        verdict = f"no detectable difference (B/A CI {lo:.3f}..{hi:.3f})"
    print(f"{metric}:")
    for label, xs in (("A", a), ("B", b)):
        print(
            f"  {label}: median {statistics.median(xs):.3f} {unit}  p95 {percentile(xs, 0.95):.3f}"
            f"  min {min(xs):.3f}  stdev {statistics.stdev(xs):.3f}  n={len(xs)}"
        )
    print(f"  B/A median ratio {point:.4f} -> {verdict}")


def cmd_run(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    for _ in range(args.warmup):
        run_once(args.a)
        run_once(args.b)
    samples: dict[str, list[tuple[float, float]]] = {"A": [], "B": []}
    hashes: dict[str, set[str]] = {"A": set(), "B": set()}
    first_out: dict[str, bytes] = {}
    for _ in range(args.runs):
        order = ["A", "B"]
        rng.shuffle(order)
        for side in order:
            wall, cpu, out, digest = run_once(args.a if side == "A" else args.b)
            samples[side].append((wall, cpu))
            hashes[side].add(digest)
            first_out.setdefault(side, out)

    for i, (metric, unit) in enumerate((("wall time", "ms"), ("cpu time (user+sys)", "ms"))):
        report(metric, [s[i] for s in samples["A"]], [s[i] for s in samples["B"]], unit, rng)

    if args.no_check_output:
        print("output: NOT CHECKED (--no-check-output); prove equivalence another way")
        return 0
    if len(hashes["A"]) > 1:
        print(f"output: A produced {len(hashes['A'])} distinct outputs across runs; cannot compare")
        return 4
    if hashes["A"] != hashes["B"]:
        outdir = Path(tempfile.mkdtemp(prefix="abtest-"))
        (outdir / "a.out").write_bytes(first_out["A"])
        (outdir / "b.out").write_bytes(first_out["B"])
        print(f"output: DIFFERS; diff {outdir}/a.out {outdir}/b.out")
        return 3
    print(f"output: identical across all {2 * args.runs} runs (sha256 {next(iter(hashes['A']))[:16]})")
    return 0


def read_samples(path: Path) -> list[float]:
    try:
        values = [float(line) for line in path.read_text().split() if line]
    except (OSError, ValueError) as exc:
        sys.exit(f"error: {path}: {exc}; expected one number per line")
    if len(values) < 5:
        sys.exit(f"error: {path} has {len(values)} samples; need at least 5")
    return values


def cmd_compare(args: argparse.Namespace) -> int:
    report(args.metric, read_samples(args.a), read_samples(args.b), args.unit, random.Random(args.seed))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="mode", required=True)

    run = sub.add_parser("run", help="benchmark two shell commands, interleaved")
    run.add_argument(
        "--a", required=True, help="baseline shell command, e.g. 'cd ../base && ./target/release/app in.csv'"
    )
    run.add_argument("--b", required=True, help="candidate shell command")
    run.add_argument(
        "--runs", type=int, default=30, help="measured runs per side (default 30; use 50+ for effects under 2%%)"
    )
    run.add_argument("--warmup", type=int, default=3, help="unmeasured runs per side first (default 3)")
    run.add_argument("--seed", type=int, default=0, help="seed for run order and bootstrap (default 0)")
    run.add_argument("--no-check-output", action="store_true", help="skip the stdout equality check")
    run.set_defaults(func=cmd_run)

    cmp = sub.add_parser("compare", help="compare two sample files (one number per line)")
    cmp.add_argument("a", type=Path, help="baseline samples")
    cmp.add_argument("b", type=Path, help="candidate samples")
    cmp.add_argument("--metric", default="samples", help="label for the report (default: samples)")
    cmp.add_argument("--unit", default="", help="unit label, e.g. ns (default: none)")
    cmp.add_argument("--seed", type=int, default=0, help="bootstrap seed (default 0)")
    cmp.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    if getattr(args, "runs", 5) < 5:
        parser.error("--runs must be at least 5")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
