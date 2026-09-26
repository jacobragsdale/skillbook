# Parity testing and reconciliation

How to prove a new job's output matches a reference system (the oracle), and
how to check what the job wrote. Read at step 3 to plan and step 5 to execute.

## Contents

- [Pin the inputs](#pin-the-inputs)
- [Reconcile in layers](#reconcile-in-layers)
- [SQL templates](#sql-templates)
- [Scale, rounding, and tolerance](#scale-rounding-and-tolerance)
- [Coverage](#coverage)
- [Break categories and dispositions](#break-categories-and-dispositions)
- [Database write checks](#database-write-checks)
- [Determinism](#determinism)
- [Tools](#tools)

## Pin the inputs

A parity run proves something only when both sides saw identical inputs.

- Run both sides on the same as-of date, input snapshot, and price, FX, and
  reference-data versions. Record each ID in preflight.
- Never let either side read "latest" data or call `now()` in a calculation.
  If one side does, that is a finding.
- Freeze the oracle's output (CSV in the pack or a scratch table) before
  comparing. Extract it again after the new job runs; the two extracts must be
  identical, which proves the new job didn't change the oracle's inputs.
- Compare keyed sets, never rows by position.

## Reconcile in layers

Run the layers in this order. Each one makes the next one meaningful.

1. **Key sanity, both sides.** Keys are non-null and unique. Duplicate keys
   multiply rows in a join, and null keys never match.
2. **Row counts** per as-of date.
3. **Control totals by group** (portfolio, currency, product type): `COUNT`,
   `SUM`, and `SUM(ABS())` of each money column. They locate breaks cheaply,
   but offsetting errors net to zero, so never stop here.
4. **Keyed full outer join**, classifying each key as `match`,
   `only_in_oracle`, `only_in_new`, or `value_mismatch`.
5. **Column diffs** on the mismatched keys. Column diffs only see keys present
   on both sides, which is why layer 4 comes first.

Persist every non-matching row from layers 4 and 5 into the pack, not only the
counts.

## SQL templates

Key sanity (run on each side; both must return zero rows):

```sql
SELECT account_id, instrument_id, as_of_date, COUNT(*) AS n
FROM <table>
WHERE as_of_date = :as_of
GROUP BY account_id, instrument_id, as_of_date
HAVING COUNT(*) > 1
   OR account_id IS NULL OR instrument_id IS NULL;
```

Control totals by group:

```sql
SELECT 'oracle' AS side, currency, COUNT(*) AS n,
       SUM(amount) AS total, SUM(ABS(amount)) AS abs_total
FROM oracle_frozen WHERE as_of_date = :as_of GROUP BY currency
UNION ALL
SELECT 'new', currency, COUNT(*), SUM(amount), SUM(ABS(amount))
FROM new_output WHERE as_of_date = :as_of GROUP BY currency
ORDER BY currency, side;
```

Keyed full outer join, classified (run the summary, then save
`SELECT * FROM j WHERE status <> 'match'` as the break list):

```sql
WITH o AS (SELECT account_id, instrument_id, amount_a, amount_b
           FROM oracle_frozen WHERE as_of_date = :as_of),
     n AS (SELECT account_id, instrument_id, amount_a, amount_b
           FROM new_output WHERE as_of_date = :as_of),
     j AS (SELECT COALESCE(o.account_id, n.account_id)       AS account_id,
                  COALESCE(o.instrument_id, n.instrument_id) AS instrument_id,
                  o.amount_a AS o_a, n.amount_a AS n_a,
                  o.amount_b AS o_b, n.amount_b AS n_b,
                  CASE WHEN o.account_id IS NULL THEN 'only_in_new'
                       WHEN n.account_id IS NULL THEN 'only_in_oracle'
                       WHEN o.amount_a IS DISTINCT FROM n.amount_a
                         OR o.amount_b IS DISTINCT FROM n.amount_b THEN 'value_mismatch'
                       ELSE 'match' END AS status
           FROM o FULL OUTER JOIN n
             ON o.account_id = n.account_id AND o.instrument_id = n.instrument_id)
SELECT status, COUNT(*) AS n_rows,
       SUM(ABS(COALESCE(n_a, 0) - COALESCE(o_a, 0))) AS abs_diff_a,
       SUM(ABS(COALESCE(n_b, 0) - COALESCE(o_b, 0))) AS abs_diff_b
FROM j GROUP BY status;
```

Engine notes:

- `IS DISTINCT FROM` works in Postgres, SQL Server 2022+, BigQuery, DuckDB,
  and Snowflake. MySQL uses `NOT (a <=> b)`. Elsewhere (Oracle, older SQL
  Server) write `(a <> b OR (a IS NULL AND b IS NOT NULL) OR (a IS NOT NULL
  AND b IS NULL))`. A plain `<>` silently treats NULL-vs-value as a match.
- `EXCEPT` in both directions is a fast whole-row check and is null-safe, but
  it collapses duplicates. Run key sanity first. `EXCEPT ALL` keeps
  duplicates but SQL Server lacks it. Oracle spells it `MINUS`.
- Filter both sides to the same as-of date inside the CTEs, not after the
  join, or the outer join turns into an inner one.

## Scale, rounding, and tolerance

- **Compare at stored scale.** Cast both sides to the larger of the two stored
  scales, never smaller: casting to a coarser `DECIMAL` rounds differences
  away. A float column on either side is a finding; compare it after rounding
  to the spec's scale with the spec's rounding mode, and say so in the report.
- **Rounding defaults differ by engine**, the classic cause of one-cent breaks:

  | Engine or language | Default for ties |
  |---|---|
  | Python `round()`, `Decimal` context, .NET `Math.Round`, Java `NumberFormat` | half-even (banker's) |
  | SQL Server `ROUND`, Postgres `round(numeric)` | half away from zero |
  | Postgres `round(double precision)` | platform, usually half-even |

  Python `round(2.675, 2)` is 2.67 because the float is below 2.675.
- **Rounding point matters as much as mode.** Rounding each row and then
  summing differs from summing and then rounding. The spec fixes both.
- **Tolerance policy.** Default exact. A tolerance is absolute, per column, in
  minor currency units, tied to a demonstrated cause (a proven rounding-mode
  difference), and approved by the user. Never use a relative tolerance on
  money: 1e-6 on a 10,000,000 balance lets 10.00 through.
- **Keep tolerated differences visible.** Report their count and net sum per
  column (`reconcile.py` does). When they all have the same sign, it is bias
  from a logic difference, not rounding noise. Investigate it as a break.

## Coverage

- Compare the full population. Sampling misses rare categories, and SQL
  comparisons are cheap.
- Choose several as-of dates: a month-end, a quarter- or year-end when the
  change touches period logic, the day after a corporate-action ex-date, and a
  date with a stale price or an FX holiday.
- Report row counts per stratum (product type, currency, position sign) so a
  reviewer can see that edge categories were present, not just that totals
  matched.
- Add hand-calculated golden cases for categories the oracle lacks and for
  errors both systems could share. Back-to-back testing only finds
  differences.

## Break categories and dispositions

| Category | Typical cause |
|---|---|
| As-of or timing | Different cutoff, timezone, or trade vs settle date |
| Reference data | Different price, FX rate, or static data version |
| Rounding | Mode, point, or scale differs |
| Population | Different filters on which rows exist |
| Logic defect | The change is wrong against the spec |
| Oracle defect | The reference system is wrong against the spec |
| Input data quality | Bad or duplicate source rows |
| Test error | Wrong query, stale extract, mismatched as-of |

- Record for each break: key or group, column, both values, difference,
  category, evidence (minimal key plus hand calculation), and disposition.
- Every exclusion rule (ignored columns, filtered keys) guarantees the sides
  differ somewhere. Keep them narrow, list each in the report with the count
  of rows it removed.
- "Pass with unexplained breaks" does not exist. An unexplained break means
  the cause list is incomplete; it can be the visible edge of a systemic
  defect that a tolerance is hiding elsewhere.
- An oracle defect is accepted only with an independent hand calculation and
  the user's agreement. The calculated value becomes the expected value.

## Database write checks

Use these for the run-behavior test cases.

- **Before and after snapshots:** row counts and control totals of the target
  table for every as-of date, not only the one under test. Only the planned
  partition may change.
- **Collateral writes:** row counts and `MAX(updated_at)` of tables the job
  must not touch. On Postgres, compare `n_tup_ins`, `n_tup_upd`, and
  `n_tup_del` in `pg_stat_all_tables`, read in a fresh transaction at least a
  second after the run, because the counters lag.
- **Rerun the same as-of date:** the key-sanity query returns nothing, and
  row count and values are unchanged. A plain `INSERT` on rerun is the usual
  defect.
- **Failure mid-run** (only when the plan lists it): afterward, either no rows
  are written or the documented resumable state holds.
- **Audit columns:** populated, `created_at` preserved on rerun when that is
  the policy, and the run ID traceable to the input snapshot.

## Determinism

- Run the job twice on the same inputs and reconcile the outputs, excluding
  only an explicit list of volatile columns (run timestamps, run IDs,
  surrogate keys). List them in the report.
- Common sources of nondeterminism: `ROW_NUMBER` ordered by a non-unique
  column, `LIMIT` or `TOP` without `ORDER BY`, float `SUM` in a parallel
  engine, and unstated tie-breaks in lot selection.

## Tools

- `scripts/reconcile.py` — keyed comparison of two CSV extracts with exact
  decimal math, in memory. Fine to a few million rows; above that, reconcile
  in SQL inside the database and capture the queries. It compares numbers by
  value (`1.10` equals `1.1`); pass `--text` for numeric-looking identifiers
  where leading zeros matter.
- Export both sides at stored scale with a stable number format: no thousands
  separators, no scientific notation, and the same NULL token (`--null`).
- datacompy converts `Decimal` to float before comparing, so it is unsafe for
  money unless amounts are first cast to integer minor units. Its relative
  tolerance also scales with the value.
- The open-source `data-diff` has been unmaintained since May 2024 and hashes
  values as text, so formatting differences between engines show up as false
  breaks.
