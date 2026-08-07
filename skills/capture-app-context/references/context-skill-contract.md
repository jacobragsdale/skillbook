# Repo-scoped context skill contract

Use this contract for the skill produced inside the target repository. The
result is operational reference for an agent working in that repository, not a
general architecture narrative or a dump of live systems.

## Contents

- Placement and shape
- Reference record
- Collector contract
- Sensitivity gate

## Placement and shape

Use the repository's existing project-skill convention. Otherwise create:

```text
.agents/skills/<repo-name>-context/
├── SKILL.md
├── references/
│   └── application-context.md
└── scripts/
    └── <one or more authority-specific collectors>
```

Normalize `<repo-name>-context` to lowercase hyphen-case. Keep one canonical
copy. Add client-specific links or generated copies only when the repository
already has a mechanism that prevents drift.

The generated `SKILL.md` must tell an agent to:

1. Read its `application-context.md` reference before answering operational,
   integration, data, deployment, or incident questions.
2. Run a named collector before relying on a drift-prone fact.
3. Treat collector output as current evidence, not permission to modify the
   external system.
4. Surface unknown, stale, inferred, or conflicting facts instead of guessing.

Keep detailed facts in the reference, not in `SKILL.md`.

## Reference record

Start `application-context.md` with scope, owning application,
repository, sensitivity, and last review time. Organize the rest in this order:

1. Environments and ownership
2. Observability
3. External APIs
4. Databases
5. AKS runtime and endpoints
6. Jobs and schedules
7. Messaging, storage, caches, configuration, and secret stores
8. Deployment, alerts, and runbooks
9. Unknowns and conflicts

Use repeated records or tables with these fields:

| Field | Required meaning |
| --- | --- |
| Environment | QA, production, shared, or not applicable |
| Fact | Exact identifier, behavior, relationship, or definition |
| Purpose | Why the application uses it |
| Status | `verified-live`, `verified-repo`, `user-provided`, `inferred`, `unknown`, or `not-applicable` |
| Source | File and line, immutable URL, command plus stable target, schema source, or named user statement |
| Verified | UTC timestamp or repository commit |
| Refresh | Collector command or manual authority |

Do not use `verified` without saying whether the evidence came from the
repository or a live system. An inference must state its reasoning. A user
statement remains `user-provided` until another authority verifies it.

For databases, map each call site to the exact database object, read/write
effect, definition source, and refresh method. Store DDL only when it contains
no credentials, grants, row data, or environment secrets.

For AKS, record stable workload identity before volatile observations:
subscription, resource group, cluster, namespace, workload kind/name, labels,
containers, services, and ingress. Record current pod names with the observation
time; never present a pod name as durable configuration.

For logs, distinguish application file paths or stdout/stderr from the central
sink that operators actually query. Record the dashboard/query location and
correlation fields, not copied production events.

## Collector contract

Create one collector per authority only when live freshness is useful, such as:

- `collect-aks-runtime` for workloads, selectors, services, and current pods;
- `collect-observability` for log sink metadata and saved-query locations;
- `collect-database-definitions` for schema metadata and object definitions;
- `collect-api-contracts` for OpenAPI or other authoritative contracts.

Names and implementation language follow the target repository. Each collector
must:

- expose useful help and require an explicit QA or production target;
- pin subscription, cluster, context, namespace, workspace, server, database,
  or API authority rather than inherit an ambient default;
- call only documented read-only operations and use argument arrays rather
  than a shell command string;
- set timeouts, cap records and bytes, and return nonzero on partial failure;
- emit structured data or concise text to stdout by default;
- identify its source target and observation time;
- redact credential-like values and omit production rows and log bodies;
- leave reference updates for agent review instead of editing them directly.

Do not build a configurable arbitrary-command runner. Do not add a collector
for a system whose authority, authentication model, and safe read operation are
still unknown.

## Sensitivity gate

Before committing internal topology, determine repository visibility from the
hosting provider when possible. If it is public or visibility cannot be
verified, ask the user whether to sanitize the reference, keep it in an ignored
local skill, or stop. Never assume that a Git remote using authentication means
the repository is private.

Secret-store names and authentication mechanism names are useful context;
secret values, connection strings, tokens, certificates, Kubernetes Secret
payloads, production rows, and raw production logs are prohibited.
