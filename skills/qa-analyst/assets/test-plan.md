# <TICKET>: test plan

| Field | Value |
|---|---|
| Spec version | |
| Environment | <QA server and database names> |
| Builds under test | <new job version or commit; oracle version> |
| As-of dates | |
| Input snapshot | <batch or snapshot IDs; price, FX, reference-data versions> |
| Prepared by | <agent and model> for <invoking user> |

## Approach

<Two or three sentences: parity layers, golden cases, run-behavior checks,
and what is deliberately not tested.>

## Planned QA writes

| Step | Target (table and partition) | Operation | How it is undone |
|---|---|---|---|

## Test cases

Expected results are fixed here, before execution. Every AC in the spec
appears in at least one row.

| TC | AC | Risk | Technique | Input | Expected result | Tolerance | Evidence to capture |
|---|---|---|---|---|---|---|---|

## Exit criteria

- Every test case executed.
- Every test case passed, or its failure is a logged defect.
- Zero unexplained breaks; every accepted break names who accepted it.

## Approval

Approved by <name> at <UTC timestamp>; frozen as run `PLAN` in `log.jsonl`.
