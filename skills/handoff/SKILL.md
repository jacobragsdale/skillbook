---
name: handoff
description: "Write a handoff document so a fresh agent session can continue this work. Use when the user wants to hand off, pause, or move work to a new session or agent \u2014 even if they only say the context is getting long."
license: "MIT, adapted from mattpocock/skills. See LICENSE.txt"
---

# Handoff

Write a document that lets a fresh agent, with none of this conversation,
pick up the work where it stands. If the user passed an argument, it says
what the next session will focus on: tailor the document to that and drop
what that session won't need.

## Workflow

1. **Read the live state** instead of writing it from memory. For each repo
   the work touched: its path, branch, `HEAD` commit, and
   `git status --short`. Also note running servers or processes, worktrees,
   and scratch directories the next agent needs or must clean up.
2. **Write the document** with these sections, each REQUIRED ("none" when
   empty):
   - **Goal**: what the user wants, in their words where possible, and what
     done looks like.
   - **State**: what is finished, what is in progress, and the live state
     from step 1.
   - **Decisions**: choices made and why, including approaches tried and
     rejected, so the next agent doesn't retry them.
   - **Next steps**: in order, the first one concrete enough to start
     without asking.
   - **Waiting on the user**: open questions and approvals.
   - **Out of scope**: what the next agent must leave alone.
   - **Pointers**: specs, plans, tickets, PRs, commits, files, and logs, by
     path or URL.
   - **Suggested skills**: skills the next agent should load, by name.
3. **Save it** to the OS temp directory (`$TMPDIR`, else `/tmp`) as
   `handoff-<repo or topic>-<YYYYMMDD-HHMM>.md`, never in the workspace.
4. **Reply** with the absolute path and a prompt the user can paste into the
   new session.

Rules for the content:

- Point at artifacts that already hold the detail (specs, plans, tickets,
  commits, diffs) instead of copying them.
- Copy verbatim what the next agent can't cheaply re-derive: exact error
  text, commands that worked, measured numbers with when they were measured.
  Mark anything time-sensitive to re-check.
- Redact secrets and client or account data. Name where a credential lives
  (env var, file, keychain item), never its value.

## Example

User: "context is getting long, hand this off — next session finishes the
retry fix". The reply:

```text
Handoff written to /tmp/handoff-ledger-sync-20261022-2310.md

Paste into the new session:
Read /tmp/handoff-ledger-sync-20261022-2310.md and continue the work it
describes. Check its State section against the repo before you change
anything.
```
