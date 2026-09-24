---
name: perf-tune
description: "Profile-driven speedups: ranked plan, A/B benchmarks, equivalence proof. Use when the user runs /perf-tune or asks to make code faster, cut latency or startup ms, or prove a speedup, even if they don't say profile."
disable-model-invocation: true
---

# Perf tune

Measure where a repository's workload spends its time, present a ranked plan of
the changes most likely to save milliseconds, and implement only the items the
user approves. Keep a change only when an interleaved A/B benchmark shows it
is faster and a differential run shows the output is unchanged. This works
in any language.

These rules replace the default "optimize while reading" behavior:

- Make no edits to the user's checkout before they approve specific plan
  items. Instrumentation and prototypes go in a throwaway copy or worktree.
- Claim a speedup only from an A/B run whose confidence interval excludes no
  change. "No detectable difference" means reject and revert, not "small win".
- Output must match the baseline byte-for-byte unless the user approved a
  named tolerance (float reassociation, result order).
- Never run anything needing root or changing system settings (governor,
  cache drops, sysctl); suggest it. Ask before installing system packages.

## Workflow

### 1. Scope and workload

Read the argument after `/perf-tune`: a path limits the review, a command is
the workload, and other text is a focus (startup, p99 latency, throughput,
one endpoint). Then pick the workload, first match wins:

1. The command or scenario the user named.
2. An existing benchmark suite or bench script in the repo. When the
   representative one needs a database or service you'd have to start, ask
   the user to start it; otherwise use the best one that runs offline and
   label the plan with what it leaves out.
3. The main entry point run on realistic input from the repo (fixtures,
   samples, docs examples). Ask the user for real input when only toy input
   exists: toy input puts the hot path in the wrong place.
4. The test suite, as a last resort and labeled unrepresentative.

When nothing runnable exists and the user can't supply a workload, continue
in static mode: mark every plan item "unmeasured" and say so in the verdict.

Build the optimized configuration (release, `-O2`, production mode), because
debug builds profile a different program. Note exactly which artifact the
workload runs; every later "rebuild" means that artifact.

Look at what the workload prints. When stdout is a pass/fail summary or
timings rather than the program's real output (a test runner's "7 passed"),
`abtest.py`'s output check proves nothing: plan a differential dump harness
for every item (step 6.4), and say so in the brief.

### 2. Baseline and noise floor

Read `references/measurement.md` sections **Noise control** and **Noise floor
and run counts**, run the checks, then measure the workload against itself:

```bash
uv run <this-skill-dir>/scripts/abtest.py run --a '<workload>' --b '<workload>' --runs 30
```

Record the baseline wall and CPU medians and the noise floor: the `±x%` on
the wall-time ratio line of this self-comparison. Output must be identical
across these runs. If `abtest.py` exits 4, the output is nondeterministic;
pass `--normalize '<filter>'` (strip timings, `sort` unordered lines) or fix
the seed until it is stable, and use the same flag in every later A/B.

### 3. Profile

Take a CPU profile and a syscall summary of the workload (tools, profiling
builds, and fallbacks when no profiler runs are in `references/measurement.md`
**Profilers**). Classify the workload from the baseline: CPU time well below
wall means it waits on IO or locks; CPU near wall means compute; CPU above
wall means already parallel. Skip the syscall summary for compute workloads
when no tracer is installed, and write "not measured".

Write a hot-path brief of 40 lines or fewer: the workload command, input,
baseline medians, noise floor, classification, the top frames or functions
with their share of wall time, syscall counts and bytes moved, the build and
test commands, and the repo's conventions (`AGENTS.md`, `CLAUDE.md`,
house-standards skills), including architecture rules such as which module
may own threads. Name any known candidate (a `ponytail:` or `TODO: perf`
note on a hot path) and assign it to one lens, so lenses don't all prototype
it. Run the repo's pre-commit test command once now, in the build mode the
workload uses, and record its result.

### 4. Fan out lenses

In a single message, start one subagent per lens (`cpu`, `io`,
`concurrency`, `data`) so they run in parallel, each with this prompt:

```text
Read <abs path to this skill>/references/lenses.md. Your prompt is its
"Shared preamble" section followed by its "<lens>" section. Follow both
exactly, and reply only in the preamble's output format.

Placeholders: REPO_PATH=<abs path> · LENS=<lens> · SCOPE=<scope>

Hot-path brief:
<the brief from step 3>
```

In Claude Code, use the `general-purpose` agent type; lenses may run the
workload, profilers, and prototypes in their own temp copy. Skip a lens the
classification rules out (no `io` for a pure in-memory compute kernel) and
say you did. Delete the lenses' temp copies after step 5; build dirs are
large.

### 5. Verify and rank

Treat lens output as leads. For each one, open the cited code, confirm it runs
on the workload's path (the profile or a trace), and recompute the estimate
yourself: share of wall time × fraction removed × baseline ms. Drop leads
that fail, and leads that only speed up the benchmark's own harness or
fixtures. Merge duplicates, and when two leads conflict, keep one and note
the trade-off. When an estimate assumes another item lands first, say
`after #n`. When a saving depends on the benchmark's access pattern rather
than real use (it repeats a query the real app asks once), say so in the
evidence and drop the confidence one level.

Group and sort by estimated saving, then confidence, then effort:

