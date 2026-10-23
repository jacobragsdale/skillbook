---
name: diagnosing-bugs
description: "Diagnose hard bugs and regressions with a red repro loop, hypotheses, and a fix. Use when the user says debug or diagnose, or reports something broken, throwing, failing, flaky, or slower \u2014 even if they only paste an error."
license: "MIT, adapted from mattpocock/skills. See LICENSE.txt"
---

# Diagnosing bugs

A discipline for hard bugs and regressions. Skip a phase only when you say
why. For making working code faster rather than finding why it broke or got
slower, use `perf-tune`.

## Redact

This skill has you show commands, outputs, and captured artifacts. **Redact
every secret and every piece of client or account data first**: write
`<REDACTED>` in its place. Build loops against env vars, so the credential
stays in the environment rather than in what you show. Captured artifacts
carry auth headers: quote only the lines that carry the signal.

If the redacted output is not enough to diagnose the bug, say so and ask the
user.

## Phase 1: Build a feedback loop

**This is the skill.** Everything else is mechanical. If you have a **tight**
pass/fail signal for the bug (one that goes red on _this_ bug), you will find
the cause; bisection, hypothesis-testing, and instrumentation all just
consume it. If you don't have one, no amount of staring at code will save
you.

Spend disproportionate effort here. **Be aggressive. Be creative. Refuse to
give up.**

### Ways to construct one, in roughly this order

1. **Failing test** at whatever seam reaches the bug: unit, integration, e2e.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a
   known-good snapshot.
4. **Data fixture.** When the bug depends on data, extract the offending
   rows read-only (from a non-production copy when one exists) into a local
   fixture, redacted, and run the code path on it.
5. **Headless browser script** (Playwright) that drives the UI and asserts on
   DOM, console, or network.
6. **Replay a captured trace.** Save a real request, payload, or event log to
   disk; replay it through the code path in isolation.
7. **Throwaway harness.** Spin up a minimal subset of the system (one
   service, mocked deps) that exercises the bug code path with a single
   function call.
8. **Property / fuzz loop.** If the bug is "sometimes wrong output", run 1000
   random inputs and look for the failure mode.
9. **Bisection harness.** If the bug appeared between two known states
   (commit, dataset, version), automate "boot at state X, check, repeat" so
   you can `git bisect run` it.
10. **Differential loop.** Run the same input through old-version vs
    new-version (or two configs) and diff outputs.
11. **Human-in-the-loop script.** Last resort. If a human must click, drive
    _them_ with a copy of `scripts/hitl-loop.template.sh` so the loop is
    still structured. Captured output feeds back to you.

Build the right feedback loop, and the bug is 90% fixed.

### Tighten the loop

Treat the loop as a product. Once you have _a_ loop, **tighten** it:

- Can I make it faster? (Cache setup, skip unrelated init, narrow the test
  scope.)
- Can I make the signal sharper? (Assert on the specific symptom, not
  "didn't crash".)
- Can I make it more deterministic? (Pin time, seed RNG, isolate filesystem,
  freeze network.)

A 30-second flaky loop is barely better than no loop; a 2-second
deterministic one is tight, a debugging superpower.

### Non-deterministic bugs

The goal is not a clean repro but a **higher reproduction rate**. Loop the
trigger 100×, parallelise, add stress, narrow timing windows, inject sleeps.
A 50%-flake bug is debuggable; 1% is not, so keep raising the rate until it's
debuggable.

### When you genuinely cannot build a loop

Stop and say so explicitly. List what you tried. Ask the user for: (a)
access to whatever environment reproduces it, (b) a redacted captured
artifact (HAR file, log dump, core dump, screen recording with timestamps),
or (c) permission to add temporary production instrumentation. Do **not**
proceed to hypothesise without a loop.

### Completion criterion: a tight loop that goes red

Phase 1 is done when the loop is **tight** and **red-capable**: you can name
**one command** (a script path, a test invocation, a curl) that you have
**already run at least once** (show the invocation and its output, redacted),
and that is:

- [ ] **Red-capable**: it drives the actual bug code path and asserts the
  **user's exact symptom**, so it can go red on this bug and green once
  fixed. Not "runs without erroring"; it must be able to _catch this
  specific bug_.
- [ ] **Deterministic**: same verdict every run (flaky bugs: a pinned, high
  reproduction rate, per above).
