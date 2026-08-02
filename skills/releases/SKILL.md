---
name: releases
description: "Manages local software releases and Azure Repos evidence. Use when explicitly invoked to create, review, or update release records, PRs, commits, testing, risks, or notes \u2014 even if the user calls them projects or production bundles."
compatibility: "Requires Azure CLI with the azure-devops extension and authenticated Azure DevOps access."
disable-model-invocation: true
---

# Releases

Maintain a small local record for each production release while treating Azure
Repos pull requests and their linked work items as the live delivery evidence.
This skill is manual-only: use it only after the user explicitly invokes it.

## Start every invocation

Before reading or writing any release record, prove that Azure DevOps is ready:

1. Confirm `az` exists and `az extension show --name azure-devops` succeeds.
2. Run `az devops configure --list`. Require configured `organization` and
   `project` values; do not guess either from the current Git repository.
3. Run `az devops project show --organization <organization> --project
   <project> --only-show-errors`, passing both configured values explicitly.
4. If any check fails, stop before accessing `~/.agents/releases`. Report the
   failed check and the login or configuration action the user must take. Never
   run `az login` or `az devops login`, request a token, or fall back to stale
   local-only release management.
5. After the preflight succeeds, create `~/.agents/releases` if it is missing.

Use Azure only for read operations in this workflow.

## Select the operation

- **Create:** Create a release when the user asks for a new project, release,
  rollout, or production bundle. Require a release name; record unknown details
  as visible follow-up checkboxes instead of inventing them.
- **Review:** When no operation is supplied, list active releases. Review one
  release when the user names it, or all active releases when they ask for an
  overview. Include released records only when requested.
- **Update:** Change only the requested release. Resolve it by exact filename
  slug or title; if more than one record matches, ask which one before writing.

Never infer or silently advance a release status from PR or work-item state.

## Store release records

Keep a flat directory with one Markdown file per release:

```text
~/.agents/releases/<release-slug>.md
```

Slug the release name with lowercase letters, digits, and single hyphens. Do
not create an index, database, archive directory, or nested release folders.
Keep released files in place and exclude them from active views by default.

Use exactly these statuses: `not started`, `in progress`, `in qa`, `released`.
Default new releases to `not started`. Change status only when the user asks;
allow backward or skipped transitions, but append the transition to Notes.
Use ISO `YYYY-MM-DD` dates. Update `Updated` after every edit. Treat Notes as
append-only unless the user explicitly asks to correct or remove an entry.

Create every record with this shape and preserve its heading order:

```markdown
# <release name>

- Status: not started
- Target date: Not set
- Created: YYYY-MM-DD
- Updated: YYYY-MM-DD

## Scope

Not yet defined.

## Acceptance criteria

- [ ] Define acceptance criteria.

## Required testing

- [ ] Define required testing.

## Possible regressions

- [ ] Assess possible regressions.

## Repositories

- None recorded.

## Notes

- YYYY-MM-DD — Release created.
```

Interpret an unchecked regression item as unresolved. Check it only after its
detection, mitigation, or explicit acceptance is recorded.

For each touched repository, replace `None recorded` with this structure:

```markdown
### <repository name>

- Local path: `/absolute/local/path`
- Pull requests:
  - [PR <id>](<full Azure Repos PR URL>)
- Commits:
  - `<commit SHA>` — <commit subject>
```

Record Azure Repos PRs only. Do not add a separate work-item section: Azure is
the source of truth, and linked work items must be discovered from each PR
during review. Before recording a repository or commit, confirm the local path
is a Git checkout and the commit resolves there. Before recording a PR, use
`az repos pr show --id <id> --organization <organization> --only-show-errors`
to confirm it exists. When no PR or commit exists yet, put `None recorded` under
that label. Record only commits the user identifies or that already resolve in
the local checkout; do not fetch or infer a PR's full commit set. Reject a
filename collision rather than overwriting an existing release.

## Review live evidence

For every PR in the selected release records:

1. Get current PR details with `az repos pr show`.
2. Run `az repos pr work-item list --id <id> --organization <organization>
   --only-show-errors`.
3. For each returned ID, run `az boards work-item show --id <work-item-id>
   --organization <organization> --fields
   System.Id,System.Title,System.State,System.AssignedTo --only-show-errors`.
4. Report the live PR status and each linked work item's ID, title, state, and
   assignee. Do not copy these mutable values into the release file.
5. Verify every recorded local path and commit without changing the checkout.

If a later Azure read fails after the initial preflight, label that evidence
unavailable and continue the report from facts already established. Never
replace live values with cached guesses or edit a record merely because review
found a mismatch.

Group an overview by release status. For each release, show its target date and
the concrete gaps that need attention, including:

- unchecked acceptance criteria, required testing, or regression items;
- missing or invalid local repositories and commits;
- PRs that do not resolve or have no linked work items; and
- a `released` record whose PRs or linked work items are not complete.

## Update safely

Edit the smallest relevant section, retain existing evidence, set `Updated`,
and append a dated note for status changes or other material decisions. Do not
rename or delete a release file unless the user explicitly requests that exact
file operation.

This skill does not authenticate to Azure, edit work items, update or merge
PRs, change votes, modify repository checkouts, commit code, deploy, or release
software. A separate explicit request and the relevant workflow are required
for those actions.

## Verify completion

Before reporting success, confirm:

- Azure preflight passed before release-file access;
- the intended file is the only release record created or changed;
- the status and all headings follow the required shape;
- `Updated` and any material Notes entry use today's date;
- every recorded repository, PR, and commit was verified; and
- the final response distinguishes stored facts, live Azure evidence, gaps,
  and any checks that could not run.

## Example

Input: `$releases create Billing August for the production bundle in
/work/billing, using Azure Repos PR 482.`

After a successful Azure preflight, create
`~/.agents/releases/billing-august.md`, verify the checkout and PR, store the PR
and any supplied or locally proven commits, leave unknown
acceptance/testing/regression items as unchecked follow-ups, and report the
PR's live linked work items without duplicating them in the file.
