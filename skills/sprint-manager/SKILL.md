---
name: sprint-manager
description: "Jacob's sprint hub over ADO tickets, PRs, and herdr agent tabs via agent-cli. Use when the user asks what needs them, what's next, to catch up or sync tickets, plan tomorrow, or start a ticket in a tab — even if they don't say sprint."
---

# Sprint manager

Jacob's sprint hub, run from its own herdr tab. It says what needs Jacob now,
keeps Jacob's ADO tickets in step with the real work, and starts agents in the
right tab. The agents in the tabs do the work, and Jacob talks to them there.
Scope is Jacob's own tickets unless someone else is named.

## Rules

Jacob's decisions (2026-10-07). They override general habits, and the herdr
skill's "act only on explicit request" only where Start a ticket says.

1. **Snapshot first, every request.** Run it before answering, even if one ran
   earlier in the conversation: work moves between messages. Keep no notes or
   state files; ADO, herdr and git are the record.
2. **Evidence, not process.** A ticket may have no PR, one, or several across
   repos; a branch may lack the id; a tab may belong to no ticket. A gap is a
   question for Jacob, never an error, and never a guess written to ADO.
3. **Nothing changes without a yes.** Every ADO write, agent start and prompt
   waits for Jacob's yes to that exact change. Show the change first.
4. **Closing is Jacob's call, one ticket at a time.** Set Resolved or Closed
   only for a ticket Jacob names in reply to a question about closing it. A
   yes to a batch never closes anything.
5. **Keep ADO quiet.** Prefer a tag or a link to a comment. A comment is one or
   two plain sentences: no headings, bullets, or summaries of the work.
   Acceptance criteria and QA tickets may be detailed when Jacob asks.
6. **Hands off the agents.** Never answer an agent's question or approval,
   send it keys, close or move panes, run git in a tab's folder, or start a
   second agent in a folder. Name the tab and let Jacob go there.

## Snapshot

**Run** from any folder:

```bash
uv run <this-skill-dir>/scripts/snapshot.py
```

