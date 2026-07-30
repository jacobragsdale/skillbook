# Test data and the integration tier

Read when a test needs more than a hand-built frame: golden files, recorded
upstream payloads, property-based invariants, or a real database.

## Contents

- [Recorded fixtures from APIs and stored procedures](#recorded-fixtures-from-apis-and-stored-procedures)
- [Golden files](#golden-files)
- [Property-based tests with Hypothesis](#property-based-tests-with-hypothesis)
- [Synthesizing frames from a Pandera schema](#synthesizing-frames-from-a-pandera-schema)
- [The integration tier](#the-integration-tier)
- [HTTP and async](#http-and-async)

## Recorded fixtures from APIs and stored procedures

Use a recorded fixture when the realistic *shape* is the point — nested JSON, a
40-column result set — and a hand-built frame would be a lie about what
upstream sends.

1. Capture once with a throwaway script, not inside the test.
2. Trim to five rows or fewer, chosen to cover the interesting cases (a null, a
   boundary value, a duplicate key if legal).
3. Scrub credentials, account identifiers, and anything personal. A committed
   fixture is public to everyone with repository access.
4. Save as Parquet under `tests/data/`. CSV discards dtypes, which reintroduces
   the type inference the test is trying to pin down.
5. Record the source and capture date in the loader's docstring.

A recorded fixture proves your code handles the payload you saw in the past. It
cannot notice that upstream changed — only a tier 4 contract test does that.
Ship both or accept the gap knowingly.

## Golden files

Justified when the expected output is genuinely unreasonable to hand-write: a
report with dozens of derived columns. Not justified because writing the
expected frame is tedious.

- Store the golden output as Parquet under `tests/data/golden/`.
- Regenerate only through an explicit command — a `scripts/update_golden.py` or
  a custom `--update-golden` flag — never automatically on failure.
- A changed golden file in a commit is a claim that the output changed on
  purpose. Review it as a diff and say why in the message. Parquet does not
  diff readably, so have the regeneration script print the changed columns and
  row counts and paste that into the commit.
- Never regenerate to make a red test green without reading what moved. An
  unreviewed golden update is how wrong output becomes the expectation.

For small structures — a dict, a summary tuple, an error message — prefer an
inline literal in the test over a snapshot file. The value of a golden file
drops to zero the moment the reader cannot tell what it should contain.

## Property-based tests with Hypothesis

Use these for invariants you can state in one sentence about *any* input, which
is where hand-picked cases run out. High-value shapes here:

- A decision never breaches its limit, for any position and limit.
- Applying the same decision twice equals applying it once (idempotency).
- `parse(render(x)) == x` for any domain value (round-trip).
- Allocations sum to the total being allocated, for any split.

```python
from decimal import Decimal

from hypothesis import given, settings, strategies as st


@given(
    position=st.decimals(min_value=0, max_value=10_000, places=2),
    limit=st.decimals(min_value=1, max_value=10_000, places=2),
)
def test_sizing_never_exceeds_the_position_limit(position: Decimal, limit: Decimal) -> None:
    order = size_order(position=position, limit=limit)
    assert position + order.quantity <= limit


@given(trades=trade_lists())  # a composite strategy building valid domain values
@settings(deadline=None)  # DataFrame construction blows the 200ms per-example default
def test_reconciliation_is_idempotent(trades: list[Trade]) -> None:
    once = reconcile(trades)
    assert reconcile(once.trades) == once
```

Two operational notes: pass `places=` to `st.decimals` (and never
`allow_nan`/`allow_infinity`) so generated money stays in the domain, and
gitignore `.hypothesis/`, the local example database.

When a property test fails, Hypothesis prints a minimal counterexample. Copy it
into a permanent `parametrize` case — the property test finds the bug once, the
example test keeps it fixed.

## Synthesizing frames from a Pandera schema

`SCHEMA.example(size=5)` and `SCHEMA.strategy()` generate conforming frames;
both need the `pandera[strategies]` extra, which pulls in Hypothesis.

Use them to feed a property test, or to prove a schema is satisfiable at all.
Do not use them as ordinary fixtures: the values are arbitrary, so the test
stops documenting its own case, and generation is slow enough to notice in a
suite. Hand-built frames from the builder in SKILL.md stay the default.

## The integration tier

Every test here carries `@pytest.mark.integration` and is excluded from the
default run. Two safety rules, both absolute:

- The connection comes from a test-only settings object. Never import or reuse
  the production settings object in a test, and never let a default point at a
  production host.
- Writes go to an ephemeral database or a per-run schema/table prefix. A test
  that can write to a shared environment will eventually run against the wrong
  one.

### Ephemeral SQL Server for stored procedures

SQLite is not a substitute the moment a stored procedure or T-SQL dialect is
involved. Use `testcontainers[mssql]` (verified against testcontainers 4.15.0):

```python
import pytest
from testcontainers.mssql import SqlServerContainer


@pytest.fixture(scope="session")
def mssql_url() -> Iterator[str]:
    pytest.importorskip("docker")  # skip cleanly where Docker is unavailable
    with SqlServerContainer() as container:
        yield container.get_connection_url()
```

Apply schema DDL and the procedure definitions in a session fixture, then let
each test insert only its own rows. Keep the container session-scoped —
per-test startup dominates the suite.

Where a container is impractical, a shared dev database is acceptable for
read-only contract tests.

### The contract test itself

```python
@pytest.mark.integration
def test_trades_proc_still_returns_the_agreed_contract(dev_connection: Connection) -> None:
    frame = fetch_trades(dev_connection, partition=date(2026, 7, 1))
    TRADES_SCHEMA.validate(frame, lazy=True)  # the production schema, unmodified
```

Assert nothing about the values. Row counts and prices change daily; the
contract must not. If this test needs a value assertion to be useful, the
missing constraint belongs in the schema instead.

## HTTP and async

- Fake HTTP with `httpx.MockTransport` — explicit, no new dependency, and the
  handler is ordinary code you can assert against. Reach for `respx` only when
  routing several endpoints makes the transport handler unwieldy.
- Never let a default-run test open a socket. A gateway that cannot be handed a
  client is missing a seam.
- With `asyncio_mode = "auto"`, `async def test_*` needs no decorator. Test
  timeout behavior by asserting `pytest.raises(TimeoutError)` against an
  injected slow fake, never by sleeping — a real sleep makes the suite slow and
  the assertion machine-dependent.
