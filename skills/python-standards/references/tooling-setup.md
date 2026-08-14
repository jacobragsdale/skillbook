# Tooling setup

Read when standardizing a repo's tooling, migrating a type checker, or
debugging a hook that behaves differently from the local command.

## Standardize a repo

After copying the assets in:

```bash
uv add --dev ruff ty pre-commit
uv run pre-commit autoupdate
uv run pre-commit install
```

`pre-commit autoupdate` moves the `rev` pins. After it runs, re-align
`required-version` in `[tool.ruff]` with the `ruff-pre-commit` rev, and the
pinned `ty` dev dependency with the `ty-pre-commit` rev. ty has no
`required-version` setting, so that pairing is manual.

The asset intentionally sets neither Ruff's `target-version` nor ty's
`environment.python-version`. Both infer the minimum supported version from
`project.requires-python`; when a project cannot declare that field, set ty's
version explicitly — project configuration, not a house-wide pin.

## Hooks that do not run

Configuration alone does not install the repo-local Git hook — a fresh clone
has `.pre-commit-config.yaml` but no hook. Resolve the active path with
`git rev-parse --git-path hooks/pre-commit`; if the file is absent, run
`uv run pre-commit install`.

## ty resolves the wrong environment

Run `uv sync --locked` first. Locally, ty uses the active environment or a
project-root `.venv`; use `uv run ty check -v` to inspect its search paths. The
official pre-commit hook resolves dependencies from the project's
`pyproject.toml` through uv and does not use `additional_dependencies`. If the
hook and `uv run ty check` disagree, compare the pinned ty versions and the uv
groups selected by the hook before changing import rules.

## Migrating from another type checker

Remove the old checker, its config, hook, and suppressions in the same change.
Copy the asset's `[tool.ty]` tables, then run `uv run ty check`. Translate only
genuine exceptions to a specific `# ty: ignore[rule]` with an adjacent reason;
do not mechanically preserve disabled diagnostics from the previous checker.

## Staged adoption

Only when the user explicitly chooses staged adoption over fixing the backlog.
ty has no checked-in diagnostic baseline. Prefer migrating one owned package or
directory at a time and keep new or migrated code under the standard config.
When that split is impossible, use the narrowest file-pattern override or
specific suppression available, record why it exists, and remove it as the
backlog shrinks. Never turn off a rule for the whole project merely to make the
first run pass.

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
