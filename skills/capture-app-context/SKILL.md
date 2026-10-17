---
name: capture-app-context
description: "Capture a repo's ops context: environments, logs, databases, AKS, jobs, APIs. Use when the user runs /capture-app-context or wants agents to know where an app runs and what it touches, even if they only say make this repo self-explanatory."
disable-model-invocation: true
---

# Capture app context

Write `docs/app-context.md`: the operational facts an agent cannot read from
the code and that are slow to rediscover — where the app runs, where its logs
go, which databases and outside systems it touches — plus an `agent-cli`
command to re-check each fact that changes. Other skills (`e2e-audit`,
`qa-analyst`, `perf-tune`) read this file instead of rediscovering it, so the
path is fixed.

## Hard rules

- **Read-only.** Run only `agent-cli` commands whose `--help` says `Read.`
  Never pass `--reveal`, and never run `sql query run`, `kv secret get`,
  `k8s secret get`, `aks cluster connect`, a login, or a kube context switch.
- **Name the target on every call** (`--cluster`, `--namespace`, `--conn`,
  `--env`, `--instance`) from repo evidence. A default that happens to answer
  says nothing about this app.
- **Never write into the file:** secret values, connection strings, tokens,
  log lines, query rows, or values that change run to run (pod names, image
  tags, replica counts, error rates). Vault and secret *names* are fine.
- **Private repos only.** If the remote is GitHub, check
  `gh repo view --json visibility`. If the repo is public or you cannot tell,
  ask whether to sanitize, keep the file untracked, or stop.

## Workflow

### 1. Read what exists

If `docs/app-context.md` exists, this is a refresh: run each Live checks
command, fix what changed, and keep user-stated facts unless evidence
contradicts them. Then read `AGENTS.md`, the README, pipeline YAML,
Helm/Kustomize/manifests, IaC, and per-environment config
(`appsettings.*.json`, `environment*.ts`, `.env.example`, settings modules).

### 2. Find leads with `rg -l`

List paths only; read the matched files yourself. A match is a lead, not a
fact, and a miss proves nothing.

```bash
rg -l -i 'datadog|serilog|ilogger|applicationinsights|structlog'               # logs
rg -l -i 'dbcontext|sqlconnection|dapper|sqlalchemy|exec |create (procedure|view)'  # databases
rg -l -i 'httpclient|httpx|requests\.|axios|openapi|swagger'                   # outside APIs
rg -l -i 'kind: *(cronjob|job)|airflow|hangfire|quartz'                        # jobs
rg -l -i 'service ?bus|event ?hub|kafka|redis|blob|key ?vault|secretkeyref'    # messaging, storage, secrets
```

### 3. Confirm live with agent-cli

Run `agent-cli` to see which domains are set up, then confirm each fact the
repo names. Use `agent-cli search "<what>"` when unsure of the command.

| Fact | Command |
|---|---|
| Cluster scope | `agent-cli aks cluster list --fields name,k8s_scope` |
| Workload | `agent-cli k8s deployment list <name> --cluster <scope> --namespace <ns> --fields name,ready,images` |
| Logs reach Datadog | `agent-cli dd log-count list --service <svc> --env <env> --since 1d` (counts, never lines) |
| APM service name | `agent-cli dd service list --env <env>` |
| DB object owned elsewhere | `agent-cli sql object get <schema.name> --conn <conn> --fields kind,columns` |
| Job | `agent-cli airflow dag get <dag> --instance <name> --fields schedule_text,owners,file` |
| Secret names | `agent-cli kv secret list --vault <vault> --fields name` |
| Pipeline | `agent-cli ado pipeline list --repo <repo> --fields name,last_run.result` |

Exit 3 means the domain is not set up: mark the fact unconfirmed, name the
domain in the report, and move on without setting it up.

### 4. Ask only for gaps

Send one message with at most three groups. Show what you found in each so
the user can correct it. Ask for identifiers, locations, and owners; never
for credentials or data.

### 5. Write the file

Use this template, 80 lines or fewer. Include only facts the code does not
show: never list the routes, tables a query touches, or anything else `rg`
finds in a minute.

```markdown
# <app> — operational context

Reviewed <YYYY-MM-DD> at commit <short-sha>. Refresh with /capture-app-context.

## Environments

| | QA | Production |
|---|---|---|
| Runs on | AKS `<scope>`, namespace `<ns>`, deployment `<name>` | … |
| Database | connection `<conn>` (`<server>/<database>`) | … |
| Logs | Datadog `service:<svc> env:<env>` | … |
| Deploys from | pipeline `<name>` | … |
| Secrets | vault `<vault>` | … |

## Depends on

- <system>: <what for>. Client in `<path>`; owner <team>; contract `<path or URL>`.
- `<schema.object>`: defined in `<repo>/<path>`, not this repo.
- `<job>`: <schedule>, defined in `<path or DAG id>`.

## Live checks

- Workload and image: `agent-cli k8s deployment list …`
- Errors today: `agent-cli dd log-count list … --status error --since 1d`

## Unknowns and conflicts

- <fact>: <what is known, the competing sources, who decides>.
```

Leave a fact unmarked only when repo and live evidence agree. Append
`(per <person>, <date>)` to facts the user stated and `(unconfirmed)` to
facts no live check reached. When sources conflict, list both under
Unknowns; do not pick one.

Then add this line to the repo's `AGENTS.md`, creating the file if needed:

```text
Operational context (environments, logs, databases, jobs, outside systems): read docs/app-context.md before operational, data, or incident work.
```

### 6. Check and hand off

1. Run every Live checks command once; fix or remove any that fail.
2. Run `rg -n -i 'password|pwd=|secret=|token=|connection ?string|accountkey|sig=|bearer ' docs/app-context.md`
   and remove every hit that is a value rather than a name.
3. Leave both files uncommitted unless the user or the repo's `AGENTS.md`
   says to commit.
4. Report the path, the unknowns, and the checks that could not run.

## Example

**Input:** `/capture-app-context` in a .NET billing worker repo.

**Output:** Reads `azure-pipelines.yml`, `charts/billing-worker/values-qa.yaml`,
`values-prod.yaml`, and `appsettings.*.json`. Confirms the deployment on both
cluster scopes with `k8s deployment list`, the Datadog service with
`dd log-count list`, and that `ledger.usp_PostLedger` exists but is not
defined in this repo with `sql object get`. Asks one question: who owns the
ledger API. Writes a 48-line `docs/app-context.md` and adds the pointer line
to `AGENTS.md`.
