---
name: python-standards
description: "Enforce high-integrity Python types, I/O, performance, and tooling. Use when coding, reviewing, profiling, or configuring Python, uv, Ruff, pyrefly, Pydantic, pandas, FastAPI, asyncio, or dependencies — even if unrequested. Not for test design."
---

# Python house standard

Apply these rules to all first-party Python. Optimize for explicit guarantees,
then choose the simplest implementation that preserves them.

## Types and state

- Rely on inference only for locals whose resulting type remains precise.
- Run pyrefly with `preset = "all"` over all owned code and require zero
  diagnostics. Do not fall back to the `strict`, `default`, `legacy`, or
  `basic` preset for brownfield code, and do not disable error kinds in
  `[tool.pyrefly.errors]` to clear a backlog. Offer a checked-in baseline
  only when the user explicitly chooses staged adoption over fixing the
  backlog; `references/tooling-setup.md` has the commands.
- `preset = "all"` makes `explicit-any` an error, so `Any` cannot be written
  at all. Model an unknown payload as `object` and narrow it, or type the
  shape it actually has. Where a third-party signature leaves no alternative,
  keep the single `# pyrefly: ignore[explicit-any]` in the adapter and let
  nothing untyped past it.
- Do not let `Any` or `Unknown` escape an untyped dependency adapter. Add a
  stub, `Protocol`, or narrow validated wrapper instead.
- Keep type-checker fixes in the type domain. Do not add runtime branches or
  assertions solely to appease the checker. Write every necessary suppression
  as `# pyrefly: ignore[error-kind]` with an adjacent reason; the asset sets
  `enabled-ignores`, so `# type: ignore` and `# pyright: ignore` no longer
  suppress anything. The `unused-ignore` kind rejects stale suppressions.
- Decorate every method that overrides a base-class member with `@override`;
  `missing-override-decorator` is an error. On the pinned Python 3.11 it comes
  from `typing_extensions`, which is a direct dependency — `typing.override`
  is 3.12 and later.
- Use `None` only when absence is a valid domain state. Do not use nullable
  fields for partial construction, missing required input, or error signaling;
  use complete objects or tagged state types instead.
- Prefer immutable values. Make mutation and state transitions explicit rather
  than exposing partially valid mutable objects.

## Validate boundaries

- Treat environment/configuration, network and queue messages, files, database
  rows, CLI input, and outbound payloads as I/O boundaries. Validate them with
  Pydantic before domain code consumes them or another system receives them.
- Use strict boundary models by default:

```python
model_config = ConfigDict(
    strict=True,
    extra="forbid",
    frozen=True,
    validate_default=True,
    revalidate_instances="always",
    allow_inf_nan=False,
)
```

- Convert validated input to typed domain objects; do not pass raw mappings
  through the core. Do not use `model_construct()` or unvalidated
  `model_copy(update=...)` with boundary data.
- Schema validation does not establish freshness, sequence continuity,
  referential integrity, reconciliation, or risk limits. Enforce those
  invariants explicitly and fail before acting when they are unknown.
- Keep validation at ingress even in latency-sensitive code. Move from
  Pydantic to an immutable dataclass or specialized hot-path representation
  only after measuring allocations and P50/P99/P99.9 latency.

## Configuration

- Load configuration once at startup into a validated, immutable settings
  object. Required environment variables have no defaults.
- Never use `os.getenv`, `os.environ.get`, or a configuration mapping's
  `.get()` for required settings. Missing or invalid configuration stops
  startup; ordinary mappings may use `.get()` when absence is meaningful.
- Commit `.env.example`; gitignore `.env` and `.env.*` with `!.env.example`;
  load the selected file explicitly with `uv run --env-file .env ...`. Do not
  call `load_dotenv()`.

## Domain code

- Prefer plain functions, explicit control flow, and small immutable data
  structures. Add an abstraction only when it enforces an invariant or removes
  observed duplication.
- Keep I/O in thin adapters and domain calculations deterministic. Pass clocks
  and random generators in rather than reading hidden process state.
- Give every dependency a seam: take collaborators — clock, RNG, HTTP client,
  database session — as parameters or constructor arguments. Code that needs
  `mock.patch` to exercise is code that hid a dependency; move it into the
  signature instead of reaching for the patch.
- Choose numeric representations from required precision, range, and units;
  never choose `float` implicitly for money, prices, quantities, or rates.
  Make rounding explicit and reject non-finite boundary values.
- Normalize external timestamps at the boundary to timezone-aware UTC.

## Performance

- Change code for speed only against a measurement. Profile CPU with `py-spy`
  (`py-spy top --pid <pid>`, `py-spy record`), which attaches to a running
  process and needs no code change, and allocations with `memray`. Time
  isolated code with `time.perf_counter`.
- Report P50/P99/P99.9 over a fixed workload, and state before-and-after
  numbers when reporting the change. A mean hides the tail that costs money.
- Work in this order: algorithm and data structure, then per-call overhead in
  the hot loop, then data representation. Micro-optimizing inside a quadratic
  join is wasted effort.
- Do repeated work once: hoist loop-invariant lookups, compiled regexes, and
  parsed config out of the loop, and precompute a `dict`/`set` for membership
  instead of rescanning a list.