- [ ] **Fast**: seconds, not minutes.
- [ ] **Agent-runnable**: you can run it unattended; a human in the loop only
  via the template script.

If you catch yourself reading code to build a theory before this command
exists, **stop: jumping straight to a hypothesis is the exact failure this
skill prevents.** No red-capable command, no Phase 2.

## Phase 2: Reproduce + minimise

Run the loop. Watch it go red as the bug appears.

Confirm:

- [ ] The loop produces the failure mode the **user** described, not a
  different failure that happens to be nearby. Wrong bug = wrong fix.
- [ ] The failure is reproducible across multiple runs (or, for
  non-deterministic bugs, at a high enough rate to debug against).
- [ ] You have captured the exact symptom (error message, wrong output, slow
  timing) so later phases can verify the fix addresses it.

### Minimise

Once it's red, shrink the repro to the **smallest scenario that still goes
red**. Cut inputs, callers, config, data, and steps **one at a time**,
re-running the loop after each cut, and keep only what's load-bearing for the
failure.

A minimal repro shrinks the hypothesis space in Phase 3 and becomes the clean
regression test in Phase 5.

Done when **every remaining element is load-bearing**: removing any one of
them makes the loop go green.

## Phase 3: Hypothesise

Generate **3–5 ranked hypotheses** before testing any of them.
Single-hypothesis generation anchors on the first plausible idea.

Each hypothesis must be **falsifiable**: state the prediction it makes.

> Format: "If <X> is the cause, then <changing Y> will make the bug
> disappear / <changing Z> will make it worse."

If you cannot state the prediction, the hypothesis is a vibe: discard or
sharpen it.

**Show the ranked list to the user before testing.** They often have domain
knowledge that re-ranks instantly ("we just deployed a change to #3"), or
know hypotheses they've already ruled out. Don't block on it; proceed with
your ranking if the user is away.

## Phase 4: Instrument

Each probe must map to a specific prediction from Phase 3. **Change one
variable at a time.**

Tool preference:

1. **Debugger / REPL inspection** if the env supports it. One breakpoint
   beats ten logs.
2. **Targeted logs** at the boundaries that distinguish hypotheses.
3. Never "log everything and grep".

**Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]`. Cleanup at
the end becomes a single grep.

**Attack the premise.** When two probes or fixes that share one assumption
have both failed, write that assumption down as one sentence and test it
directly before trying a third. Each failure was evidence against it.

**Perf regressions.** Logs are usually wrong here. Establish a baseline
measurement (timing harness, profiler, query plan), then bisect. Measure
first, fix second.

## Phase 5: Fix + regression test

Fix where the system first goes wrong, not where the symptom shows. A guard,
retry, or catch-all is a fix only when the state it handles is legitimate.
Disabling TLS verification is never the fix for a certificate error: find
the CA bundle the corporate proxy needs.

Write the regression test **before the fix**, but only if there is a
**correct seam** for it. For Python, design the test with `python-testing`.

A correct seam is one where the test exercises the **real bug pattern** as it
occurs at the call site. If the only available seam is too shallow
(single-caller test when the bug needs multiple callers, unit test that can't
replicate the chain that triggered the bug), a regression test there gives
false confidence.

**If no correct seam exists, that itself is the finding.** Note it: the
architecture is preventing the bug from being locked down.

If a correct seam exists:

1. Turn the minimised repro into a failing test at that seam.
2. Watch it fail. If you forced the red by mutating code or a fixture, `diff`
   against a pristine copy to prove the mutation landed before you trust it.
3. Apply the fix.
4. Watch it pass.
5. Re-run the Phase 1 feedback loop against the original (un-minimised)
   scenario.

## Phase 6: Cleanup

Required before declaring done:

- [ ] Original repro no longer reproduces (re-run the Phase 1 loop)
- [ ] Regression test passes (or absence of seam is documented)
- [ ] All `[DEBUG-...]` instrumentation removed (`grep` the prefix)
- [ ] Throwaway harnesses, fixtures, and extracted data deleted (or moved to
  a clearly marked debug location, redacted)
- [ ] The hypothesis that turned out correct is stated in the commit message,
  so the next debugger learns

## Bundled resources

- `scripts/hitl-loop.template.sh` — **copy** to the scratchpad, edit the
  steps between the markers, and run it when a human must perform part of the
  repro. It prints captured answers as `KEY=VALUE` lines for you to read.
