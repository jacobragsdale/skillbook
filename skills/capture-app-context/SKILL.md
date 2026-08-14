---
name: capture-app-context
description: "Capture repo app context: logs, APIs, databases, AKS, jobs, and deployments. Use when users want agents to discover or document operational surroundings—even if they only ask to make a repository self-explanatory. Not for code-only docs."
---

# Capture application context

Discover the operational facts that source code alone cannot prove, then create
or refresh a repo-scoped skill that makes those facts safely retrievable.

## Workflow

### 1. Establish the repository boundary

- Resolve the repository root and read its agent instructions, documentation,
  remotes, and existing skill directories.
- Reuse the repository's established project-skill location. If none exists,
  use `.agents/skills/<repo-name>-context/`. Keep one canonical copy; do not
  create divergent Cursor-, Claude-, or Codex-specific copies.
- If a context skill already exists, update it in place. Preserve verified
  facts and custom collectors unless newer evidence supersedes them.
- Determine whether the repository is public before recording internal host,
  cluster, database, or monitoring identifiers. If visibility is unknown, ask
  before committing sensitive topology.

### 2. Discover before asking

Run `scripts/scan_repo_context.py` against the repository and write its JSON to
a temporary path. Treat matches as leads, never as facts. Inspect the matched
files plus code, configuration, IaC, pipelines, Helm/Kustomize, migrations,
SQL, runbooks, and existing docs.

Follow resolvable references into already-authenticated, read-only systems.
Use repository configuration to identify the exact Azure subscription, AKS
cluster, namespace, observability workspace, API specification, or database;
do not guess a target from the current CLI context. Never log in, change a
context, deploy, restart, scale, execute a job, query business rows, or mutate
an external system as part of discovery.

Build an evidence matrix for:

- QA and production log sources, files or streams, central sink, dashboard or
  query entry point, retention when known, and correlation fields;
- every external API, its purpose, environment-specific authority, client call
  sites, authentication mechanism name, contract source, timeout, and retry
  behavior;
- database calls mapped to tables, views, functions, and stored procedures,
  including authoritative definitions and whether each call reads or writes;
- AKS subscription, resource group, cluster, namespace, workload kind/name,
  containers, labels, services/ingress, and current pod names;
- CronJobs, Jobs, or externally scheduled work and the authoritative location
  of each definition;
- applicable queues/topics, storage, caches, configuration and secret-store
  names, deployment pipelines, alerts, runbooks, ownership, and on-call path.

Record `not applicable` when evidence proves a domain does not exist. Record
`unknown` when it remains unresolved; absence of a scanner match proves
nothing.

### 3. Ask only for gaps

After discovery, ask for only the unresolved fields. Group questions into at
most three coherent areas per message and include the evidence already found
so the user can correct it. Ask for locations, identifiers, definitions, and
owners—not credentials, tokens, connection strings, production data, or copied
log contents.

For pod names, explain that names rotate. Request the stable workload and label
selector if they are unknown, then capture current pod names only as timestamped
examples.

### 4. Create the repo-scoped context skill

Read `references/context-skill-contract.md` before authoring. Create a concise
`SKILL.md`, source-attributed reference material, and one narrow collector per
live authority that must be refreshed. Follow the target repository's language
and tooling conventions for generated scripts.

Collectors must be read-only, require an explicit environment, use explicit
targets rather than ambient defaults, bound output and time, emit to stdout or
a caller-selected temporary file, and fail with an actionable message. They
must not contain secrets, perform login, silently switch Azure or Kubernetes
contexts, query business data, or overwrite the reference automatically.

Do not create a generic command runner or a placeholder collector. Generate a
collector only after the exact system, read-only interface, and target are
known. Reconcile every flag and field against the installed tool's help or an
authoritative contract, then run `--help` and a safe representative call when
access is available.

### 5. Verify and hand off

- Trace every factual statement to repository evidence, live read-only output,
  or a clearly labeled user statement.
- Mark each fact `verified-live`, `verified-repo`, `user-provided`, `inferred`,
  `unknown`, or `not-applicable`, with source and UTC verification time.
- Search the generated skill for credentials, tokens, connection strings,
  copied production rows, and log payloads before committing it.
- Run every collector's help path and representative safe path. Run the target
  repository's skill validator and tests when present.
- Report the created path, unresolved facts, live checks that could not run,
  collector commands, and any reload needed for the target agent client.

If evidence conflicts, do not average it into a plausible answer. Preserve the
conflict, identify the competing sources and dates, and ask which authority
governs.

## Example

**Input:** “Make this billing worker repo explain where it runs and what it
depends on.”

**Output:** Inspect the worker, pipeline, Helm values, SQL calls, and API client;
use authenticated read-only metadata to confirm QA/production AKS workloads;
ask only for the missing log workspace and externally owned procedure source;
then create `.agents/skills/billing-worker-context/` with verified reference
facts and tailored runtime, log-location, API-contract, and database-definition
collectors. Store the workload selector as durable truth and current pod names
as timestamped observations.

## Bundled resources

- `scripts/scan_repo_context.py` — **run** first to inventory tracked-file
  evidence without emitting source lines or secret values.
- `references/context-skill-contract.md` — **read** before creating or updating
  the target repo-scoped skill; it defines placement, reference fields, script
  requirements, and safety boundaries.
