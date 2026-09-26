---
name: e2e-audit
description: "Live end-to-end audit: every state and edge case, tested on real DBs and APIs. Use when the user runs /e2e-audit or wants an app exhaustively tested live or on its deployed instance, even if they don't say e2e."
disable-model-invocation: true
---

# E2E audit

Test a running application end to end against its real database, its real
external APIs, and its deployed instance when there is one. Model every state
and edge case first. Then create each state through the app, check what the
user sees, what was stored, and what side effects fired, and fix each defect
as you find it.

These rules replace the default "run the test suite and summarize" behavior:

- **Live only.** No mocks, stubs, fakes, recorded responses, or substitute
  databases. The repo's own test suites are leads for recon, never evidence.
  An external API runs in whatever mode the target is configured with; use
  its test or sandbox mode when the target offers one.
- **Three layers or it didn't pass.** A case passes only when the interface,
  the stored state, and the side effects plus server log all match. Read
  stored state from the database, or read it back through the API when there
  is no database access. "Saved" over a 500 in the log, or over a row that
  was never written, is a failure.
- **Evidence or it didn't happen.** Every status in the matrix points at
  captured output in `evidence/<case>/`. Never mark a case from memory or
  from reading code.
- **No rerun until green.** A case that gives different results across
  identical runs is a defect: run it five times, record the ratio, and treat
  it as a race. Retesting after a fix is a new run, not a rerun.
- **Tag and ledger every write.** Every record the run creates carries the
  run ID where a text field allows it, and every write goes in `ledger.md`,
  so cleanup can find it.
- **Every row ends with a status.** Nothing is skipped for time. A case you
  cannot run is `blocked` or `excluded`, with the reason and what would
  unblock it.
- **Run straight through.** Don't stop for approval between steps. Stop only
  for the production guard, and ask once, at preflight, for what you cannot
  obtain yourself.

## Production guard

Treat the target as production when it serves real users, holds live payment
keys, or you cannot prove otherwise. On production, tagged writes that
cleanup can undo need no approval. Ask first, one action at a time, before
you:

- move real money or use live payment credentials;
- send email, SMS, push, or webhooks to any recipient the run doesn't control;
- change or delete data the run didn't create;
- send traffic beyond one user's rate (load, stress, rate-limit probing);
- deploy, restart, or induce a failure in production infrastructure;
- make any write that cleanup cannot undo.

On other targets, the first two items still need asking. Redact credentials,
tokens, and cookies from evidence, and mask real users' personal data
captured on production.

## Run folder

Create `~/e2e-audits/<app>-<run-id>/`, outside any repo. The run ID is `e2e`
plus UTC `MMDDHHMM` (`e2e09251430`), short enough to fit in names and email
addresses.

```text
brief.md     recon brief
matrix.md    state matrix, updated after every case
ledger.md    every write: time, case, target, identifier, cleanup status
evidence/    one folder per case: requests, responses, screenshots, SQL and results, log excerpts
report.md    final report
```

`matrix.md` is the run's memory. Update it after every case, because a long
run outlives the context window.

## Workflow

### 1. Recon

Read the argument after `/e2e-audit`: a URL or environment name picks the
target, a path or feature name limits the scope, and other text is a focus.
Pick the target; the first match wins:

1. The target the user named.
2. The deployed instance the repo points to: deploy config, CI deploy jobs,
   README, env files, reverse-proxy config.
3. A local stack from the repo's own compose file or dev command, with
   production's database engine and external services. When local config
   swaps one out (SQLite for Postgres, a fake payment client), run the real
   one in a container if config allows; otherwise record the gap.

Write `brief.md`, 60 lines or fewer:

- app kind, stack, and interfaces (web UI, API, CLI, TUI, jobs, webhooks, queues);
- target, environment class, and the evidence for that class;
- each data store and how you reach it (where the credentials live, a
  tunnel, an admin CLI); never the secret itself;
- server logs and how to read them from a given timestamp;
- external integrations, each with its mode (live, test, sandbox, local);
- roles, and how to get an account for each one;
- the feature inventory: every route, endpoint, command, job, and webhook,
  taken from a machine-readable source where one exists (OpenAPI document,
  router table, `--help` tree, scheduler config) rather than from skimming
  files;