- **Do first:** estimate at least 3× the noise floor, confidence H or M.
- **Worth trying:** the rest of the measured items.
- **Speculative:** unmeasured, or below the noise floor alone.
- **Needs a decision:** anything that adds a dependency, changes a public
  API, stored or wire format, durability, or result order, or goes against
  the repo's architecture rules. Include these in the plan but not in "all"
  approvals unless the user names them.

Present the plan in chat in this format. Every field is REQUIRED:

```markdown
## Perf plan — <repo> (<short workload label>)

Workload: `<command>`. Baseline: <wall> ms wall, <cpu> ms CPU, noise floor ±<x>%.
Noise: <governor, load, pinning; any fix to suggest, or "clean">.
<one sentence on where time goes>.

### Do first
1. **<imperative title>** `[io]` · est −<ms> ms (−<pct>%)[ after #n] · conf H · effort S · risk: none
   `src/load.py:88` — <evidence: profile share + code fact, one sentence; "prototyped" if a lens measured it>
   Change: <one sentence>. Prove: <A/B workload + equivalence method>.

### Worth trying
…
### Speculative
…
### Needs a decision
…

<n> leads from <k> lenses; <m> dropped after verification; <j> merged.

Which items should I implement? ("all", "1-4, 7", or "none")
```

Stop and wait for the answer.

### 6. Implement approved items, one at a time

The baseline is `HEAD`, so start from a clean tree: if `git status` shows
changes, ask the user to commit or stash them. Record the start commit, then
create a baseline worktree in the scratchpad or a temp dir and build it:

```bash
git worktree add --detach <tmp>/perf-base HEAD
```

**Gotcha:** each side must run its own code. An editable install, shared
`node_modules` symlink, `PYTHONPATH`, or globally installed binary makes both
commands run the main checkout, and a stale un-rebuilt artifact runs old
code; either way every A/B reads "no difference". After each rebuild, print
the path and sha256 of the artifact each side runs (or the resolved module
file): the paths must be in their own trees and the hashes must differ.

Then for each approved item in plan order:

1. Make the change in the main checkout. Keep it to the item; if it needs a
   decision the plan didn't cover, revert it, mark it skipped, and continue.
2. Rebuild the artifact the workload runs, and run the tests that cover the
   touched code.
3. A/B it against the baseline worktree:
   `abtest.py run --a 'cd <tmp>/perf-base && <workload>' --b '<workload>'`.
   Use `--runs 50` or more when the estimate is under 3% of the baseline.
4. Prove equivalence with every layer the item's risk needs, from
   `references/measurement.md` **Proving equivalence**. `abtest.py` covers
   stdout on the workload input only. Keep differential harnesses in the
   scratchpad, copy the same file into both sides for the run, and remove
   them before committing.
5. Keep the item only when wall time is FASTER and every equivalence check
   passes. Otherwise revert it (`git restore .` and delete files it created)
   and record the numbers and the reason.
6. Commit a kept item with its A/B numbers in the message body, then,
   unless it is the last item, move the baseline to it (`git -C
   <tmp>/perf-base checkout --detach <sha>`) and rebuild, so each item is
   measured against the items kept before it. When the repo's instructions
   don't ask for commits, these are temporary: step 7 undoes them.

### 7. Report

With two or more kept items, measure the end-to-end change: check the
baseline worktree out at the start commit, rebuild, and A/B it against the
final state with the same workload. With one, reuse its numbers. Remove the
worktree (`git worktree remove`, which also deletes its build dir). If the
commits were temporary, `git reset --soft <start commit>` to leave the kept
changes staged.
Report with this table plus one line per skipped or rejected item:

```markdown
| # | Item | Verdict | Wall A → B (median) | Change (95% CI) | Equivalence |
|---|------|---------|---------------------|-----------------|-------------|
| 1 | Batch inserts | kept | 182.4 → 131.0 ms | −28.2% (−29.0..−27.3) | stdout + DB dump + edge corpus |
| 3 | Cache schema | rejected | 131.0 → 130.6 ms | no detectable diff | — |

End to end: 182.4 → 118.9 ms (−34.8%, CI −35.6..−34.0), output identical.
```

## Example

`/perf-tune "./ingest data/orders.csv"` on a Rust CLI. The baseline is
212 ms wall and 205 ms CPU with a ±1.2% noise floor, so the work is compute.
The profile puts 48% of wall time in `parse_row` and 22% in `Regex::new`.
Verification confirms the `cpu` lens's lead that a regex is compiled per row
(est −44 ms) and the `data` lens's lead to reuse one `String` buffer per line
(est −9 ms). It drops an `io` lead whose file read is 0.4% of wall time. The
user approves both. Item 1 A/Bs at −20.6% (CI −21.3..−19.9) with identical
stdout on the workload and the edge corpus, so it's kept. Item 2 shows no
detectable difference at 50 runs, so it's reverted. The report shows
212 → 168 ms end to end.

## Bundled resources

- `scripts/abtest.py` — **run** for every A/B and the noise-floor check. The
  `compare` subcommand takes per-iteration samples from a harness.
  `--help` has the flags and exit codes.
- `references/measurement.md` — **read** at step 2, and at step 6 for the
  equivalence layers. Covers noise control, metrics, harnesses, profilers.
- `references/lenses.md` — the preamble and four lens prompts. Lens subagents
  **read** it; read it yourself only in static mode or when changing a lens.