- Batch and bound I/O. One round trip per row is the usual cause of a slow
  job. Every network and database call gets an explicit timeout.
- Optimize the measured path only; leave the rest at the simplest correct
  implementation.

## pandas

- Write for pandas 3 semantics. Copy-on-Write is the default, so chained
  assignment (`df[mask]["col"] = x`) silently updates a temporary and loses
  the write — assign through a single `.loc`/`.iloc` call. Strings infer to
  the `str` dtype, and `to_datetime` yields `datetime64[us]` unless the input
  needs nanoseconds. Install `pyarrow` so `str` columns use Arrow storage
  rather than the Python-object fallback.
- Pass `validate=` to every `merge` and `join` — `"one_to_one"`,
  `"one_to_many"`, or `"many_to_one"`. Without it a duplicate key silently
  multiplies rows, and nothing downstream distinguishes that from real data.
- Declare dtypes at the boundary (`read_csv(dtype=...)`, an explicit `astype`
  after a query). Inferred dtypes make a job's behavior depend on the values
  that happened to arrive that day.
- Assert the frame contract before the transform runs: required columns,
  dtypes, key uniqueness (`df.index.is_unique`, `df[key].is_unique`), and
  expected row count. Do this at the adapter boundary, like any other I/O.
- Never rely on index alignment across differently indexed objects —
  arithmetic between them produces `NaN` instead of raising. Merge on an
  explicit key, or reindex deliberately.
- Vectorize. `iterrows`, `apply(axis=1)`, and per-row Python calls are the
  last resort, not the first reach; use `category` for low-cardinality string
  columns before optimizing anything else.
- Compose transforms as named, pure functions of DataFrame to DataFrame and
  chain them with `.pipe()`. Each step is then testable on a small frame
  without constructing the whole pipeline.

## Async and services

- Never block the event loop. In FastAPI, declare a path operation or
  dependency `def` when its body calls blocking code — FastAPI runs `def`
  handlers in a threadpool — and `async def` only when the body awaits.
  Blocking inside `async def` stalls every concurrent request on that worker.
- Wrap an unavoidable blocking call in `asyncio.to_thread`. Keep CPU-bound
  work out of the API process entirely.
- Structure concurrency with `asyncio.TaskGroup` so a failing child cancels
  its siblings and the error propagates. A bare `asyncio.create_task` result
  must be held in a strong reference; the loop keeps only a weak one, so an
  unreferenced task can be garbage-collected mid-flight.
- Put a deadline on every await that crosses the network — `asyncio.timeout`
  or the client's own timeout. Bound fan-out with a semaphore and size
  connection pools explicitly.
- Never swallow `CancelledError`. Clean up and re-raise; suppressing it breaks
  `TaskGroup` and `asyncio.timeout`, which drive shutdown through cancellation.
- Build clients, pools, and sessions in the FastAPI `lifespan` handler, not at
  import time. Import-time I/O breaks startup ordering, hides failures from
  the health check, and makes the module unimportable in a test.

## Failure and diagnosis

- Log through `logging` with lazy `%s` arguments and structured `extra=`
  fields. `T20` rejects `print`, and `G004` rejects f-strings in log calls.
  Put the identifiers that make an incident searchable — run or partition id,
  request id, instrument, order id — in `extra`, not inside the message text.
- Log the identifying context at the point of failure and re-raise. Catching
  an exception, logging it, and returning a default converts an outage into
  silently wrong output.
- Log the resolved configuration and the input partition at startup, so a
  failed run can be reproduced from its own logs.

## Environment and tools

- Pin Python 3.11 in `.python-version` and set `requires-python = ">=3.11"`.
  Do not upgrade it incidentally.
- Keep dependencies, dev dependencies, and tool configuration in one
  `pyproject.toml`; commit `uv.lock`. Remove `requirements*.txt`, `setup.py`,
  `setup.cfg`, `Pipfile`, and setup scripts.
- Use `uv add`, `uv remove`, `uv sync`, and `uv run`; never `pip install`.
  Standalone scripts use a PEP 723 header and run with `uv run script.py`.
- Copy the Ruff and pyrefly sections from `assets/pyproject.toml` and copy
  `assets/pre-commit-config.yaml` verbatim; never retype or improvise them.
  Read `references/tooling-setup.md` before standardizing a repo's tooling,
  migrating from mypy or pyright, or debugging a hook that disagrees with the
  local command — it covers the pre-commit and pyrefly gotchas that produce
  confusing failures.
- Suppress a Ruff diagnostic with a specific rule code and an adjacent reason.
  Blanket `noqa` and blanket `type: ignore` are rejected by `PGH003`/`PGH004`,
  and `RUF102`/`RUF103`/`RUF104` reject invalid or stale suppressions.
- Expose each entry point as one `uv run` command with no prerequisite shell
  state.
- For a package published to others, read `references/packaging.md`: build
  backend, the `py.typed` marker and `__all__`, `uv build --no-sources`,
  trusted publishing, and verifying the artifact from the index.

## Verification

Before finishing Python work, run:

```text
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run pyrefly check
uv run pre-commit run --all-files
```

After dependency or environment changes, also delete only the repo-local
`.venv`, run `uv sync --locked`, and verify the program's imports or entry
point from that fresh environment.
