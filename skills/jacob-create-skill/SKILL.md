---
name: jacob-create-skill
description: Create, improve, or validate agent skills (SKILL.md folders). Use whenever the user wants to make a new skill, fix one that isn't triggering, review, refactor, or scaffold a skill, add scripts to one, or fold LEARNINGS.md notes in — even if they don't say "skill" but want a reusable agent workflow, checklist, or SOP packaged for reuse.
metadata:
  author: jacob
---

# Creating and improving agent skills

Build skills from the agentskills.io core format plus deliberate target-specific
extensions for Cursor, Claude Code, and optionally Codex. Do not call a skill
strictly spec-conformant when its frontmatter contains vendor extensions. A skill
is a folder whose name matches the `name:` in `SKILL.md`, optionally with
`scripts/`, `references/`, `assets/`, and product metadata alongside.

**Before doing anything else, read `LEARNINGS.md` next to this SKILL.md.**
Entries there are corrections from real use and override anything below.

## Step 1 — Confirm an evidence-backed intent brief

Mine the current conversation, repository, transcripts, examples, and existing
artifacts before asking questions. Draft answers yourself, ask only about
unresolved high-impact gaps (one to three questions at a time), then show the
user the completed brief for confirmation before scaffolding:

1. **Job and boundary.** State the coherent capability in one short sentence.
   Split it only when parts have different triggers, outputs, dependencies, or
   useful independent lives; the word "and" alone does not require a split.
2. **Evidence.** Ground the skill in at least one successful task transcript or
   demonstration, recurring correction or failure, authoritative project
   artifact (runbook, schema, issue, review, patch), or baseline task run. If
   none exists, do the task once without a skill and capture the useful pattern.
3. **Targets and scope.** Record the intended clients, personal or project
   location, and explicit or automatic invocation. This repo defaults to
   automatic invocation (the model triggers the skill from conversation);
   Codex uses separate metadata. If the behavior must hold in *every*
   session — a standing policy rather than an on-demand procedure — read
   `references/placement-and-conflicts.md` first: it may belong in an
   always-on rule, or a rule-plus-skill pair, rather than a skill alone.
4. **Triggers and near-misses.** Capture realistic user wording, indirect
   phrasings, and adjacent requests that must use a different skill or no skill.
5. **Inputs and sources of truth.** Identify files, APIs, schemas, examples,
   existing conventions, runtime dependencies, and freshness requirements.
6. **Output and definition of done.** Specify the artifact or response shape,
   allowed side effects, required verification, and observable success criteria.
7. **Edges and safety.** Identify a boundary case, likely failure, permissions,
   destructive or external actions, and behavior the skill must never surprise
   the user with.
8. **Resources and freedom.** Put deterministic or repeatedly reconstructed work
   in scripts; stable detail in references; reusable output material in assets;
   and judgment in prose. Calibrate each step independently: fragile operations
   get exact guardrails, while context-dependent work gets a default and a clear
   decision rule.

## Step 2 — Scaffold

Run the scaffolder rather than hand-creating files, so the folder name, the
frontmatter, and the learnings loop start correct:

```bash
uv run <this-skill-dir>/scripts/init_skill.py <skill-name> --dir <skills-root>
```

New skills default to automatic invocation — no `disable-model-invocation`
field — so the model triggers them from conversation via the description.
Pass `--explicit-only` when the skill should only ever run via `/skill-name`
(orchestrator sub-steps, dangerous operations). Pass `--strict-core` to omit
vendor frontmatter, and `--codex` to add Codex metadata (with `--explicit-only`
it writes the explicit-invocation policy sidecar).

Edit the scaffolded files in place, section by section. Do not replace the full
`SKILL.md`; preserve its frontmatter and re-read the frontmatter after drafting.

## Step 3 — Draft the SKILL.md

House rules, and why:

- **Front-load the first sentence; keep the whole description under 250
  characters.** Cursor shows the model only ~80 characters in cloud sessions
  and trims variably locally, so the first sentence must name the capability
  and top trigger keywords on its own. Claude Code shows up to 1,536 and
  Codex budgets 2% of context, so 250 total is safe everywhere (the per-client
  numbers are tabulated in `references/frontmatter.md`). Follow with
  "Use when …" listing concrete intents, symptoms, formats, and error text.
  Keep workflow steps out of the description.