- oracles: docs, specs, tickets, validators, database constraints, UI copy;
- what you can induce: which dependencies you can stop, slow, or fail, and how;
- repo conventions (`AGENTS.md`, `CLAUDE.md`); build, test, deploy commands.

### 2. Model every state

"Every possible state" means every state class, not every value: each value
of every dimension at least once, pairs across dimensions that interact in
one flow (role × record state, input × state), and the full product for
access control and for paths that move money or delete data.

In a single message, start one subagent per lens (`lifecycle`, `access`,
`input`, `failure`, `interface`) so they run in parallel, each with this
prompt:

```text
Read <abs path to this skill>/references/lenses.md. Your prompt is its
"Shared preamble" section followed by its "<lens>" section. Follow both
exactly, and reply only in the preamble's output format.

Placeholders: REPO_PATH=<abs path> · LENS=<lens> · TARGET=<target and class> · SCOPE=<scope> · FOCUS=<focus or none>

Recon brief:
<brief.md>
```

In Claude Code, use the `general-purpose` agent type. Skip a lens that can't
apply (`access` for an app with no identities) and say so.

Merge the replies into `matrix.md`:

1. Drop duplicates across lenses, keeping the more specific case.
2. Fill gaps yourself: every inventory item appears in at least one row,
   every entity state has a row that enters it and one that leaves it, and
   every lens's "Inventory gaps" item is covered.
3. Keep the lens IDs (`LIF-`, `ACC-`, `INP-`, `FAI-`, `IFC-`) and never
   renumber. New rows get the next free number in their area.
4. Mark each case `excluded` that the production guard or the brief rules
   out, with the reason.

Use this table; a table-driven case keeps its value grid in its evidence
folder:

```markdown
| ID | Given | When | Then (interface · stored · effects) | Oracle | Risk | Status | Evidence |
```

Statuses: `todo`, `pass`, `fail`, `fixed` (retested live and passing),
`fixed-unverified`, `question`, `blocked`, `excluded`. Post a one-paragraph
summary in chat (cases per area, high-risk count, exclusions) so the user can
interrupt, then continue.

### 3. Preflight

Save each check's output in `evidence/PREFLIGHT/`:

1. **Identity.** Hit the target's health or version endpoint, query the
   database's identity (`SELECT current_database(), inet_server_addr()` on
   Postgres, `SELECT @@SERVERNAME, DB_NAME()` on SQL Server), and record the
   deployed build. When it differs from `HEAD`, fixes will need a deploy.
   Stop when the identity contradicts the brief.
2. **Access.** One read against every store, log source, and interface the
   matrix uses.
3. **Baseline.** Row counts of every table the app writes, queue depths, and
   the log's current timestamp.
4. **Identities.** Create one tagged account per role through the app's own
   signup or admin flow (`e2e09251430-admin@example.com`). A state that needs
   a received email (verification, reset, invite) uses a local mail catcher
   or plus-addressing into an inbox the user controls. Never invent
   addresses at real domains.
5. **Ask once.** In one batch, ask only for what you cannot obtain:
   credentials, a role you cannot create, an inbox. Cases still missing one
   are `blocked`.

### 4. Execute

Run the core happy path first and fix it before anything else when it
fails. Then go area by area, highest risk first. For each case:

1. Arrange the Given state through the interface. Write to the database
   directly only when the interface cannot reach the state (an expired
   token, a record from before a migration), and say so in the row. Log
   every write in the ledger.
2. Act through the real interface.
3. Check all three layers. Read the server log from the case's start
   timestamp; any error or unhandled exception fails the case, even when the
   interface looked right.
4. Save evidence, update the row, and continue.

Drive each interface the way its users do:

- **Web UI:** the harness's browser tool when it has one, otherwise a
  Playwright script: `uv run --with playwright python <script>`, after
  `uv run --with playwright playwright install chromium`. Type and click;
  never set values or submit forms through JavaScript. Capture a screenshot,
  console errors, and failed requests for every case.
- **API and CLI:** real auth and the built binary; capture status, headers,
  and body, or stdout, stderr, and exit code. Capture a TUI's `tmux` pane.