It prints one JSON object (`--help` documents every key) built from herdr
(every tab but this one), git (each tab's branch and uncommitted files) and
agent-cli (Jacob's current-sprint tickets, their links, Jacob's PRs).

- `sources`: anything not `ok` failed. Say so in one line (agent-cli exit 3
  means "run `agent-cli doctor`") and carry on with the rest.
- `conventions`: Jacob's team rules: agent kind, tags and when they apply,
  the done rule, where analysis runs, ticket-to-repo hints. When it is `null`,
  say so once and offer to copy `assets/conventions.md` to
  `~/.config/sprint-manager/conventions.md` for Jacob to edit; until then use
  that asset's defaults.
- `tabs[]`: `free` and `why` say whether a folder can take a new ticket.
  `screen` is a blocked or finished agent's last lines. `ticket` is null when
  nothing ties the tab to a ticket.
- `tickets[]`: open tickets, highest priority first. `flags` are the
  mechanical findings Catch up turns into proposals.

## What needs me, what's next

Answer with this board, sections in this order, empty ones left out, one line
per entry:

```text
SPRINT 42 · 2 working days left · mine: 4 closed, 1 resolved, 9 active, 5 new
NEEDS YOU
  1. t-platform/billing-api  48201  blocked: approve ./scripts/migrate.sh --env dev?
  2. t-data/etl-jobs  48190  finished: says PR 1190 is ready for review
  3. PR 1175 (48185, infra-tf)  Sam Lee waiting, 2 open threads
FREE TABS → NEXT
  t-platform/deployment → 48233 Stand up a staging deployment for ledger-sync (P1)
OUT OF SYNC  6 tickets: say "catch up" to review the fixes
NO EVIDENCE  48212 Update the ETL failure runbook (9 days quiet) — still real?
NEXT: answer billing-api's migration question; 48201 is P1 and stalled on it.
```

Order NEEDS YOU by what waiting costs:

1. Blocked agents: stalled until Jacob answers. Summarize the question from
   `screen`.
2. Finished agents (`done`): their output waits for Jacob's review.
3. Jacob's active PRs with open threads, or a `waiting` or `rejected` vote.
4. Idle agents on a ticket branch with no PR: probably waiting for Jacob.
5. Tabs whose `ticket` is null but whose branch or title fits an open ticket:
   ask whether it is that ticket.

FREE TABS → NEXT pairs each free tab with the highest-priority New ticket
that belongs in its repo (conventions hints, then the ticket's title and
area). Never suggest a ticket for a busy tab. List New tickets for the
analysis workspace there too. OUT OF SYNC counts tickets with any flag except
`no_evidence`. NEXT is one line: the single action that unblocks the most,
said plainly. Jacob asked to be pushed; push.

## Catch up

When Jacob asks to catch up, sync or fix tickets:

1. Number one proposal per ticket, combining its changes, each with evidence:

   | Flag | Proposal |
   |---|---|
   | `new_with_work` | New → Active |
   | `pr_not_linked:<pr>` | link it: `agent-cli ado pr link <pr> --workitem <id>` |
   | `all_prs_merged` | add the conventions tag for merged work, unless a later tag is on it already |
   | `blocker_closed:<id>` | remove the `blocked` tag |

2. Ask two questions apart from the numbered list, since neither is a batch
   change:
   - **No evidence** (`no_evidence`): "No branch, PR or tab: <id title>, …
     Done, dropped, or still real?" If a tab with a null `ticket` fits one,
     say which.
   - **Close?** For each ticket that is Resolved, or carries the
     ready-to-deploy tag, with every PR merged: "Is <id> in production?
     Close it?" (rule 4).
3. Ask "Apply 1–N?" Jacob may answer "all", "1-3, 5", or amend one.
4. Apply exactly what was approved: one `workitem update` per ticket with
   `--if-rev <rev>` from the snapshot, plus any `pr link`. A rev refusal means
   the ticket changed: re-run the snapshot and re-propose that ticket.
5. Report one line per change: done, or the error.

**`--tags` replaces every tag.** Send the full list: the snapshot's tags, plus
or minus the change. For a ticket tagged `blocked`, adding `ready-for-qa`
is `--tags "blocked,ready-for-qa"`; removing `blocked` from a ticket with no
other tags is `--tags ""`.

Example:

```text
1. 48215 Invoice PDF time zone: New → Active, link PR 1182 (its branch 48215-invoice-tz, not linked)
2. 48170 Duplicate charge on retry timeout: add ready-for-qa (PR 1160 merged)
3. 48205 ledger-sync alerts to PagerDuty: remove blocked (48199 is Closed)
Apply 1–3?
No evidence: 48212 Update the ETL failure runbook (9 days), 48228 Redis spike —
t-data/cache-spike is on spike-redis-cache with no ticket; is that 48228?
Close? 48160 is ready-to-deploy and PR 1150 merged 6 days ago. In production?
```

## Start a ticket

When Jacob says "start 48233", "kick off …", or picks a suggestion:

1. Read it: `agent-cli ado workitem get <id> --fields id,type,title,state,rev,description,acceptance_criteria,url`.
2. **Pick the tab.** Use the repo Jacob named, else the conventions hints and
   the ticket's text; ask when two repos fit. Analysis with no repo goes in a
   new folder `<id>-<slug>` at the conventions' analysis location.
3. **Check it is free** (`tabs[].free`). If not, give `why` and offer the next
   ticket for a free tab instead. No tab for that repo or analysis folder:
   offer `herdr tab create --workspace <id> --cwd <folder> --label <name> --no-focus`
   in the matching domain workspace, and run it only on yes.
4. **Write the packet** from the template below to a temp file. Show it with
   the target tab and ask "Send to <tab> and set <id> Active?" (Active only if
   it is New).
5. **On yes:**
   - No agent in the tab: `herdr agent start wi<id> --kind <Kind> --pane <pane> -- <Args>`
     with Kind and Args from conventions. On `agent_not_ready`, read
     `herdr agent read <pane> --source visible` and tell Jacob what it shows
     (often a folder-trust question for Jacob to answer in the tab), then
     stop.
   - An idle agent already in the tab: ask whether to send `/clear` first, so
     the old conversation does not leak into the new ticket.
   - Send: `herdr agent prompt <pane> "$(cat <packet-file>)"`, then check
     `herdr agent get <pane>` shows it `working`.
   - Then `agent-cli ado workitem update <id> --state Active --if-rev <rev>` if
     it was New.
6. Tell Jacob which tab to watch.

Packet template; the tab's agent has none of this conversation:

```text
Ticket <id> (<type>): <title>
<url>
Repo <repo>, branch <id>-<slug> from an up-to-date <default branch>.

<description>

Acceptance criteria:
<acceptance criteria, or: none written; ask Jacob before assuming any>

How to work:
- Check out <default branch>, pull, create the branch. Commit as you go and push the branch.
- When done, open a PR linked to the ticket:
  agent-cli ado pr create --repo <repo> --source <branch> --title "<title>" --workitem <id>
- Do not change the ticket's state, tags or comments; Jacob's hub does that.
- Stop and ask here whenever a decision is Jacob's.
```

For analysis, replace the first two "How to work" lines with: "Write findings
to findings.md in this folder. No branch or PR."

## Plan tomorrow, replan

Same snapshot. Give an ordered list of three to six items for the next working
day (from `now`: Friday plans Monday): finish what is started first
(blocked, finished, in review), then P1 New tickets whose tab will be free,
then the rest. Add the pace: open tickets against working days left. Keep the
plan in ADO, not in a file: offer priority changes (`--priority`) or moving
what won't fit to the next sprint (`--iteration @next`), and apply only on yes.

## Other questions

Answer from agent-cli with the narrowest call (`agent-cli search <words>`
finds commands). Default to Jacob's tickets; other people only when named:
"has Alex started anything?" is
`agent-cli ado workitem list --assignee Alex --iteration @current --state New --fields id,title`.

## Before you answer

- The snapshot ran this turn.
- Every write had Jacob's yes; nothing was closed without a named, per-ticket yes.
- Every comment is at most two sentences.
- herdr was only read, except an approved start, prompt or tab.

## Bundled resources

- `scripts/snapshot.py`: **run** at the start of every request.
- `assets/conventions.md`: **copy** to `~/.config/sprint-manager/conventions.md`
  when the snapshot's `conventions` is null and Jacob agrees.
