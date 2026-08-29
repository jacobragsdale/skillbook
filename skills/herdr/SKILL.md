---
name: herdr
description: "Control Herdr, a terminal workspace manager for coding agents — create panes, tabs, workspaces, and worktrees, start agents in them, send messages or handoff packets to another agent, and read another agent's output. Use ONLY when the user explicitly asks for Herdr or explicitly asks to open a pane/tab/workspace, spin up another agent, or pass work or a message to another agent. Never invoke it merely because a task could benefit from parallelism, delegation, or a background terminal."
---

# Herdr

Herdr organizes terminals into workspaces, tabs, and panes, detects coding agents running inside panes, and exposes the live session through the `herdr` CLI.

## When to act — read this first

Act only on an explicit request. Qualifying asks look like:

- "use herdr to…", "open a pane/tab/workspace", "split this"
- "spin up another agent", "start a claude/codex over there"
- "pass this to the other agent", "send that agent a message", "ask the other agent what it found"
- "what's the other agent doing", "read that pane"

Do NOT create layout or agents on your own initiative. A task that *would* go faster in parallel is not a request. A long-running command is not a request. If you think a second agent or pane would help, say so in one line and let the user decide.

Never close, kill, or restart anything you did not create unless the user explicitly asks.

## Preflight

```bash
test "${HERDR_ENV:-}" = 1
```

If that fails, say you are not running inside Herdr and stop — do not control a session from outside it.

Herdr injects the caller's own context:

```bash
printf '%s\n' "$HERDR_WORKSPACE_ID" "$HERDR_TAB_ID" "$HERDR_PANE_ID"
```

## The binary is the authority

This file was written against **herdr 0.8.2**. Syntax moves. Print a group without a subcommand to get its current commands:

```bash
herdr agent      # list get read send-keys prompt rename focus wait attach start explain
herdr pane       # list current get layout neighbor split move close read run send-text send-keys wait-output zoom …
herdr tab        # list create get focus rename close
herdr workspace  # list create get focus rename close
herdr worktree   # list create open remove
```

Never run bare `herdr` for discovery — it launches or attaches the TUI. Do not probe a mutating nested command by omitting arguments; `herdr workspace create` is valid with defaults and will execute.

Most commands return JSON. Parse IDs out of responses; never guess them or read them off the sidebar.

## IDs and lifecycle states

Public IDs are opaque and stable: workspace `w1`, tab `w1:t1`, pane `w1:p1`. Closed IDs are not reused. A pane moved to another workspace gets a **new** workspace-qualified ID — after `pane move`, continue with `.result.move_result.pane.pane_id`.

Agent commands take a unique live agent name **or** the pane ID hosting it — not terminal IDs, not bare kind labels. Names match `[a-z][a-z0-9_-]{0,31}`, must be unique among live agents, follow the pane's current occupant, and clear when it exits.

| State | Meaning |
|---|---|
| `idle` | ready for input, and its tab has been seen in the focused UI |
| `done` | same idle state, after *unseen* background work finished |
| `working` | mid-turn |
| `blocked` | Herdr detected an approval or question UI |
| `unknown` | an agent is present but unclassified — **not** proof of completion |

CLI reads do not mark a tab seen; focusing it does.

### Herdr agents are not the same list as `ListAgents`

`herdr agent list` shows agents occupying Herdr panes. Claude Code's own `ListAgents` shows peer Claude sessions, which may include sessions in no Herdr pane at all, and omits non-Claude agents. When the user says "the other agent in this workspace", resolve it against `herdr agent list` filtered to `$HERDR_WORKSPACE_ID`, and say which one you picked if more than one could match.

## Discover before you build

```bash
herdr workspace list
herdr tab list --workspace "$HERDR_WORKSPACE_ID"
herdr pane list --workspace "$HERDR_WORKSPACE_ID"
herdr agent list
herdr pane layout --pane "$HERDR_PANE_ID"
```

## Creating layout

Match the primitive to what was actually asked. Default to a **sibling pane in the current tab, in the current working directory**. Do not create a tab, workspace, or worktree unless the user asked for that topology or a different location.

| User asked for | Use |
|---|---|
| another terminal / split / "next to this" | `pane split` |
| a separate tab for a different task | `tab create` |
| a separate project or context | `workspace create` |
| an isolated branch checkout | `worktree create` |

Geometry: split a **wide** pane `right`, a **narrow or tall** pane `down`. Avoid repeated same-direction splits that produce unusable slivers. Preserve the caller's cwd and leave the user's focus alone:

```bash
herdr pane split --current --direction right --cwd "$PWD" --no-focus
```

New pane ID is `.result.pane.pane_id`. Creation responses expose what you need next: `workspace create` returns `.result.workspace`, `.result.tab`, `.result.root_pane`; `tab create` returns `.result.tab` and `.result.root_pane`.

## Starting an agent

