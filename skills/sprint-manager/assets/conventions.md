# Sprint manager conventions

The sprint-manager skill reads this file on every run. It holds what is specific
to this team and machine. Edit it freely; plain prose works.

## Agents

- Kind: copilot
- Args:

`Kind` is the herdr agent kind started in a free tab (`herdr agent start --help`
lists them). `Args` go after `--`, for example `--model <id>`.

## Tags

| Tag | Apply when | Remove when |
|---|---|---|
| blocked | Waiting on a person, team or system outside my control. Add a one-sentence comment naming what. | The blocker clears. |
| ready-for-qa | Every PR on the ticket is merged and the change is in the QA environment. | QA passes (then ready-to-deploy) or fails. |
| ready-to-deploy | QA passed, or no QA is needed; waiting on the production release. | Never: closing the ticket ends it. |

## Done

I move tickets to Resolved or Closed myself, usually once the change is in
production. Ask me per ticket.

## Where work runs

- One herdr workspace per domain, one tab per repo, one agent per folder, no
  git worktrees.
- Analysis with no repo: workspace `analysis`, one folder per ticket at
  `~/work/analysis/<id>-<slug>/`. Split panes are fine there.
- New environments and deployments: the `deployment` repo.

## Ticket to repo hints

- (area path, keyword or service) → (repo)
