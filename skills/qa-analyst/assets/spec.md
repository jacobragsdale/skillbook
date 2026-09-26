# <TICKET>: <title> — specification

| Field | Value |
|---|---|
| Ticket | <TICKET> |
| Version | 1 (increment on every change after approval) |
| Prepared by | <agent and model> for <invoking user> |
| Approved by | <name, UTC timestamp, where recorded on the ticket> |

## 1. Purpose

<What the change does and why, in two or three sentences.>

## 2. Scope

- In scope:
- Out of scope:
- Downstream consumers of the output:

## 3. Glossary

| Term | Meaning |
|---|---|

## 4. Inputs and output

| Input | Source (table or feed) | As-of semantics |
|---|---|---|

Output table: `<schema.table>`. Grain: <one row per …>. Key: <columns>.

| Column | Type and scale | Meaning |
|---|---|---|

## 5. Rules

<Number every rule R1…Rn. Write calculations as decision tables with a
"Unique" hit policy: every input combination matches exactly one column.>

## 6. Precision and conventions

| Item | Rule |
|---|---|
| Rounding mode | |
| Rounding point | <per row or on the total> |
| Scale | <per column or per currency, from ISO 4217> |
| Sign convention | |
| As-of cutoff and timezone | |
| Trade or settle date | |
| Business-day calendar | |
| Missing price, rate, or reference data | <must fail loudly> |

## 7. Worked examples

| ID | Rule | Inputs | Calculation (arithmetic shown) | Expected | Tolerance |
|---|---|---|---|---|---|

## 8. Run behavior

| Situation | Required behavior |
|---|---|
| Rerun of the same as-of date | |
| Failure mid-run | |
| Idempotency key | |
| Audit columns | |

## 9. Reference system (oracle)

<Which system and component is the reference, which output is compared, its
known defects or intended differences, and who decides when it is wrong.>

## 10. Acceptance criteria

| AC | Rule(s) | Criterion |
|---|---|---|

<Tables for calculations; Given/When/Then for run behavior.>

## 11. Assumptions

| # | Assumption | Owner |
|---|---|---|

## 12. Open questions

| # | Question | Asked of | Answer |
|---|---|---|---|
