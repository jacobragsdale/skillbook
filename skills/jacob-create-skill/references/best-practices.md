# Skill-writing best practices

Primary-source synthesis, verified 2026-07-18. House policy is called out as
house policy rather than attributed to the open specification.

## Contents

- Evidence before instructions
- Coherent scope
- Progressive disclosure
- Descriptions and the 250-character budget
- Calibrating control
- Scripts and resources
- Evaluation layers
- Target portability
- Maintenance
- Primary sources

## Evidence before instructions

Create a skill from evidence that a capable agent would otherwise lack:

- a completed task transcript or recorded demonstration;
- recurring corrections, failures, or wasted execution paths;
- project artifacts such as runbooks, schemas, issue history, code review,
  patches, or incident reports; or
- a representative baseline run without the skill.

Do not make the user restate evidence already present in the conversation or
repository. Extract an intent brief, propose answers, and ask only about gaps.
If no evidence exists, perform the task once without a skill before encoding it.

## Coherent scope

One skill should represent one coherent capability, like a well-named function.
The presence of "and" does not prove a split is needed: querying a database and
formatting the result may be one useful workflow. Split when parts have distinct
triggers, outputs, dependencies, owners, or useful independent lives.

Start narrow and consolidate only after task evaluations show that a broader
skill performs at least as well as its focused predecessors.

A skill is the wrong vehicle for a policy that must hold in every session —
auto-triggering is best-effort. See `placement-and-conflicts.md` for the
rules-vs-skills decision and for handling overlap with client defaults.

## Progressive disclosure

Use three loading tiers:

1. `name` and `description` — discovery metadata.
2. `SKILL.md` — core procedure loaded when invoked.
3. `scripts/`, `references/`, and `assets/` — used only when needed.

Keep `SKILL.md` under 300 lines as a house target and under the open standard's
500-line/5,000-token recommendation. Link references directly from `SKILL.md`
and state when to read each one. Avoid reference-to-reference chains. Give any
reference over 100 lines a table of contents.

## Descriptions and the 250-character budget

The first sentence (~80 characters) is the hard routing window — Cursor
truncates injected descriptions there — and 250 characters is the total house
budget; per-client numbers are tabulated in `frontmatter.md` ("Routing windows
by client"). Put the concrete job and top trigger keywords in that first
sentence, then `Use when ...` intents, symptoms, formats, and relevant error
text — not the internal workflow.

Write in third person: the text is injected into the system prompt, and
inconsistent point of view breaks discovery. Phrase it as a directive trigger —
"Use when(ever) the user …" plus an "even if they don't explicitly mention
<domain>" clause — because models undertrigger skills, and directive phrasing
measurably outperforms passive summaries (roughly 20–50% activation for
passive descriptions vs ~100% for directive ones in published measurements).
For high-frequency domains, add an anti-trigger sentence ("Not for …") so the
skill doesn't fire on adjacent work. Only the description drives triggering:
keywords added to the body have zero measured effect.

Separate description evaluation from task evaluation:

- Minimum: three should-trigger messages and three near-misses, judged twice —
  against the name and first sentence only, then against the first 250
  characters. Persist the set in `evals/trigger_queries.json`.
- Auto-triggered skill: run those prompts through each target client and inspect
  whether it actually loads `SKILL.md`. A non-trigger on a trivially handled
  one-step ask is expected behavior, not a description failure.
- High-value auto-triggered skill: use roughly 20 balanced queries, three runs
  per query, and a fixed 60/40 train/validation split.

Real prompts vary in formality, explicitness, detail, typos, and whether the
relevant task is buried inside a longer workflow. Negative cases should share
vocabulary but need a different capability.

## Calibrating control

Match instruction form to the observed failure:

| Need | Effective form |
|---|---|
| Fragile, ordered operation | Exact command or low-parameter script |
| Preferred pattern with variation | Default plus observable escape condition |
| Context-dependent judgment | Heuristics and the reason they matter |
| Repeated omission | Checklist |
| Exact output shape | Template with required fields |
| Non-obvious environment fact | Prominent gotcha |

Avoid vague nuance such as "unless it matters." State the default, the condition
that changes it, and the allowed alternative. Prefer a clear default over a menu
of equal options.

## Scripts and resources

Bundle a script when the agent repeatedly reconstructs deterministic logic or
when reliability matters. Scripts should be non-interactive, self-contained or
explicit about dependencies, documented by `--help`, and fail with actionable
messages. Use structured output when another step consumes the result.

State whether the agent should run or read every bundled file. Execute each
script with `--help` and a representative input. Verify rule names, flags,
configuration keys, API fields, and similar identifiers against the real tool;
handle version drift deliberately.

For this repository, Python scripts use `uv` plus PEP 723. Outside this
repository, follow the target project's runtime conventions and declare
non-obvious requirements in `compatibility`.

## Evaluation layers

Test four different things rather than treating validation as one gate:

1. **Structure:** frontmatter schema, naming, placeholder removal, local
   references, script packaging, and target metadata.
2. **Triggering:** should-trigger and near-miss prompts for auto invocation.
3. **Task output:** two or three realistic cases with expected outputs and at
   least one edge case, run in fresh contexts with the skill and a baseline.
4. **Human quality:** usefulness, clarity, visual quality, and unexpected
   behavior that mechanical assertions cannot capture.

For a new skill, the baseline is no skill. For an improved skill, snapshot and
run the previous version. Add objective assertions after inspecting the first
outputs so they are observable rather than hypothetical. Read execution traces,
not only final artifacts: a correct result reached through wasteful exploration
still reveals a skill problem.

Use one run per case initially for a low-risk personal skill. Repeat runs and
track pass rate, time, and tokens for high-stakes, side-effecting, auto-triggered,
or distributed skills. Test coexistence with the surrounding skill set when
routing collisions are plausible.

## Target portability

The agentskills.io core and vendor extensions are different profiles:

- Strict core accepts only the standard frontmatter fields.
- Cursor and Claude Code support additional frontmatter fields.
- Codex keeps invocation policy and UI/tool metadata in `agents/openai.yaml`.

Do not assume unknown frontmatter is harmless: a client may ignore it, while a
strict validator may reject it. Choose targets during discovery and validate
each claimed target separately. Read `frontmatter.md` for the current matrix.

## Maintenance

After use, capture only verified surprises or explicit corrections in
`LEARNINGS.md`. Fold recurring or user-confirmed lessons into the relevant step,
then remove the sidecar entry. Preserve the existing name, invocation policy,
and frontmatter while editing unless the user requested a change. Prune prose on
every revision because skills accrete.

## Primary sources

- https://agentskills.io/specification
- https://agentskills.io/skill-creation/best-practices
- https://agentskills.io/skill-creation/evaluating-skills
- https://agentskills.io/skill-creation/optimizing-descriptions
- https://cursor.com/docs/skills
- https://code.claude.com/docs/en/skills
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- https://github.com/anthropics/skills/tree/main/skills/skill-creator
  (also shipped as a plugin in anthropics/claude-plugins-official)
- https://developers.openai.com/codex/skills
- Measured triggering evidence: directive vs passive descriptions (650-trial
  study, 20.6x odds ratio) —
  https://medium.com/@ivan.seleznov1/why-claude-code-skills-dont-activate-and-how-to-fix-it-86f679409af1;
  forced-eval hook 84% vs 20% baseline —
  https://scottspence.com/posts/how-to-make-claude-code-skills-activate-reliably
