# Tooling setup

Read when standardizing a repo's tooling, migrating a type checker, or
debugging a hook that behaves differently from the local command.

## Standardize a repo

Copy the Ruff and pyrefly sections from `assets/pyproject.toml` and copy
`assets/pre-commit-config.yaml`; do not retype them. Then:

```bash
uv add --dev ruff pyrefly pre-commit
uv run pre-commit autoupdate
uv run pre-commit install
```

`pre-commit autoupdate` moves the `rev` pins. After it runs, re-align
`required-version` in `[tool.ruff]` with the `ruff-pre-commit` rev, and the
pinned `pyrefly` dev dependency with the `pyrefly-pre-commit` rev. Pyrefly has
no `required-version` setting, so that pairing is manual.

## Hooks that do not run

Configuration alone does not install the repo-local Git hook — a fresh clone
has `.pre-commit-config.yaml` but no hook. Resolve the active path with
`git rev-parse --git-path hooks/pre-commit`; if the file is absent, run
`uv run pre-commit install`.

## pyrefly resolves the wrong environment

Keep `python-interpreter-path = ".venv/bin/python"` in `[tool.pyrefly]`. The
`pyrefly-check` hook runs inside pre-commit's own virtualenv, so without it
pyrefly resolves imports and the standard library against that environment and
reports `missing-import` for every real dependency — while the bare
`uv run pyrefly check` passes.

## Migrating from mypy or pyright

`uv run pyrefly init` converts an existing mypy or pyright config in place.
Replace the translated result with the asset's `[tool.pyrefly]` section rather
than keeping the migrated severities, which reproduce the old checker's
weaker defaults.

## Staged adoption with a baseline

Only when the user explicitly chooses staged adoption over fixing the backlog.
A baseline keeps `preset = "all"` active: it suppresses only the recorded
diagnostics, tolerates line drift, and still fails on new ones.

```bash
uv run pyrefly check --baseline pyrefly-baseline.json --update-baseline
```

`--update-baseline` requires the explicit `--baseline` flag even when the
`baseline` config key is set. Set `baseline` in `[tool.pyrefly]` so the bare
`pyrefly check` in the hook reads it. Pyrefly does not prune entries as they
are fixed, so re-run the update command periodically; otherwise the baseline
hides regressions instead of shrinking.

## Ruff notes

- The asset uses `extend-select`, so Ruff's own defaults stay on and the list
  adds to them. Never convert it to `select`, which replaces them. Ruff 0.16
  or newer is required for that default set.
- `flake8-bandit` (`S`) is disabled in the asset's `ignore` list, which also
  turns off the three `S` rules Ruff enables by default. Re-select `S` for a
  repo that handles untrusted input and wants the audit.
- `ruff format` also formats Python inside Markdown code blocks. Expect
  `ruff format --check .` to flag documentation on the first run in an
  existing repo; reformat it rather than excluding Markdown.
- `ASYNC109` stays ignored because timeout parameters can be deliberate API
  design. Keep `PERF`, `ASYNC`, `FAST`, and the pandas-vet rules enabled in
  every repo; they stay inactive when the matching constructs are absent. Do
  not generate per-dependency Ruff configurations.
