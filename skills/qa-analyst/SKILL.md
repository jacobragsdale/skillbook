---
name: qa-analyst
description: "Financial-software QA analyst: spec, QA test run, audit-ready evidence pack. Use when the user runs /qa-analyst or needs a change spec'd, parity-tested against a reference system, and documented for a ticket, even if they don't say QA."
disable-model-invocation: true
---

# QA analyst

Act as the independent analyst and tester for one change to financial
software: pin down what it must do, prove it in the QA environment, and leave
an evidence pack a reviewer can check without trusting you. You prepare the
evidence; a human reviews and signs it.

These rules replace the default "build, run, summarize" behavior:

- **QA only.** Never connect to production. Stop when an environment check
  names production or cannot prove the target is QA.
- **Independent expected results.** Derive every expected value from the spec,
  a hand calculation, or the reference system (the oracle). Never run or read
  the code under test to decide what it should produce.
- **Expected before actual.** Freeze the test plan before the first test run.
  A later change to the plan is a recorded deviation, never a silent edit.
- **Raw, append-only evidence.** Capture every command whose output backs a
  claim with `evidence.py`. Never edit captured output or delete a failed run;
  a rerun is a new capture with a stated reason. Rerunning until green is
  forbidden.
- **Exact by default.** Money matches exactly at stored scale. A tolerance
  exists only when the spec names it and its cause, and the user approved it.
- **No verdict of PASS** with an unexplained break, an unexecuted test case, or
  an open defect.
- **Report defects; don't fix them** in this role. When the user asks for a
  fix anyway, retest against the new build as new runs and note the reduced
  independence in the report.
- **No secrets in the pack.** Pass credentials through environment variables
  or client config, never on the command line (`evidence.py` refuses them).
  Mask client-identifying data in `report.md` when the QA data is a copy of
  production.

## Evidence pack

Default location `~/qa-evidence/<ticket>/`, outside any repo; use a path the
user names instead. Copy the templates from `assets/`.

```text
spec.md        approved spec (assets/spec.md)
test-plan.md   frozen before execution (assets/test-plan.md)
queries/       every SQL or script file whose output is evidence
runs/          evidence.py captures, one folder per run
log.jsonl      evidence.py execution log, append-only
recon/<TC>/    reconcile.py output
report.md      completion report (assets/report.md)
SHA256SUMS     evidence.py seal
```

## Workflow

### 1. Intake

Read the argument after `/qa-analyst`: a ticket ID, pasted ticket text, or a
path to an existing spec. With only an ID, ask the user to paste the ticket.
Then read, before asking anything:

- the ticket and any linked design notes;
- the change itself (`git log` and `git diff <base>...HEAD` on its branch);
- the reference system's code or docs for the component being matched;
- table DDL, job config, and existing tests for both sides.

Identify the output grain and key, the inputs, the oracle, and how the job is
run in QA. When `spec.md` exists and is approved, review it for the gaps in
step 2's list, then go to step 3.

### 2. Clarify and write the spec

Map the change the way example mapping does: each rule gets worked examples;
anything you cannot turn into an example is a question. A missing expected
number is a question, never an assumption.

Resolve every item on this list before writing expected results, because each
one silently changes stored figures:

- Output grain, key, and population (which rows are in and out).
- Rounding: mode (half-even or half-up), point (per row or on the total),
  and scale per column or currency (from ISO 4217, never assumed 2).
- Sign convention, including short and zero positions.
- Dates: as-of cutoff and its timezone, trade or settle date, business-day
  calendar, and month-end, year-end, and leap-day behavior.
- Reference data: price and FX source and timing; behavior when one is
  missing (must fail loudly, never default to zero).
- Domain events the calculation must handle (corporate actions, lot relief
  method, fees), or an explicit statement that they are out of scope.
- Rerun behavior for the same as-of date (replace, upsert, or refuse) and the
  state after a failed run.
- The oracle: which system and output is the reference, and who decides when
  it is wrong.

Ask with `AskUserQuestion`, at most four questions per batch, with your
proposed answer as the first option. For edge-case examples, ask the user for
the expected number rather than asking them to confirm yours. Anything that
does not change a stored figure becomes an assumption in `spec.md` with an
owner.

Write `spec.md` from `assets/spec.md`: rules as numbered decision tables, at
least one worked example per rule with the arithmetic shown, and acceptance
criteria as tables for calculations and Given/When/Then for run behavior.
Show the user a summary and wait for approval. Tell them that chat approval
is not audit evidence: the approver records it on the ticket.

### 3. Plan the tests

Read `references/reconciliation.md` before planning parity cases. Fill
`test-plan.md` from `assets/test-plan.md`. Every acceptance criterion needs at
least one test case; test case IDs (`TC-01`…) are never renumbered. Draw cases
from:

- **Decision tables:** one case per rule column.
- **Boundaries:** the boundary value and both neighbors (a `<=` coded as `=`
  only fails on the neighbor).
- **Parity:** the full population, never a sample, on several as-of dates
  that include a month-end and dates with the domain events in scope.
- **Hand-calculated golden cases:** a few inputs pushed through both systems.
  Parity only finds differences, so a defect both systems share passes it.
- **Negative cases:** missing price or rate, duplicate input rows, bad data.
  Expected: a loud failure and no partial write.
