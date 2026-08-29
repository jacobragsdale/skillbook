---
name: python-testing
description: "Design and review Python tests: pytest, fixtures, pandas test data. Use when writing, reviewing, or debugging Python tests or coverage — even if unrequested. Not for implementation, typing, or Ruff config; use python-standards."
---

# Python testing house standard

Decide what to test, then build the smallest test data that states the case.
Implementation, typing, and tooling configuration belong to `python-standards`;
this asset covers test design, pytest setup, and test data only.

These rules replace default test-writing habits. Specifically: do not reach for
`unittest.mock.patch` or `pytest-mock`, do not assert on mock calls, and do not
build fixtures from untrimmed real extracts. The codebase is written as a pure
core behind thin gateways, so a test that needs patching has found a hidden
dependency — move it into the signature instead.

## What to test, in priority order

Spend effort top-down. Tiers 1 and 2 carry most of the value; a suite that
stops after tier 3 is already a good suite.

### Tier 1 — pure core functions

Every function in the functional core gets a table-driven test that asserts on
the returned value. Cover the boundary of each rule (at the limit and just
past it), the empty input, and one representative normal case. Do not add a
fourth case that exercises an already-covered branch.

Because decisions are returned as data rather than executed, test the decision
directly — no database, no fakes, no fixtures.

### Tier 2 — invariants no schema can express

These are the ETL failures that reach production. Work the checklist for every
batch job:

- [ ] **Idempotency** — run the job twice over one partition; the second
      output equals the first and the row count does not grow.
- [ ] **Partition isolation** — writing partition B leaves partition A intact.
- [ ] **Merge cardinality** — feed a duplicated key to each merge and assert it
      raises. `validate=` is required by `python-standards`; this is the test
      that proves it is actually wired to the right cardinality.
- [ ] **Output gate** — a zero-row result fails unless allow-empty was passed.
- [ ] **Atomic publish** — when validation fails mid-write, the destination is
      byte-for-byte unchanged.
- [ ] **Exit code** — a failing run makes `main()` return nonzero. That is the
      contract with the scheduler, and it silently regresses.

### Tier 3 — boundary reject paths

A boundary model's value is what it refuses. Per Pydantic model or frame
schema: one test that valid input passes, then one each for wrong dtype, null
in a non-nullable column, duplicate composite key, and an out-of-domain value.
Test that *this schema* says what you think it says; never test that Pydantic
or pandas works.

### Tier 4 — gateway contract tests

Mark these `integration`. Call the real query, stored procedure, or endpoint
and validate the result with the same frame schema production uses. Assert
the shape — columns, dtypes, nullability — and nothing about the values, which
change daily. This is what converts "someone altered the stored procedure"
into a red test instead of a 3am pipeline failure, and it is the tier most
often skipped.

### Tier 5 — one smoke test per entry point

Run `main()` over a tiny fixture partition with `tmp_path` or SQLite as the
sink; assert the exit code and a couple of output rows. It exists to catch
wiring mistakes. One or two per repository, no more.

### Do not test

Framework behavior, log message text, private helpers directly (reach them
through the public function), trivial accessors, or anything whose test would
need rewriting after a pure refactor. A test that breaks when correct code is
restructured is a liability.

## When to write which

- **A bug escaped** → write the failing test that reproduces it *before* the
  fix. No exceptions; this is the habit that grows the suite along the axis
  the system actually fails on.
- **About to refactor** → tiers 1 and 2 over the code being changed, first.
- **The rule is statable in one sentence before coding it** (risk limit, order
  sizing, reconciliation) → test first.
- **Exploratory DataFrame work** → implement, then pin the behavior with tier 1
  tests once the shape settles. Do not test-drive a transform you are still
  discovering.
- **New gateway** → write its tier 4 contract test immediately, while a real
  payload is still in front of you.
- **Coverage** is a diagnostic, never a gate. Read branch coverage of the core
  module and treat gaps as questions. Do not add a percentage threshold to CI:
  it produces tests written to move a number, and 100% coverage of gateway
  glue is theater.

## Setup

Merge `assets/pyproject.toml` into the repository's `pyproject.toml`. Four
lines in it are load-bearing and easy to drop:

- `filterwarnings = ["error"]` — in pandas 3, chained assignment raises
  `ChainedAssignmentError`, which subclasses `Warning`: under default filters
  the write is silently discarded and the suite still passes. This line is what
  makes the `python-standards` chained-assignment rule enforceable, and it
  catches deprecations before an upgrade does.
