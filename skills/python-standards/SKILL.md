---
name: python-standards
description: "Enforce high-integrity Python implementation and tooling; exclude test design. Use when coding, reviewing, profiling, or configuring Python, Pydantic, performance, uv, Ruff, ty, FastAPI, asyncio, tooling, or dependencies — even if unrequested."
---

# Python house standard

These rules cover the Python you write or change. In someone else's repo, its
own config, tools, and conventions win: do not migrate its tooling, tighten
its checks, add a dependency, or refactor code the task does not touch.
Jacob's own repos also get the house libraries and tooling in
[Jacob's own repos](#jacobs-own-repos). A repo is his own only when its
`AGENTS.md` says the house Python standards apply, he says so, or you are
creating a new repo for him; when you create one, add that line to its
`AGENTS.md`.

## Types

- Do not write `Any` in first-party interfaces. Model an unknown payload as
  `object` and narrow it, or type the shape it actually has. Keep an untyped
  dependency behind a narrow typed wrapper so neither `Any` nor ty's inferred
  `Unknown` leaks past it.
- Keep type-checker fixes in the type domain: no runtime branches or
  assertions added only to satisfy the checker. Suppress with a named rule and
  an adjacent reason (`# ty: ignore[rule]` under ty), never a blanket ignore.
- Use `None` only when absence is a valid domain state, not for partial
  construction, missing required input, or error signaling.

## Boundaries and domain

- Validate I/O boundaries — configuration, network and queue messages, files,
  database rows, CLI input, tabular data, outbound payloads — before domain
  code consumes them or another system receives them. Convert to typed domain
  objects; do not pass raw mappings through the core.
- Schema validation does not establish freshness, sequence continuity,
  referential integrity, completeness relative to the source, provenance,
  reconciliation, or risk limits. Enforce those invariants explicitly and fail
  before acting when they are unknown.
- Never choose `float` implicitly for money, prices, quantities, or rates.
  Pick the representation from required precision, range, and units; make
  rounding explicit; reject non-finite values at the boundary.
- Normalize external timestamps to timezone-aware UTC at the boundary.
- Pass clocks, random generators, and I/O clients in as parameters instead of
  reading hidden process state.
- Catching an exception, logging it, and returning a default turns an outage
  into silently wrong output. Log the identifying context and re-raise.
- Do not change the project's `requires-python` range as a side effect.

## pandas

- Declare dtypes at the read boundary (`read_csv(dtype=...)`, an explicit
  `astype` after a query), and validate required columns, nullability,
  uniqueness, and cross-column invariants before domain code uses the frame.
- Pass `validate=` to every `merge` and `join` — `"one_to_one"`,
  `"one_to_many"`, or `"many_to_one"`. Without it a duplicate key silently
  multiplies rows, and nothing downstream tells that apart from real data.
- Never rely on index alignment across differently indexed objects:
  arithmetic between them yields `NaN` instead of raising. Merge on an
  explicit key, or reindex deliberately.

## Async and FastAPI

- Declare a FastAPI path operation or dependency `def` when its body calls
  blocking code — FastAPI runs `def` handlers in a threadpool — and
  `async def` only when the body awaits.
- Put a deadline on every call that crosses the network, sync or async, and
  bound fan-out with a semaphore.
- Never swallow `CancelledError`; clean up and re-raise. Ruff's `SIM105`
  offers `contextlib.suppress` here — that fix is wrong.
- Build clients, pools, and sessions in the FastAPI `lifespan` handler, not at
  import time.

## Jacob's own repos

- Use Pydantic for record and object boundaries with this config. Lax mode is
  deliberate: do not add `strict=True`.

  ```python
  model_config = ConfigDict(
      extra="forbid",
      frozen=True,
      validate_default=True,
      revalidate_instances="always",
      allow_inf_nan=False,
  )
  ```

  Do not use `model_construct()` or unvalidated `model_copy(update=...)` with
  boundary data. Keep validation at ingress in hot paths too; replace a model
  with a dataclass only after measuring.
- Load configuration once at startup through a `pydantic-settings`
  `BaseSettings` using the options above. Give environment-backed fields no
  default, so missing configuration stops startup. Never read required
  settings with `os.getenv` or `os.environ.get`. Commit `.env.example`,
  gitignore the rest of `.env*`, load it with `uv run --env-file .env`, and
  never call `load_dotenv()`.
- Copy the Ruff and ty sections of `assets/pyproject.toml` and all of
  `assets/pre-commit-config.yaml` verbatim. Read
  `references/tooling-setup.md` before creating or standardizing a repo,
  migrating from another type checker, or debugging a hook.
- For a package published to others, read `references/packaging.md`.

## Verification

Run the repo's own checks — from its `AGENTS.md`, CI config, or pre-commit
config. In a repo with the house assets, that is:

```text
uv sync --locked
uv run pre-commit run --all-files
```

`ruff-check --fix` edits in place, so review what it changed. Run
`uv run ruff check .` or `uv run ty check` only to read diagnostics without
fixing them.
