# Pandera boundary validation

Read when a pandas DataFrame enters from Excel, CSV, SQL, a network response,
or another external system, or when a correctness-critical pipeline publishes
a frame.

## Choose the boundary model

- Use Pydantic for configuration, messages, nested object graphs, individual
  records, and outbound API contracts.
- Use Pandera for DataFrame columns, pandas dtypes, nullability, allowed values,
  composite keys, indexes, and vectorized cross-column rules.
- Do not convert a large DataFrame to record dictionaries and Pydantic models.
  That adds per-row allocations and discards the columnar contract.
- Do not add Pandera for small temporary frames built entirely from already
  validated domain values.

## Standard schema

Use the object API by default; it works cleanly with strict Pyrefly and states
joint constraints directly:

```python
import pandera.pandas as pa

TRADES_SCHEMA = pa.DataFrameSchema(
    {
        "account_id": pa.Column(
            "string",
            pa.Check.str_length(min_value=1),
            nullable=False,
        ),
        "trade_id": pa.Column(
            "string",
            pa.Check.str_length(min_value=1),
            nullable=False,
        ),
        "quantity": pa.Column("Int64", pa.Check.gt(0), nullable=False),
        "price_micros": pa.Column("Int64", pa.Check.gt(0), nullable=False),
    },
    name="trades",
    strict=True,
    coerce=False,
    unique=["account_id", "trade_id"],
    unique_column_names=True,
)

validated = TRADES_SCHEMA.validate(raw, lazy=True)
```

Declare dtypes in `read_excel`, `read_csv`, or `read_sql_query` where the
reader supports them. Keep `coerce=False` so a producer changing an integer
column to strings fails instead of being normalized silently. Set
`coerce=True` only in an adapter whose declared job includes parsing that
representation.

`lazy=True` aggregates all schema failures before raising; it does not postpone
validation. Log the schema, source, partition, and failure count, not the full
input or secret-bearing rows.

## Preserve global invariants

- Validating SQL chunks checks each chunk independently. Composite uniqueness,
  total row counts, monotonic sequence, and reconciliation across chunks need a
  database guarantee or explicit cross-chunk state.
- Validate at ingress and before publishing when the output contract differs.
  Do not validate after every pure transform unless measurement and risk justify
  it.

## Class API and tool compatibility

Prefer `DataFrameSchema`. Use `DataFrameModel` only when inheritance or reusable
annotated fields remove real duplication. The Ruff asset already marks
`pandera.pandas.DataFrameModel` as runtime-evaluated so annotation imports stay
available.

With Pyrefly 1.1.1 and Pandera 0.32.1, put this single suppression on a model's
configuration class, then re-test and remove it when either tool is upgraded:

```python
class Config:  # pyrefly: ignore[bad-override] - Pandera's runtime Config pattern conflicts with its published typing.
    strict = True
    coerce = False
```
