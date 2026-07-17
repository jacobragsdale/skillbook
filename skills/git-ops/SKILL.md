---
name: git-ops
description: "Jacob's solo git workflow: work directly on main, small frequent commits, push to GitHub after every commit, end every task with a clean working tree. Use when committing, pushing, deciding whether to branch or open a PR, finishing a task with uncommitted changes, or untangling a dirty or diverged repo."
---

# Git operations

All of Jacob's repos are personal, single-developer projects. There is no
review gate, no team to coordinate with, and no reason for branches to exist.
The goal state after every task: on `main`, working tree clean, everything
pushed to GitHub.

## Rules

- **Stay on main.** Never create a branch or open a PR unless Jacob
  explicitly asks for one. If you find the repo on another branch, say so
  before doing anything — don't silently merge or switch.
- **Commit at every working checkpoint**, not one blob at the end. A
  checkpoint = a coherent change that leaves the repo working (tests/hooks
  pass). Subject line: imperative, ≤ 72 chars; add a body only when the
  *why* isn't obvious from the diff.
- **Push after every commit.** `git push` immediately; don't batch pushes
  for later. If the remote rejects (work from another machine),
  `git pull --rebase` then push. Never force-push `main`.
- **Pre-commit hooks are the gate.** Fix what they flag; never
  `--no-verify`. If a hook is chronically slow or wrong, fix the hook in
  its own commit — don't bypass it.
- **Don't rewrite pushed history.** Amending or rebasing an unpushed commit
  is fine; once it's on GitHub it's immutable.
- **No parking lots.** Never leave work in a stash or as stray untracked
  files at the end of a task. Build artifacts and caches get gitignored (in
  the same commit that introduces them); everything else gets committed or
  explicitly handed back to Jacob with a reason.
- **Secrets never enter history.** `.env*` (except `.env.example`) stays
  gitignored per the `python-standards` skill. If a secret lands in a
  commit, stop and tell Jacob before pushing — pushed secrets must be
  rotated, not just deleted.

## End-of-task checklist

Run before declaring any task done:

- [ ] `git branch --show-current` → `main`
- [ ] `git status` → clean (no staged, unstaged, or untracked files)
- [ ] `git log origin/main..main --oneline` → empty (everything pushed)

## Example

A task touches three files across two concerns (a bug fix, then a config
tweak it uncovered):

```bash
git add src/sync.py tests/test_sync.py
git commit -m "Fix off-by-one in partition date range"
git push
git add pyproject.toml
git commit -m "Raise coverage ratchet to 84"
git push
git status   # clean — task can end
```

Not: one `git commit -am "updates"` at the end, unpushed.

## Improving this skill

Before executing, read `LEARNINGS.md` in this skill's folder — entries there
override the instructions above. After use, if the user corrected you or the
outcome surprised you, append one dated line to `LEARNINGS.md`:
`- YYYY-MM-DD: <what happened> → <what to do instead>`. Do not edit SKILL.md
directly; lessons are folded in deliberately, not on the fly.
