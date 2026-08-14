---
name: jacob-create-skill
description: Create, improve, or validate agent skills (SKILL.md folders). Use whenever the user wants a new skill, trigger fix, review, refactor, scaffold, or bundled script — even if they don't say "skill" but want a reusable agent workflow, checklist, or SOP.
metadata:
  author: jacob
---

# Creating and improving agent skills

Build skills from the agentskills.io core format plus deliberate target-specific
extensions for Cursor, Claude Code, and optionally Codex. Do not call a skill
strictly spec-conformant when its frontmatter contains vendor extensions. A skill
is a folder whose name matches the `name:` in `SKILL.md`, optionally with
`scripts/`, `references/`, `assets/`, and product metadata alongside.

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
   artifact (runbook, schema, issue, review, patch), or successful task run. If
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

Run the scaffolder rather than hand-creating files, so the folder name,
frontmatter, and section structure start correct:

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
- **Apply the default-behavior test to every rule as you draft and revise.**
  Ask: "Would a capable model in the target harness already behave this way by
  default, or does it need this guidance to start doing so?" If it already
  would, delete the rule. Keep only guidance backed by an observed miss, a
  user- or project-specific choice, a harness conflict, or a fragile operation;
  state the smallest delta needed to change the behavior.
- **Imperative voice, one excellent worked example.** "Run X, then check Y"
  beats "the agent should…". Keep one compact input→output example in the body.
- **Replace vague nuance with decision rules.** Avoid "unless it matters."
  State the default, the observable condition that changes it, and the allowed
  alternative. Explain why when the task needs contextual judgment.
- **Match the guidance form to the failure type.** Agent skips a rule → hard
  prohibition, not "prefer". Agent produces the wrong shape → exact template
  with REQUIRED fields, not a prohibition list. Agent forgets things → a
  checklist, not prose reminders.
- **Default automatic invocation.** Skills in this repo are model-invocable:
  the description is the router, so it must earn the trigger. Add
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

## Improving an existing skill

When asked to improve a skill:

1. Read its `SKILL.md` and inspect the evidence behind the requested change.
2. Preserve the existing directory name, `name`, invocation policy, and other
   frontmatter unless the user explicitly asked to change them. Edit in place.
3. Apply confirmed corrections in the section where the behavior occurs;
   remove stale or speculative instructions that lack evidence.
4. Cut body lines that aren't pulling weight; skills accrete.
5. Re-run Step 4 before finishing.

## Bundled resources

- `scripts/init_skill.py` — **run** to scaffold a new skill folder.
- `scripts/validate_skill.py` — **run** to lint core or target-specific
  frontmatter plus these house rules.
- `references/best-practices.md` — **read** when unsure about a design choice
  (evidence, scope, control, token budgets, sources).
- `references/frontmatter.md` — **read** before using any frontmatter field
  beyond `name`/`description` or adding Codex metadata, and for per-client
  routing windows and Cursor reliability gotchas.
- `references/placement-and-conflicts.md` — **read** when a capability must
  hold in every session, when a skill overlaps a rule or another skill, or
  when it contradicts a client default (rules-vs-skills, precedence).