- **Write the description as a directive trigger in third person.** Models
  undertrigger skills, so be pushy: "Use when(ever) the user …" plus an
  "even if they don't explicitly mention <domain>" clause for adjacent
  intents, and an anti-trigger sentence ("Not for …") when the domain is
  high-frequency. Never first person — the text is injected into the system
  prompt, and inconsistent point of view breaks discovery. Fix undertriggering
  in the description only: keywords in the body have zero measured effect on
  triggering.
- **Keep the body under 300 lines** (house target; the open-spec recommendation
  is under 500 lines and 5,000 tokens). Move conditional detail to a directly
  linked reference and state exactly when to read it. Give references over 100
  lines a table of contents.
- **Only write what moves the agent off its defaults.** A capable agent
  already knows how to write Python and read docs. Every line should encode
  something it would otherwise get wrong. Delete the rest.
- **Imperative voice, one excellent worked example.** "Run X, then check Y"
  beats "the agent should…". Keep one compact input→output example in the body;
  keep behavioral test cases outside it.
- **Replace vague nuance with decision rules.** Avoid "unless it matters."
  State the default, the observable condition that changes it, and the allowed
  alternative. Explain why when the task needs contextual judgment.
- **Match the guidance form to the failure type.** Agent skips a rule → hard
  prohibition, not "prefer". Agent produces the wrong shape → exact template
  with REQUIRED fields, not a prohibition list. Agent forgets things → a
  checklist, not prose reminders.
- **Default automatic invocation.** Skills in this repo are model-invocable:
  the description is the router, so it must earn the trigger (Step 5). Add
  `disable-model-invocation: true` only when a skill must never fire on its
  own — an orchestrator sub-step or a destructive operation — and say why in
  the brief.
- **Purge contradictions; state precedence.** When a skill overrides a client
  or harness default (default git behavior, default test style), say so
  explicitly in the body — "these rules replace …" — because models burn
  reasoning reconciling conflicting instructions instead of picking one.
  When a skill overlaps an always-on rule, another skill, or a client
  default, read `references/placement-and-conflicts.md`.

### Scripts and tool-specific facts