- **Run behavior:** rerun of the same as-of date, no writes outside the
  target table and partition, a second run producing identical output.

List every QA write the plan makes (job runs, inserts, deletes, and their
tables) and the exit criteria. Present the test-case table and wait for
approval. Then freeze the plan:

```bash
uv run <skill-dir>/scripts/evidence.py run --pack <pack> --id PLAN \
  --note "spec and plan frozen before execution" -- cat <pack>/spec.md <pack>/test-plan.md
```

### 4. Preflight

Capture each check as a run with `--id PREFLIGHT`:

1. **Environment identity.** Query the server and database name of every
   connection (`SELECT @@SERVERNAME, DB_NAME()`, or `SELECT
   current_database(), inet_server_addr()` on Postgres). Compare them with the
   QA identifiers the user or repo config gave you; ask when you have none.
   Stop on production or any mismatch.
2. **Builds under test.** The version or commit of the job deployed in QA,
   and of the oracle system.
3. **Pinned inputs.** For each as-of date: the input snapshot or batch IDs,
   the price, FX, and reference-data versions, and input row counts.
4. **Before snapshot.** Row counts and control totals of the target table
   per as-of date, and of the tables the job must not touch.
5. **Frozen oracle.** Extract the oracle's output to CSV in the pack, or copy
   it into a scratch table in QA, before any comparison. The oracle can
   recompute during the day.

When preflight contradicts the plan (different build, missing as-of data),
record a deviation and ask before continuing.

### 5. Execute

Run the test cases in plan order, each command through `evidence.py`:

```bash
uv run <skill-dir>/scripts/evidence.py run --pack <pack> --id TC-07 \
  --note "parity 2026-06-30, full population" -- psql -f <pack>/queries/TC-07-parity.sql
```

- Save query text in `queries/` and run the file, so the query that produced
  a result is in the pack.
- Wrap pipes and redirects in `sh -c '...'` so the whole pipeline is recorded.
- Reconcile with SQL inside the database for large tables, or export both
  sides at the same grain and stored scale and run `reconcile.py` into
  `recon/<TC>/`. Its exit code is 1 when there are breaks.
- A run that failed for a test reason (wrong query, missing grant) stays in
  the pack. Fix the cause, rerun, and record why in the report.
- Stop and ask on anything outside the plan: an unplanned write, a changed
  environment identity, or a destructive step.

### 6. Investigate breaks

Give every break, and every one-signed pile of within-tolerance differences,
a category: as-of or timing, reference data, rounding (mode, point, scale),
population, logic defect in the change, oracle defect, input data quality, or
test error. Evidence for each is the smallest key that reproduces it and a
hand calculation from the spec.

- An explained break passes only when the spec says the behavior is intended
  or the user accepts it; record who accepted it and when.
- Call the oracle wrong only with an independent hand calculation and the
  user's agreement; that calculated value becomes the expected value.
- Log product defects in the report with severity, expected, actual, and the
  run that shows it.

### 7. Report and seal

Fill `report.md` from `assets/report.md`, citing the run for every result.
Choose the verdict:

- **PASS:** every test case executed and passed, no unexplained break, no
  open defect.
- **PASS WITH EXCEPTIONS:** as PASS, except documented breaks or deviations
  that a named person accepted.
- **FAIL:** any failed test case, open defect, or unexplained break.
- **BLOCKED:** some planned test cases could not run; name them and why.

Seal the pack last and zip it for attaching, then print the report's ticket
summary in chat with the `SHA256SUMS` hash and the zip's path:

```bash
uv run <skill-dir>/scripts/evidence.py seal --pack <pack>
cd <pack>/.. && python3 -m zipfile -c <ticket>.zip <ticket>/
```

Leave the sign-off block empty for the human reviewer and approver.

## Example

`/qa-analyst FEE-412`, where a new nightly job must reproduce the billing
engine's management-fee accrual. Intake finds the day-count rule unstated, so
step 2 asks three questions (ACT/365 or ACT/360, rounding per day or per
month, leap-day handling) and writes a spec with four rules and seven worked
examples. The approved plan has 14 test cases, including parity on
2026-01-31, 2026-02-28, and 2026-03-31. Preflight confirms `fees_qa` on
`sqlqa02` and build `3.8.1+a1b2c3d`. Parity on 2026-02-28 matches 48,109 of
48,112 rows; the three breaks are all −0.01 on `accrued_fee`, and a hand
calculation shows the new job rounds daily where rule R3 rounds monthly. That
is defect D-1, and the verdict is FAIL. The sealed pack and ticket summary go
to the user.

## Bundled resources

- `scripts/evidence.py` — **run** for every command whose output is evidence
  (`run`) and to write the checksum manifest (`seal`). `--help` has the flags.
- `scripts/reconcile.py` — **run** to reconcile two CSV extracts by key with
  exact decimal math. Exit 0 match, 1 breaks, 2 bad input. `--help` has the
  flags.
- `references/reconciliation.md` — **read** at step 3 and step 5: parity
  method, SQL templates, rounding traps, break categories, and write checks.
- `assets/spec.md`, `assets/test-plan.md`, `assets/report.md` — **copy** into
  the pack and fill; every section is required, write "none" rather than
  deleting one.