- `xfail_strict = true` — an `xfail` that starts passing is a failure, not a
  silent pass.
- `--strict-markers --strict-config` — a typo'd marker or config key errors
  instead of being ignored.
- `--import-mode=importlib` — pytest still defaults to `prepend`; `importlib`
  keeps `tests/` off `sys.path` and needs no `__init__.py`.

Add these plugins and nothing else without a reason:

| Package | Use |
|---|---|
| `pytest-cov` | Branch coverage as a diagnostic |
| `pytest-randomly` | Randomizes order and reseeds `random` per test — surfaces inter-test coupling and hidden module state |
| `pytest-xdist` | `-n auto`, once the suite is slow enough to notice |
| `hypothesis` | Property tests for invariants; see the reference |
| `pytest-asyncio` | Only in repositories with async code; set `asyncio_mode = "auto"` |
| `respx` | httpx fakes when `httpx.MockTransport` is not enough |

Do not add `pytest-mock` (nothing here patches), `freezegun` or `time-machine`
(clocks are passed in as parameters), or `vcrpy` (recorded cassettes rot
silently and hide the upstream drift a tier 4 test is meant to catch).

Layout: `tests/` mirrors the package, `tests/conftest.py` holds the frame
builders, `tests/data/` holds committed fixture files. Register every marker.
Plain `pytest` runs the unit suite only; the `integration` tier runs on its own
command, so a default test run never needs a database or a network.

## Test data

1. Build frames in code from a per-schema builder — five rows or fewer, and
   state only the fields the test is about. A test whose input is a 40-column
   extract tells the reader nothing about what is being tested.
2. Derive the builder's dtypes from the frame schema so fixtures cannot
   drift from the contract, and assert once that the builder's output
   validates.
3. Compare frames with `assert_frame_equal` after sorting and
   `reset_index(drop=True)` on both sides; keep `check_dtype=True` so a silent
   `Int64` → `float64` promotion fails. Never let index alignment decide
   whether a test passes.
4. `Decimal` compares exactly with `==`. Use `pytest.approx` only for
   genuinely float-domain values, always with an explicit tolerance.
5. A default-run test performs no network call, touches no real database,
   reads no clock, and uses no unseeded RNG. Pass the clock and seed in.
6. Commit fixture files as Parquet, not CSV — CSV discards the dtypes the
   test is pinning down.

### Example — a builder derived from the boundary schema

```python
_TRADE_DEFAULTS = {"account_id": "A1", "trade_id": "T1", "quantity": 10, "price_micros": 1_250_000}
_TRADE_DTYPES = TRADES_SCHEMA.dtypes  # the boundary schema owns the dtype mapping


def trades_frame(*rows: Mapping[str, object]) -> pd.DataFrame:
    """Build a trades frame from partial rows; unstated fields take valid defaults."""
    return pd.DataFrame([_TRADE_DEFAULTS | dict(row) for row in rows or ({},)]).astype(_TRADE_DTYPES)


def test_builder_produces_a_frame_the_schema_accepts() -> None:
    validate_frame(trades_frame(), TRADES_SCHEMA)  # one line; guards every other test against fixture drift


def test_zero_quantity_trades_are_rejected() -> None:
    with pytest.raises(FrameSchemaError):
        validate_frame(trades_frame({"quantity": 0}), TRADES_SCHEMA)
```

Read `references/data-fixtures.md` before writing golden-file comparisons,
property-based tests, or anything in the `integration` tier — it carries the
golden-file policy, worked Hypothesis invariants, and the ephemeral-database
setup.

## Verification

Before finishing test work, run:

```text
uv run pytest
uv run pytest -m integration    # only when the tier 4 dependencies are available
```

Run the suite from the locked environment, never from an ad-hoc `uv run --with`
one: pandas resolves the `string` dtype's storage differently depending on
whether `pyarrow` is installed, so a missing extra makes dtype assertions pass
or fail for reasons that have nothing to do with the code.

A test that fails intermittently is not flaky until proven so; first re-run
with `-p no:randomly` to see whether the order was carrying hidden state, and
fix the coupling rather than the symptom. Never mark a failing test `xfail` or
`skip` to get a green run — either the behavior or the test is wrong, and both
answers are cheap to find now and expensive to find later.

## Bundled resources

- `assets/pyproject.toml` — **copy** into the repository's `pyproject.toml`;
  pytest and coverage configuration, not to be retyped.
- `references/data-fixtures.md` — **read** when handling golden files,
  property-based tests, recorded API or stored-procedure fixtures, or the
  `integration` tier's database setup.
