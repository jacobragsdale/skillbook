# Tooling setup

Read when creating a repo or standardizing one on request, migrating a type
checker, or debugging a hook that behaves differently from the local command.

## Contents

- [House repo layout](#house-repo-layout)
- [Standardize a repo](#standardize-a-repo)
- [Hooks that do not run](#hooks-that-do-not-run)
- [ty resolves the wrong environment](#ty-resolves-the-wrong-environment)
- [ty skips the rules on PEP 723 scripts](#ty-skips-the-rules-on-pep-723-scripts)
- [Migrating from another type checker](#migrating-from-another-type-checker)
- [Staged adoption](#staged-adoption)
- [Ruff and ty notes](#ruff-and-ty-notes)

## House repo layout

- Keep dependencies, dev dependencies, and tool configuration in one
  `pyproject.toml`; commit `uv.lock`. Remove `requirements*.txt`, `setup.py`,
  `setup.cfg`, `Pipfile`, and setup scripts.
- For a new project, choose `project.requires-python` from its deployment and
  dependency constraints, configure tools against that floor, and test the
  floor in CI. A `.python-version` picks a development interpreter; it does
  not define the compatibility range.
- Expose each entry point as one `uv run` command with no prerequisite shell
  state.
- Commit `.env.example`, gitignore the rest of `.env*`, load the file with
  `uv run --env-file .env`, and never call `load_dotenv()`.
- Decorate every overriding method with `@override` (the asset's ty rules
  enforce it); import it from `typing_extensions` when the floor predates 3.12.
- After a dependency or environment change, delete only the repo-local
  `.venv`, run `uv sync --locked`, and check the entry point imports from the
  fresh environment.

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

## ty skips the rules on PEP 723 scripts

ty checks a file with a `# /// script` header as its own project: the
enclosing `ty.toml` or `[tool.ty]` does not reach it, so `all = "error"` and
the analysis settings silently fall back to ty's defaults (seen in ty 0.0.95).
For a repo of standalone scripts, run `ty check --config-file ty.toml` and set
`environment.python-version` to the scripts' `requires-python` floor.

## Migrating from another type checker

Remove the old checker, its config, hook, and suppressions in the same change.
Copy the asset's `[tool.ty]` tables, then run `uv run ty check`. Translate only
genuine exceptions to a specific `# ty: ignore[rule]` with an adjacent reason;
do not mechanically preserve disabled diagnostics from the previous checker.

## Staged adoption

Only when the user explicitly chooses staged adoption over fixing the backlog.
Prefer migrating one owned package or directory at a time and keep new or
migrated code under the standard config. ty's checked-in diagnostic baseline
(`baseline = "ty-baseline.json"` with `ty check --update-baseline`) is still a
preview feature; use it only when the user accepts that.
When that split is impossible, use the narrowest file-pattern override or
specific suppression available, record why it exists, and remove it as the
backlog shrinks. Never turn off a rule for the whole project merely to make the
first run pass.

## Ruff and ty notes

- The asset selects `ALL` and lists each rule it turns off with a reason, so
  a Ruff upgrade turns on new stable rules. Because the version is pinned,
  that happens only when the pin moves; fix or suppress what the new rules
  report in the same change. Never switch back to an `extend-select` list, and
  never delete a reason from the `ignore` list.
- ty's `all = "error"` works the same way: every ty rule is an error,
  including those ty leaves off by default. Turn one off only for a real false
  positive, by name, with the reason beside it.
- `flake8-bandit` (`S`) is disabled in the asset's `ignore` list. Re-select `S`
  for a repo that handles untrusted input and wants the audit.
- `ruff format` also formats Python inside Markdown code blocks. Expect
  `ruff format --check .` to flag documentation on the first run in an
  existing repo; reformat it rather than excluding Markdown.
- `ASYNC109` stays ignored because timeout parameters can be deliberate API
  design. Keep `PERF`, `ASYNC`, `FAST`, and the pandas-vet rules enabled in
  every repo; they stay inactive when the matching constructs are absent. Do
  not generate per-dependency Ruff configurations.
