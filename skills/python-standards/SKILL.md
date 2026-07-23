---
name: python-standards
description: "Enforce high-integrity Python types, I/O, performance, and tooling. Use when coding, reviewing, profiling, or configuring Python, uv, Ruff, basedpyright, Pydantic, pandas, FastAPI, asyncio, or dependencies — even if unrequested. Not for test design."
---

# Python house standard

Apply these rules to all first-party Python. Optimize for explicit guarantees,
then choose the simplest implementation that preserves them.

## Types and state

- Annotate every function. Rely on inference only for locals whose resulting
  type remains precise.
- Run basedpyright in `recommended` mode over all owned code and require zero
  diagnostics. Do not downgrade the mode for brownfield code; use a checked-in
  baseline only when the user explicitly chooses staged adoption.
- Do not let `Any` or `Unknown` escape an untyped dependency adapter. Add a
  stub, `Protocol`, or narrow validated wrapper instead.
- Keep type-checker fixes in the type domain. Do not add runtime branches or
  assertions solely to appease the checker. Use a narrow
  `# pyright: ignore[specificRule]` only with a reason.
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
- Choose numeric representations from required precision, range, and units;
  never choose `float` implicitly for money, prices, quantities, or rates.
  Make rounding explicit and reject non-finite boundary values.
- Normalize external timestamps at the boundary to timezone-aware UTC.

## Performance and concurrency

- Treat Ruff `PERF` findings as inexpensive micro-optimization leads, not
  evidence that a hot path became faster. Measure representative end-to-end
  P50/P99/P99.9 latency, throughput, and allocations before and after a change.
- Profile before changing representations or adding concurrency. Optimize the
  measured bottleneck and include warm-up, realistic batch sizes, and production
  I/O behavior in the benchmark.
- Never block an event loop with synchronous HTTP, file, subprocess, sleep, or
  input calls. Use an async implementation or explicitly offload blocking work.
- In pandas paths, make mutation and array conversion explicit. Avoid
  `inplace=True` and ambiguous `.values`; for latency-sensitive operations,
  compare pandas, NumPy, and specialized representations with realistic data.

## Environment and tools

- Pin Python 3.11 in `.python-version` and set `requires-python = ">=3.11"`.
  Do not upgrade it incidentally.
- Keep dependencies, dev dependencies, and tool configuration in one
  `pyproject.toml`; commit `uv.lock`. Remove `requirements*.txt`, `setup.py`,
  `setup.cfg`, `Pipfile`, and setup scripts.
- Use `uv add`, `uv remove`, `uv sync`, and `uv run`; never `pip install`.
  Standalone scripts use a PEP 723 header and run with `uv run script.py`.
- When setting up or standardizing a repo, copy the Ruff and basedpyright
  sections from `assets/pyproject.toml` and copy
  `assets/pre-commit-config.yaml`; do not retype them. Then run
  `uv add --dev ruff basedpyright pre-commit`,
  `uv run pre-commit autoupdate`, and `uv run pre-commit install`.
- Keep the asset's `PERF`, `ASYNC`, `FAST`, and curated pandas-vet rules enabled
  in every repo. They remain inactive when the matching constructs are absent;
  do not generate dependency-specific Ruff configurations. `ASYNC109` stays
  ignored because timeout parameters can be deliberate API design.
- When pre-commit is already configured for a repo, resolve the active hook
  path with `git rev-parse --git-path hooks/pre-commit`. If that file is
  absent, run `uv run pre-commit install`; configuration alone does not
  install the repo-local Git hook.
- Expose each entry point as one `uv run` command with no prerequisite shell
  state.

## Verification

Before finishing Python work, run:

```text
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pre-commit run --all-files
```

After dependency or environment changes, also delete only the repo-local
`.venv`, run `uv sync --locked`, and verify the program's imports or entry
point from that fresh environment.