For skills in this repository, every bundled Python script is a self-contained
single file with PEP 723 dependency metadata, runnable through `uv` — no venv
or `pip install` prose in the skill body:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx"]
# ///
```

Rules for skill scripts:

- Run with `uv run scripts/<name>.py`. Manage dependencies with
  `uv add --script scripts/<name>.py <pkg>`, never by editing prose.
- `argparse` with `--help` text good enough that SKILL.md doesn't need to
  restate the flags — the body says *when* to run it, `--help` says *how*.
- Fail loudly: nonzero exit codes and error messages that say what to fix.
- In SKILL.md, state for each script whether the agent should **run** it or
  **read** it as reference — agents guess wrong otherwise.
- Run every script with `--help` and at least one representative input before
  finishing. When instructions encode rule names, flags, config keys, API
  fields, or other tool-specific identifiers, execute the real tool once to
  reconcile them. Handle unknown identifiers with an actionable error or a
  documented graceful fallback because tool versions drift.

For a project-local skill outside this repository, follow that project's
runtime and packaging conventions. Record non-obvious runtime requirements in
`compatibility`; do not assume `uv` is installed everywhere.

Before using frontmatter beyond `name` and `description`, read
`references/frontmatter.md`. Validate strict core, Cursor, Claude Code, and
Codex behavior separately instead of assuming unknown fields degrade safely.

## Step 4 — Validate

Run the house profile, or select a target-specific profile:

```bash
uv run <this-skill-dir>/scripts/validate_skill.py <path-to-skill-folder>
uv run <this-skill-dir>/scripts/validate_skill.py --profile core <path>
```

Fix every error. Address or consciously accept each warning. Validation must
reject unfinished scaffold placeholders, verify target-specific frontmatter
types, resolve real local references, and check bundled Python headers. Then run
the scripts and tool-specific checks from Step 3; static lint is not execution.

## Step 5 — Trigger test

Write six realistic user messages: three that should trigger the skill (varied
phrasing, explicitness, and detail) and three near-misses that share vocabulary
but need something else. Judge each twice: against **only the name and first
sentence** (~80 chars — what Cursor shows the model), then against **the first
250 characters** (other clients). Show message → expected → verdict and revise
by general category, not by copying failed-query keywords. Record the final
set in the skill's `evals/trigger_queries.json` so the validator checks it on
every revision.

For an explicit-only skill, treat this as catalog and future-auto-trigger
quality; do not claim automatic invocation was tested. For an auto-triggered
skill, run the messages through the target client and inspect whether it loaded
`SKILL.md`. Agents often skip skills for tasks they can trivially handle
alone, so a non-trigger on a trivial one-step ask is expected behavior, not a
description failure — make most should-trigger messages substantive while
still varying complexity. For high-value or distributed skills, expand to
roughly 20 balanced queries, run each three times, and keep a held-out
validation split.

## Step 6 — Forward-test output quality

Triggering and correctness are separate. Create two or three realistic task
cases with prompts, input files when needed, and a human-readable expected
output. Include at least one boundary or ambiguous case. Record the cases in
`evals/evals.json` (`{skill_name, evals: [{id, prompt, expected_output,
files}]}`) so the validator checks them on every revision.

Run each case in a clean context with the skill and against a baseline: no skill
for a new skill, or a snapshot of the previous version when improving one.
After the first outputs, add objective assertions only for mechanically
verifiable qualities; use human review for style, usefulness, and visual quality.
Compare final artifacts and execution traces. Remove instructions that cause
wasted paths, and iterate until the skill materially improves the baseline.

For low-risk personal skills, one run per case is enough initially. For
auto-triggered, high-stakes, side-effecting, or broadly distributed skills,
repeat runs, record time/tokens when available, and check coexistence with the
other skills likely to be installed.

## Step 7 — Wire the learnings loop

Every skill you create ships with a `LEARNINGS.md` (the scaffolder seeds it)
and wires the loop at both ends of the body. Near the top — instructions late
in a body are the least reliably followed — the first section opens with this
exact line:

```markdown
If `LEARNINGS.md` next to this SKILL.md has entries, read them first — they
override the instructions below.
```

("next to this SKILL.md", never "in this skill's folder": the agent's working
directory is usually another repo, and not every client tells the model where
the skill lives.) The body then ends with this exact block:

```markdown
## Improving this skill

After use, if the user corrected you or the outcome surprised you, append one
dated line to `LEARNINGS.md` next to this SKILL.md:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
```

## Improving an existing skill

When asked to improve a skill (or to "fold learnings"):

1. Read its `SKILL.md` and `LEARNINGS.md`.
2. Snapshot the current skill outside its folder for the Step 6 baseline.
3. Preserve the existing directory name, `name`, invocation policy, and other
   frontmatter unless the user explicitly asked to change them. Edit in place.
4. Fold entries that recur or were explicitly user-confirmed into the body,
   in the section where the mistake happened. Delete each folded entry.
5. Delete stale or speculative entries — a lesson that never recurred and
   can't be tied to a real failure is noise.
6. Cut body lines that aren't pulling weight; skills accrete.
7. Re-run Steps 4–6 before finishing.

## Bundled resources

- `scripts/init_skill.py` — **run** to scaffold a new skill folder.
- `scripts/validate_skill.py` — **run** to lint core or target-specific
  frontmatter plus these house rules.
- `evals/evals.json` and `evals/trigger_queries.json` — **read** when testing
  this skill; they cover output behavior and the six-message routing minimum.
- `references/best-practices.md` — **read** when unsure about a design choice
  (evidence, scope, control, evaluation, token budgets, sources).
- `references/frontmatter.md` — **read** before using any frontmatter field
  beyond `name`/`description` or adding Codex metadata, and for per-client
  routing windows and Cursor reliability gotchas.
- `references/placement-and-conflicts.md` — **read** when a capability must
  hold in every session, when a skill overlaps a rule or another skill, or
  when it contradicts a client default (rules-vs-skills, precedence).

## Improving this skill

After use, if the user corrected you or the outcome surprised you, append one
dated line to `LEARNINGS.md` next to this SKILL.md:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
