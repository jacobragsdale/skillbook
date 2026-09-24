# Measuring and proving performance changes

## Contents

- [Noise control](#noise-control)
- [Noise floor and run counts](#noise-floor-and-run-counts)
- [Metrics](#metrics)
- [Microbenchmark harnesses](#microbenchmark-harnesses)
- [Profilers](#profilers)
- [Proving equivalence](#proving-equivalence)

## Noise control

Check these before the baseline and record the state in the brief. Suggest
fixes that need root to the user; never run them yourself.

| Check | Command | If bad |
|---|---|---|
| CPU governor | `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor` | `powersave` inflates variance; suggest `sudo cpupower frequency-set -g performance` |
| Load | `uptime`; `top -bn1 \| head -15` | Ask the user to stop heavy jobs, or note it |
| Power | laptop on battery | Ask for AC power |
| Core pinning | `taskset -c 2 <cmd>` (both A and B) | Use it when variance is high on a multi-core box |
| Cache state | — | State warm or cold. Cold needs `sync; echo 3 \| sudo tee /proc/sys/vm/drop_caches` between runs, so it's user-only |
| Disk noise | — | For CPU-focused work, put inputs on tmpfs (`/dev/shm`); for IO work, use the real disk |

`abtest.py` interleaves A and B in random order, which cancels slow drift
(thermal throttling, background jobs) but not bursts. Rerun when the p95 is
far above the median on either side.

## Noise floor and run counts

Run the workload against itself before changing anything:

```bash
uv run <skill-dir>/scripts/abtest.py run --a '<workload>' --b '<workload>' --runs 30
```

The B/A confidence interval width is the noise floor: the smallest change a
30-run comparison can detect. Rules:

- An estimated saving below the noise floor can't be proven end-to-end.
  Increase `--runs` (the interval narrows with the square root of n), reduce
  noise, or prove it with a microbenchmark of the changed function plus an
  end-to-end run that shows no regression.
- Workloads under ~5 ms: process startup dominates. Loop the operation inside
  one process or use a harness below.
- Report medians and p95, never means alone; a single slow run moves a mean.

## Metrics

- **Wall time** is what users feel and what verdicts use.
- **CPU time** (user+sys) is less noisy for CPU-bound work. Parallelism
  raises CPU time while cutting wall time, so report both.
- **Instructions retired** (`perf stat -e instructions,cycles -r 10 <cmd>`)
  is the most stable CPU signal, often below 0.5% variance. Use it to prove
  sub-noise CPU savings when `perf` is installed.
- **Syscalls and bytes**: `strace -c -f <cmd>` for counts and time per
  syscall; `strace -f -e trace=read,write -o trace.txt` for sizes.
- **Service latency**: p50/p99 at a fixed request rate from a load generator
  (`oha`, `wrk`, `k6`); closed-loop max-throughput numbers hide queueing.

## Microbenchmark harnesses

Use the repo's existing harness first. Otherwise:

| Stack | Harness | Compare A vs B |
|---|---|---|
| Rust | `criterion` or `divan` via `cargo bench` | `cargo bench -- --save-baseline base`, then `-- --baseline base` |
| Go | `go test -bench . -count 10 -run '^$'` | `benchstat base.txt new.txt` |
| Python | `pyperf`; `python -m timeit` for one-liners | `pyperf compare_to base.json new.json` |
| JS/TS | `mitata` or `tinybench` | export samples, `abtest.py compare` |
| JVM | JMH | JMH score error columns |
| .NET | BenchmarkDotNet | its baseline column |
| C/C++ | google/benchmark or nanobench | `compare.py` from google/benchmark |

Anything that can print one timing per line works with
`abtest.py compare base.txt new.txt`.

Pitfalls: the optimizer deleting unused results (use `black_box`,
`DoNotOptimize`, or consume the value), constant inputs folded at compile
time, benchmarking debug builds, JIT and GC warmup, inputs that fit in cache
when production data doesn't.

## Profilers

Prefer ephemeral runners (`uvx`, `npx`, `go run`) over installs. Ask before
installing system packages.

| Question | Tool |
|---|---|
| Where does CPU go? (native) | `perf record -g` + `perf report`; `samply record <cmd>` |
| Python | `uvx py-spy record -o prof.svg -- <cmd>`; `py-spy top`; `python -X importtime` for startup |
| Node | `node --cpu-prof`; `npx 0x` |
| Go | `pprof` (`-cpuprofile`, `go tool pprof -top`) |
| JVM | async-profiler |
| .NET | `dotnet-trace`, `dotnet-counters` |
| Waiting, not computing | `strace -c -f`; `perf trace -s`; off-CPU profiles (`offcputime` from bcc) |
| Database | `EXPLAIN ANALYZE`; the slow query log |
| Allocations | `heaptrack`, `memray` (Python), `dhat` (Rust) |

With no profiler available, time phases directly: wrap major stages in
monotonic-clock timestamps written to stderr, run the workload, and remove
the instrumentation before measuring the baseline.

## Proving equivalence

Passing tests are necessary, not sufficient: they rarely cover the inputs
that make a faster path diverge. Use every layer the item's equivalence risk
needs:

1. **Differential run.** Feed identical inputs to A and B and byte-compare
   everything they produce: stdout (`abtest.py` does this), exit code, files
   (`sha256sum` or `diff -r` of output dirs), and database rows
   (`ORDER BY` dump).
2. **Edge corpus.** Beyond the workload input, run both sides on empty
   input, one item, the largest realistic input, unicode, malformed input,
   and error paths. Error messages and exit codes are output too.
3. **Ordering.** If parallelism or a hash map changes result order, find out
   whether order is part of the contract (docs, callers, tests, downstream
   diffs). If it is, restore it (stable sort, indexed results). If it's
   unclear, ask the user. Normalize (`| sort`) only for order that isn't
   contractual.
4. **Floats.** Reassociation (parallel reductions, SIMD, fast-math) changes
   low bits. Prefer an order-preserving change. Otherwise compare with a
   tolerance, name it in the report, and get the user's approval; never
   enable fast-math silently.
5. **Caches.** Prove invalidation: run, change the underlying input, run
   again, and confirm B sees the change exactly when A does.
6. **Concurrency.** Run the race detector (`go test -race`,
   `-fsanitize=thread`, `cargo +nightly miri test` where practical) and
   repeat the differential run 20+ times to shake out interleavings.
7. **Compression and formats.** Round-trip (decompress(compress(x)) == x) on
   the corpus, and confirm existing readers still accept the output. A
   changed stored or wire format is a compatibility change for the user to
   approve, even when round-trips pass.
