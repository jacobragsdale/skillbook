---
name: polish
description: "Multi-agent polish pass: small, verified app improvements, no new features. Use when the user runs /polish or asks to tidy up, harden, or do a quality pass on an app, even if they don't say polish."
disable-model-invocation: true
---

# Polish

Review an app through seven lenses in parallel, verify each finding against the
code, present a ranked plan of small improvements in chat, and implement only
the items the user approves. A polish pass never adds features.

These rules replace the default "fix what you find" behavior: make no edits
before the user approves specific plan items, and don't write the plan to a
file.

## What counts as small

An item belongs in the plan only when its fix fits in one reviewable commit
(about 100 changed lines or fewer), adds no dependency, breaks no public API,
CLI, config key, file or wire format, or schema, and adds no user-visible
capability. Real problems that need more go under **Too big for polish**, one
line each, so the user can see them.

## Workflow

### 1. Parse the scope

Read the argument after `/polish`:

- A path limits the review to that subtree.
- Lens names (`correctness`, `resiliency`, `performance`, `ux`, `ergonomics`,
  `simplification`, `security`) run only those lenses.
- Any other text is a focus that every lens gets.
- With no argument, review the whole repository with all seven lenses.

### 2. Recon (do this yourself, not in a subagent)

Build a brief of 40 lines or fewer so the lens agents don't each rediscover the
same things:

- App kind (CLI, TUI, web, API, library), language, framework, and entry points.
- Hot paths: what runs per request, frame, keystroke, row, poll tick, or at
  startup.
- Repository conventions from `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING`, and
  linter or formatter config, plus any house-standards skill that fits the stack.
- The build, test, lint, and type-check commands. **Run each once now** and put
  a pass/fail summary, including every failure and warning, into the brief.
  Lens agents rely on this and don't rerun the suite.
- Uncommitted changes (`git status`), so nobody mistakes work in progress for
  existing code.

### 3. Fan out

In a single message, start one subagent per lens so they all run in
parallel. Give each one this prompt, with the placeholders and brief filled in:

```text
Read <this skill's dir>/references/lenses.md. Your prompt is its "Shared
preamble" section followed by its "<lens>" section. Follow both exactly, and
reply only in the preamble's output format.

Placeholders: REPO_PATH=<abs path> · LENS=<lens> · SCOPE=<scope> · FOCUS=<focus or none>

Recon brief:
<the brief from step 2>
```

Use an absolute path to `lenses.md`, because subagents don't know where this
skill is installed. In Claude Code, use the `general-purpose` agent type:
lenses need to run read-only checks, and `Explore` only locates code without
reviewing it. Skip `ux` for libraries and headless APIs and say you did.

### 4. Verify every finding

The subagents' output is a set of leads, not the plan. For each finding:

1. Open the cited lines and confirm the evidence is real and current.
2. Confirm the trigger can actually happen: trace callers and inputs.
3. Confirm the fix meets **What counts as small** and doesn't break a repo
   convention.

Drop findings that fail a check. Merge duplicates across lenses, keep each
lens tag, and use the best-evidenced version of the fix. When two lenses
conflict (a performance cache against a simplification deletion), keep one and
note the trade-off. Move findings that are real but too large to **Too big for
polish**. Count what you dropped and report that count in the plan's final line;
don't list dropped items.

### 5. Present the plan in chat

Number the items continuously across groups so the user can approve them with
ranges. Sort each group by impact descending, then effort ascending:

- **Do first:** H impact, plus any high-confidence correctness or security fix.
- **Worth doing:** M impact.
- **Optional:** L impact.

Use this format. Every field is REQUIRED:

```markdown
## Polish plan — <repo> (<scope>)

<one-sentence verdict on overall state>

### Do first
1. **<imperative title>** `[correctness]` · S · H
   `src/cache.rs:88` — <evidence → consequence, one sentence>
   Fix: <change, one sentence>. Verify: <test or check>.

### Worth doing
…

### Optional
…

### Too big for polish
- <one line each, or "None">

<n> findings from 7 lenses; <m> dropped after verification; <k> merged.

Which items should I implement? ("all", "1-5, 8", or "none")
```

Stop and wait for the answer, unless the user already approved implementation
in their request ("polish it and fix what you find"). In that case, post the
plan anyway, then implement every item in it.

### 6. Implement the approved items

With 10 or fewer approved items, work through them yourself in plan order.
With more, split them into batches whose files don't overlap and give each
batch to a subagent in an isolated worktree (`isolation: "worktree"` in Claude
Code), all in parallel. Each batch prompt lists its items with the plan's
evidence and fix, names the files the other batches own, and says to leave its
changes uncommitted. When they finish, bring each worktree's `git diff` into
the main checkout with `git apply --3way` and resolve any overlaps yourself, leave the result unstaged (`git reset`), then remove the
worktrees and their branches.
Every item, whether yours or a subagent's, follows these steps:

1. Make the change. Stay inside the item. If it turns out bigger than **What
   counts as small**, or needs a decision the plan didn't cover, revert it,
   mark it skipped with the reason, and continue.
2. Add the regression test the item names when the item is a behavior fix.
3. Run the item's Verify step and the tests that cover the touched code. If
   they fail and one focused attempt doesn't fix it, revert the item and mark
   it skipped.
4. Commit per item only when the repository's instructions ask for commits
   (for example `AGENTS.md`). Otherwise leave the changes uncommitted.

After the last item, run the full build, test, and lint commands from recon.
Compare the results against the recon baseline and report: each item as done
or skipped (with the reason), any new failures, and the test results in both
states.

## Example

`/polish src/api security` on a Flask service. The recon brief notes pytest
passing and ruff clean. The security agent reports three findings. Verification
drops one, because its "unsanitized" path is already validated by a Pydantic
model at `src/api/schemas.py:14`. The plan presents two items: `subprocess.run`
built with an f-string from a query parameter (S, H), and a bearer token logged
at debug level (S, M). The user replies "1". The agent switches the call to an
argument list, adds a test with `; rm -rf` in the parameter, runs pytest, and
reports item 1 done and item 2 not approved.

## Bundled resources

- `references/lenses.md` — the shared preamble and the seven lens prompts. Each
  lens subagent **reads** it at step 3. You don't need to read it unless you
  are changing a lens.
