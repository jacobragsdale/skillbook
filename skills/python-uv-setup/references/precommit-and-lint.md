# Lint, type-check, and pre-commit templates

Copy these three blocks. Adjust only where a comment says to.

## pyproject.toml — ruff

Rationale: rule families chosen to catch real bugs (`F`, `B`), keep imports
and idioms consistent on 3.11 (`I`, `UP`), and kill noise-free wins (`SIM`,
`C4`, `RUF`) — without style-cop families that bury brownfield code in
hundreds of findings.

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = [
    "E4", "E7", "E9", # pycodestyle errors (subset that matters with a formatter)
    "F",              # pyflakes — undefined names, unused imports/vars
    "I",              # isort — deterministic import order
    "UP",             # pyupgrade — modern 3.11 idioms
    "B",              # bugbear — likely bugs (mutable defaults, etc.)
    "SIM",            # simplify — collapsible ifs, redundant bools
    "C4",             # comprehension rewrites
    "RUF",            # ruff-specific correctness checks
]

[tool.ruff.lint.per-file-ignores]
# Add brownfield hotspots here file-by-file; never delete a family above
# to silence one module.
```

## pyproject.toml — pyright

`basic` mode for brownfield — it still catches undefined names, bad calls,
and wrong argument types without demanding annotations everywhere. Once the
repo is clean under `basic`, ratchet to `"standard"` in a dedicated commit.

```toml
[tool.pyright]
pythonVersion = "3.11"
venvPath = "."
venv = ".venv"
typeCheckingMode = "basic"
exclude = [".venv"]
```

## .pre-commit-config.yaml

Pyright runs as a **local** hook via `uv run` — the published mirrors-pyright
hook runs in an isolated environment without the project's dependencies and
produces bogus import errors. `pass_filenames: false` = whole-project check;
pyright is incremental enough for this to stay fast.

The `rev:` pins below go stale — run `uv run pre-commit autoupdate` right
after copying this file in.

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: detect-private-key

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.12.5
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.8.4
    hooks:
      - id: uv-lock   # fails the commit if pyproject.toml changed without uv.lock

  - repo: local
    hooks:
      - id: pyright
        name: pyright
        entry: uv run pyright
        language: system
        types: [python]
        pass_filenames: false
```

## Install and first run

```bash
uv add --dev ruff pyright pre-commit
uv run pre-commit install
uv run pre-commit run --all-files
```

Brownfield first-run order: let `ruff-check --fix` and `ruff-format` do their
thing, review `uv run ruff check --unsafe-fixes --fix` output before
accepting, hand-fix what's left, and only then reach for per-file-ignores.