- **Jobs, queues, webhooks:** trigger them the way production does (the
  scheduler's command, a real enqueue, the provider's test-event resend) and
  wait for completion. Never call the handler function directly.

**Gotcha:** on hosts Playwright doesn't support (Arch, among others), its
browser dies with `error while loading shared libraries`. Run the script in
the official image instead, tag matching the package version:

```bash
docker run --rm --network host --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/w -w /w \
  mcr.microsoft.com/playwright/python:v<version>-noble \
  sh -c 'pip install -q --user --break-system-packages playwright==<version> && python <script>'
```

Fire concurrency cases at the same moment (parallel requests released
together, two browser contexts), never one after the other. Induce failures
only where the brief marks them inducible: stop a local dependency
container, point config at a closed port, or use the provider's documented
test triggers (decline cards, error amounts).

When execution reveals a state the model missed (an unfamiliar error page,
an unmodeled status value), add a row and test it. Never delete a row.

### 5. Fix as found

When a case fails:

1. Save the evidence before changing anything. Reproduce once; when the
   result differs, apply the five-run flaky rule instead.
2. Fix the root cause where every caller routes through, not this path only.
3. Fix now only when the oracle makes the expected behavior clear and the
   fix is small: one reviewable change, no new dependency, no schema, public
   API, or stored-format change. Otherwise leave the row `fail` with a
   proposed fix. When the right behavior is a product decision, mark it
   `question`. Either way, continue.
4. Add a regression test at the level the repo's suite already covers.
5. Make the target run the fix. Rebuild and restart a local target. Deploy
   to a staging target with the repo's deploy command. On production, ask
   before the first deploy; the user may approve deploys for the rest of
   the run. Until the retest, the row is `fixed-unverified`.
6. Retest the case live, then rerun every passed case whose flow touches
   the changed code.
7. Commit per fix only when the repo's instructions ask for commits.

### 6. Clean up

Delete every ledger entry, newest first, through the app's own delete flow
when one exists. Then delete what remains in every table the run wrote,
filtering only on the run ID or ledger identifiers. Compare row counts with
the baseline and explain every difference (real-user activity, soft-deleted
rows, audit logs). Stop only the local containers you started.

### 7. Report

Write `report.md` in this format and post it in chat. Every section is
REQUIRED; write "None." for an empty one:

```markdown
## E2E audit — <app> @ <target> (<production | staging | local>)

Run <run-id>, <start>–<end> UTC, build <commit or version>. Verdict: <PASS | FAIL | INCOMPLETE>
Coverage: <n> cases — <p> pass, <f> fixed, <u> fixed-unverified, <o> fail, <q> question, <b> blocked, <x> excluded.

### Defects
| Case | Severity | Symptom | Root cause | Status | Fix |
|------|----------|---------|------------|--------|-----|

### Questions
- <case>: <the decision needed, with the options>

### Blocked and excluded
| Case | Reason | What would unblock it |
|------|--------|-----------------------|

### Cleanup
Tagged rows remaining: <n>. Baseline differences: <each, explained>.
Side effects cleanup cannot undo: <emails sent, third-party records>.

Run folder: <path>
```

Verdict, first match wins: **FAIL** on any `fail`, `fixed-unverified`, or
`question`; **INCOMPLETE** on any `blocked` or `todo`; otherwise **PASS**.

## Example

`/e2e-audit` on a FastAPI, Postgres, and React invoicing app. Recon finds
`fly.toml`, 312 real users, and live Stripe keys, so the target is
production. The lenses return 263 cases; the merge leaves 220, with 11
excluded (no Stripe outage on production). ACC-09 shows user B reading user
A's invoice by ID; the agent adds an owner filter and a regression test, the
user approves the deploy, the retest returns 404, and the access cases pass
again. INP-22 shows "Saved" over a truncation error in the log and no row;
the fix needs a migration, so it stays `fail`. Cleanup deletes 1,488 tagged
rows. Verdict: FAIL, 1 open defect, 4 fixed.

## Bundled resources

- `references/lenses.md` — the shared preamble and five lens prompts. Lens
  subagents **read** it at step 2. Read it yourself when filling coverage
  gaps during the merge.
