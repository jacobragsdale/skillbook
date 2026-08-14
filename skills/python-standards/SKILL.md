---
name: python-standards
description: "Enforce high-integrity Python implementation and tooling; exclude test design. Use when coding, reviewing, profiling, or configuring Python, Pydantic, performance, uv, Ruff, ty, FastAPI, asyncio, tooling, or dependencies — even if unrequested."
---

# Python house standard

Apply these rules to all first-party Python. Optimize for explicit guarantees,
then choose the simplest implementation that preserves them.

## Types and state

- Rely on inference only for locals whose resulting type remains precise.
- Run `ty check` over all owned code with the checked-in strict configuration
  and require zero diagnostics. Keep ty's enabled defaults and the asset's
  selected high-signal opt-in rules; do not set `all = "error"`, which Astral
  does not recommend, or disable rules globally to clear a backlog. Allow
  staged adoption only when the user explicitly chooses it; keep every
  temporary relaxation narrow and tracked for removal.
- Do not write `Any` in first-party interfaces. Model an unknown payload as
  `object` and narrow it, or type the shape it actually has. Contain an untyped
  dependency behind an adapter — a stub, `Protocol`, or narrow validated wrapper
  — and let neither `Any` nor ty's inferred `Unknown` pass it.
- Keep type-checker fixes in the type domain. Do not add runtime branches or
  assertions solely to appease the checker. Write every necessary suppression
  as `# ty: ignore[rule]` with an adjacent reason. The asset rejects blanket
  suppressions and disables `# type: ignore`, so only a named ty rule can hide
  a diagnostic.
- Decorate every method that overrides a base-class member with `@override`.
  Import it from `typing` when every supported Python version provides it;
  otherwise use `typing_extensions` as a direct dependency.
- Use `None` only when absence is a valid domain state. Do not use nullable
  fields for partial construction, missing required input, or error signaling;
  use complete objects or tagged state types instead.
- Prefer immutable values. Make mutation and state transitions explicit rather
  than exposing partially valid mutable objects.

## Validate boundaries

- Treat environment/configuration, network and queue messages, files, database
  rows, CLI input, tabular data, and outbound payloads as I/O boundaries.
  Validate them before domain code consumes them or another system receives
  them; use Pydantic for record and object boundaries.
- Use strict Pydantic boundary models by default:

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
  referential integrity, completeness relative to the source, provenance,
  reconciliation, or risk limits. Enforce those invariants explicitly and fail
  before acting when they are unknown.
- Keep validation at ingress even in latency-sensitive code. Move from
  Pydantic to an immutable dataclass or specialized hot-path representation
  only after measuring allocations and P50/P99/P99.9 latency.

## Configuration

- Load configuration with `pydantic-settings`: define a `BaseSettings`
  subclass using `SettingsConfigDict` with the strict Pydantic options above,
  then instantiate it once at startup. Never give an environment-backed field
  a default, even when a development fallback is requested; missing or invalid
  configuration stops startup.
- Never use `os.getenv`, `os.environ.get`, or a configuration mapping's
  `.get()` for required settings; ordinary mappings may use `.get()` when
  absence is meaningful.
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
  job.
- Optimize the measured path only; leave the rest at the simplest correct
  implementation.

## pandas

- Declare dtypes at the read boundary (`read_csv(dtype=...)`, an explicit
  `astype` after a query), and validate required columns, nullability, values,
  uniqueness, and cross-column invariants before domain code consumes the data.
- Pass `validate=` to every `merge` and `join` — `"one_to_one"`,
  `"one_to_many"`, or `"many_to_one"`. Without it a duplicate key silently
  multiplies rows, and nothing downstream distinguishes that from real data;
  no schema check or lint rule replaces this cardinality assertion.
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
  its siblings and the error propagates.
- Put a deadline on every call that crosses the network, sync or async —
  `asyncio.timeout` or the client's own timeout argument. Bound fan-out with a
  semaphore and size connection pools explicitly.
- Never swallow `CancelledError`. Clean up and re-raise; suppressing it breaks
  `TaskGroup` and `asyncio.timeout`, which drive shutdown through cancellation.
  `SIM105` will offer `contextlib.suppress` here — that fix is wrong; take the
  re-raise instead.
- Build clients, pools, and sessions in the FastAPI `lifespan` handler, not at
  import time. Import-time I/O breaks startup ordering, hides failures from
  the health check, and makes the module unimportable in a test.

## Failure and diagnosis

- Log through `logging` with lazy `%s` arguments and structured `extra=`
  fields, never `print` or an f-string message. Put the identifiers that make
  an incident searchable — run or partition id, request id, instrument, order
  id — in `extra`, not inside the message text.
- Log the identifying context at the point of failure and re-raise. Catching
  an exception, logging it, and returning a default converts an outage into
  silently wrong output.
- Log the resolved configuration and the input partition at startup, so a
  failed run can be reproduced from its own logs.

## Environment and tools

- Preserve the project's declared Python compatibility range. Do not add,
  remove, or raise its minimum version incidentally. For a new project, choose
  the range from its deployment and dependency constraints, record it in
  `project.requires-python`, configure tools against its floor, and test that
  floor in CI. A `.python-version` selects a development interpreter; it does
  not define the package's compatibility contract.
- Keep dependencies, dev dependencies, and tool configuration in one
  `pyproject.toml`; commit `uv.lock`. Remove `requirements*.txt`, `setup.py`,
  `setup.cfg`, `Pipfile`, and setup scripts.
- Use `uv add`, `uv remove`, `uv sync`, and `uv run`; never `pip install`.
  Standalone scripts use a PEP 723 header and run with `uv run script.py`.
- Copy the Ruff and ty sections from `assets/pyproject.toml` and copy
  `assets/pre-commit-config.yaml` verbatim; never retype or improvise them.
  Read `references/tooling-setup.md` before standardizing a repo's tooling,
  migrating from another type checker, or debugging a hook that disagrees with
  the local command — it covers ty's environment and pre-commit behavior.
- Suppress a Ruff diagnostic with a specific rule code and an adjacent reason;
  the asset rejects blanket, invalid, and stale suppressions outright.
- Expose each entry point as one `uv run` command with no prerequisite shell
  state.
- For a package published to others, read `references/packaging.md`: build
  backend, the `py.typed` marker and `__all__`, `uv build --no-sources`,
  trusted publishing, and verifying the artifact from the index.

## Verification

Before finishing Python work, run:

```text
uv sync --locked
uv run pre-commit run --all-files
```

The hooks are the gate: they run `ruff-format`, `ruff-check --fix`, `ty`, and
`uv-lock` over the project, so a separate `ruff check` pass is duplicate work.
Because `ruff-check` fixes in place, review and stage what it changed rather
than assuming a passing run left the tree alone. Reach for the individual
commands — `uv run ruff check .`, `uv run ty check` — only to read diagnostics
without fixing them, or when a hook and the local command disagree
(`references/tooling-setup.md`).

After dependency or environment changes, also delete only the repo-local
`.venv`, run `uv sync --locked`, and verify the program's imports or entry
point from that fresh environment.
