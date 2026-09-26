# <TICKET>: test completion report

## Ticket summary

**Verdict: <PASS | PASS WITH EXCEPTIONS | FAIL | BLOCKED>**

- Scope: spec v<n>, <a> acceptance criteria, <x> of <y> planned test cases executed.
- Environment: <QA server and database>; builds <new job>, <oracle>.
- Parity: <rows> rows over <as-of dates>; <m> matched, <b> breaks (<disposition summary>).
- Defects: <IDs and one-line summaries, or "none">.
- Evidence: `<ticket>.zip`, `SHA256SUMS` sha256 `<hash>`.
- Prepared by <agent and model> for <invoking user>; awaiting human review and sign-off.

## Header

| Field | Value |
|---|---|
| Spec version | |
| Plan frozen | run `<seq>-PLAN` at <UTC> |
| Environment | <identity as captured in PREFLIGHT> |
| Builds under test | |
| Input snapshot | |
| Executed by | <agent and model>, invoked by <user> |
| Execution window | <first run UTC> to <last run UTC> |

## Results by test case

| TC | AC | Expected | Actual | Status | Run(s) |
|---|---|---|---|---|---|

## Traceability

| AC | Test cases | Result |
|---|---|---|

## Reconciliation

| As-of | Oracle rows | New rows | Matched | Breaks | Control totals |
|---|---|---|---|---|---|

Excluded columns or keys, with rows affected: <list, or "none">.

## Breaks and dispositions

| # | Key or group | Column | Oracle | New | Diff | Category | Disposition | Accepted by |
|---|---|---|---|---|---|---|---|---|

## Defects

| ID | Severity | Summary | Expected | Actual | Run | Status |
|---|---|---|---|---|---|---|

## Deviations from the plan

<Each change to the frozen plan, rerun, or invalidated run, with its reason.>

## Blockers and workarounds

## Residual risks and limitations

<What was not tested and why; categories absent from the test data.>

## Sign-off

| Role | Name | Date | Meaning of signature |
|---|---|---|---|
| Reviewer | | | Reviewed the evidence and agrees with the verdict |
| Approver | | | Approves the change for release |
