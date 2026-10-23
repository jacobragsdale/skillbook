---
name: retro
description: "Session retro: turn agent mistakes into checks, tools, and skill fixes. Use when the user runs /retro or wants agents to stop repeating a mistake, even if they don't say retro."
disable-model-invocation: true
license: "MIT, merged from mattpocock/skills (retro) and cursor/plugins pstack (correct). See LICENSE.txt"
---

# Retro

Find the mistakes and friction agents hit in a session, or keep repeating in
a repo, and change the environment so the next agent can't hit them. Propose
first; change nothing until the user approves items.

Agents skip instructions; they can't skip a check that fails. So every fix
starts as high up the fix levels in step 3 as it will go, and words (docs,
agent rules) come last, only for judgment calls no check can catch.

## 1. Gather evidence

Read the argument after `/retro`: a transcript path, a topic, `repo`, or
nothing (the current session).

- **A session.** Digest it instead of reading the raw transcript, which is
  mostly tool output:

  ```bash
  uv run <this-skill-dir>/scripts/session_digest.py --latest --cwd "$PWD"
  ```

  This finds the newest Claude Code or pi session that ran in this
  directory; `--list 5` shows others to pick from. The current session's
  digest ends with this retro request, so ignore its tail. Open the raw
  transcript at a digest line number only when a line needs its full
  context.
- **A repo** (argument `repo`, or the user says agents keep doing X): also
  read recent `git log` (reverts, commits that undo agent work), PR review
  comments where you can reach them, the repo's `AGENTS.md` / `CLAUDE.md`,
  and code comments that explain a workaround.

Look for: user corrections and redirections ("no", "stop", "I said"), tool
errors, the same call retried, long hunts for a file or fact, work redone or
reverted, expensive calls (the digest footer lists the largest results and
verbatim repeats), and skills that should have fired and didn't, or fired
and misled.

## 2. Classify

Group the findings into classes, each with evidence: a quoted correction
with its digest line number, a commit SHA, or a `file:line`. Rank classes by
how often they happen and what they cost (time, tokens, a wrong result). A
class seen twice outranks a one-off.

Tag each class with the lens that found it:

| Lens | Ask |
|---|---|
| Checks | Could a lint, type, test, or CI check have caught it? Read the repo's existing check commands first: a check that exists but isn't wired into pre-commit or CI is the finding. A repo with no guardrail at all is a finding. |
| Navigation | Did the agent hunt for a file or fact that a pointer in `AGENTS.md` or a clearer name would have handed it? |
| Information access | Was something it needed out of reach: logs, a read-only database view, a service, a CLI? |
| Tool economy | Which calls were expensive, and what flag, script, or trimmed output would make them cheap? |
| Skills | Should a skill have fired (fix its description) or did it give wrong guidance (fix its body)? |
| Instruction bloat | Which lines in `AGENTS.md`, `CLAUDE.md`, or a skill change nothing the model wouldn't do anyway, or belong in a check? |

## 3. Choose the fix level

For each class, take the highest level that works, and say why the levels
above it don't:

1. **Structure.** Remove the wrong way: one owner per piece of state, one
   supported way per task, internals hidden so the wrong import fails, dead
   code and stale examples deleted so no agent copies them.
2. **Types.** Make the bad state unwritable.
3. **A check whose error names the fix.** A lint rule, script, hook, or CI
   job: "use `ledger.post()`, not `db.insert()`" beats "forbidden". When the
   bad pattern is already common, fail only on new occurrences.
4. **A test** that fails when the behavior breaks and passes when only
   internals change.
5. **Words.** Agent instructions, only for judgment calls. Put them where
   the agent reads them at the decision (a skill, a doc `AGENTS.md` points
   to), not in an always-loaded file.

A rule that already existed and was broken anyway has failed as words: move
it up a level instead of rewording it.

Route each fix to where it lives:

- Specific to one repo: that repo.
- A skill's guidance: the skill's canonical folder `skills/<name>/` in the
  skillbook repo, following `jacob-create-skill`. Never the installed
  `skillbook-*` copy.
- Every session, everywhere: the global instructions (`~/.claude/CLAUDE.md`,
  `~/.pi/agent/SYSTEM.md`).

## 4. Propose and wait

Present the plan in this format. Every field is REQUIRED:

```markdown
## Retro: <session or repo>

Evidence: <which session digest, git range, review comments>.

1. **<imperative fix title>** · <lens> · level: <structure|types|check|test|words> · lands in: <repo path | skill | global>
   Evidence: <quote or SHA, with digest line>. Seen <n>×. Cost: <what it cost>.
   Why not higher: <one line; "top level" at level 1>.
   Proof: <how you will show the fix fails on the real past mistake>.

Which items should I apply? ("all", "1, 3", or "none")
```

Stop and wait for the answer.

## 5. Apply approved items

One commit per item. Prove each new check, type, or test fails on the real
past mistake: reproduce the mistake (check out the bad commit in a scratch
worktree, or re-apply the bad edit), run the check, see it fail with an
error that names the fix, then restore. Run the check with the same command
CI runs. A skill edit must pass `validate_skill.py` and goes through
skillbook's publish steps. Report each item as applied with its proof, or
skipped with the reason.

## Example

`/retro` after a session where the user twice said "edit it in skillbook,
not the installed copy". The digest shows `Edit` calls on
`~/.claude/skills/skillbook-polish/SKILL.md` at lines 41 and 88. skillbook's
`AGENTS.md` already forbids this, so words failed. Item 1 is a check: a
Claude Code `PreToolUse` hook that rejects writes under
`~/.claude/skills/skillbook-*` with "edit skills/<name>/ in skillbook
instead". Proof: the hook rejects the exact path from line 41. The digest
footer also shows a 40,000-character `git log -p` result at line 63: item 2,
tool economy, changes the command the skill suggested to `git log --stat`.

## Bundled resources

- `scripts/session_digest.py`: **run** at step 1. `--help` covers picking a
  session, harness, and output size.