`agent start` requires an **existing** pane sitting at an interactive shell prompt with nothing in the foreground. It never creates or moves layout — split first.

```bash
herdr agent start reviewer --kind claude --pane <pane-id>
herdr agent start reviewer --kind claude --pane <pane-id> -- <native agent args>
```

Kinds include `claude`, `codex`, `gemini`, `cursor`, `copilot`, `opencode`, `amp`, `grok` and more — check `herdr agent start --help` for the live list. Use the kind the user named; default to `claude` only if they did not name one. Native agent arguments go after `--`.

Success returns only once Herdr detects the agent ready for input (30s default, `--timeout` up to 300000). If it returns `agent_not_ready` the name still works for `agent read` and `agent send-keys` — wait for idle before prompting.

## Passing messages to another agent

This is the highest-value use, and the easiest to get wrong.

### Send

```bash
herdr agent prompt <name-or-pane-id> "text" --wait --timeout 120000
```

`agent prompt` honors bracketed paste and sends the text followed by an encoded Enter. `--wait` alone waits for the first settled `idle`/`done`/`blocked` — do not restate those with `--until`. Use `--until` only for a state-specific wait, e.g. expecting an agent to come back and ask something:

```bash
herdr agent wait reviewer --until blocked --timeout 120000
```

`--wait` tracks **lifecycle state, not turns**: if the target is already working, the current turn ending may satisfy it.

### Multi-line packets

Quoting long text on the command line is where this breaks. Write the message to a file, then pass it:

```bash
herdr agent prompt <target> "$(cat /path/to/packet.md)"
```

Newlines survive — bracketed paste means the target receives one message, not one submission per line.

### Sending to a busy agent

A prompt to a `working` Claude Code session is **queued**, not dropped; the target shows "Press up to edit queued messages" and picks it up after its current turn. That is a fine way to hand off — but skip `--wait`, since it would return on the unrelated current turn. Confirm the text landed:

```bash
herdr agent read <target> --source recent-unwrapped --lines 30
```

A `blocked` target is rejected with `agent_blocked` before any input is sent. Inspect the dialog with `agent get` and `agent read`, then **ask the user** how to answer it — do not answer an approval prompt on their behalf.

If a prompt from a non-working state produces no observed lifecycle change within 5s, Herdr returns `agent_prompt_stalled` rather than hanging.

### Write handoff packets that stand alone

The receiving agent has **none** of your context — not your conversation, not your findings, not your working assumptions. A good packet states: the goal; the concrete facts it needs (commit SHAs, file paths, exact error text); what is explicitly out of scope; acceptance criteria; and whether to commit and push. Tell it to re-verify anything time-sensitive rather than trusting numbers you gathered earlier. If the repo has its own agent contract (`AGENTS.md`, `CLAUDE.md`), honor its rules — e.g. a one-mutating-task-at-a-time rule means telling the target to start only once its current work is settled and the tree is clean.

### Reading a reply

```bash
herdr agent get <target>
herdr agent read <target> --source recent-unwrapped --lines 120
```

Read sources: `visible` (viewport), `recent` (with soft wraps), `recent-unwrapped` (wraps joined — prefer for logs and transcripts), `detection` (the plain-text snapshot Herdr classifies on). Add `--format ansi` only when color is the evidence.

If raising `--lines` reveals nothing more, the agent is drawing on the terminal's **alternate screen** and those rows never entered scrollback — no line count recovers them. Fallback: ask the agent to write its full response as Markdown to a temp path and reply with only that path, then read the file. Use this only after a read has actually failed; do not bake it into the first prompt.

### Interactive controls

```bash
herdr agent send-keys <target> esc
herdr agent send-keys <target> ctrl+c
```

Keys are validated before any bytes are written.

## Running an ordinary command elsewhere

Use pane commands, not agent commands, for plain processes — servers, tests, logs.

```bash
herdr pane split --current --direction right --cwd "$PWD" --no-focus
herdr pane run <pane-id> "npm test"
herdr pane wait-output <pane-id> --match "Tests:" --timeout 120000
herdr pane read <pane-id> --source recent-unwrapped --lines 120
```

`pane run` sends command text and Enter atomically. `pane wait-output` searches the current snapshot immediately, so pre-existing output can match — use `--regex` for patterns, and note that omitting `--timeout` waits indefinitely.

## Safety

- `--no-focus` for background work unless the user asked to switch context.
- Always target `--current`, an explicit pane ID, or a unique agent name. Never rely on the UI-focused pane — it may belong to the user or another client.
- Do not close workspaces, tabs, panes, or sessions you did not create.
- Never run `herdr server stop` from an active session; it stops the server and every pane process.
- Never kill the main Herdr process. Use a named session (`herdr --session <name>`) for experiments needing an isolated server.
- Server errors are JSON on stderr with exit 1; CLI syntax errors exit 2.
- Do not paste secrets into another agent's pane — the text lands in that terminal's scrollback.
