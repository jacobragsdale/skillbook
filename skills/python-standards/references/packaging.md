# Publishing a public package with uv

Read when a project is distributed to others — PyPI or an internal index.
Internal applications and batch jobs do not need any of this.

## Build backend

Use `uv_build` for pure Python; it is uv's own backend and needs no plugin:

```toml
[build-system]
requires = ["uv_build>=0.9"]
build-backend = "uv_build"
```

`uv_build` is pure-Python only. A package with C, Cython, or Rust extensions
needs `hatchling`, `setuptools`, or `maturin` instead.

## Make the package typed

A library whose types are invisible to consumers is untyped from their side.

- Ship `py.typed` (empty file) inside the package directory, and include it in
  the wheel — `uv_build` picks up package data automatically.
- Declare the public surface with `__all__` in the top-level `__init__.py`.
  Anything absent from it is internal and may change without a major bump.
- Do not re-export third-party types in public signatures unless that
  dependency is part of the contract; it pins consumers to your version range.
- `requires-python` is a promise. Test against the floor version in CI, not
  only the newest.

## Release

```bash
uv version --bump minor        # or: uv version 1.2.0
uv build --no-sources          # verifies the build without tool.uv.sources
uv publish
```

`--no-sources` catches a package that only builds because of local path or
workspace overrides — it would fail for anyone installing from the index.

Publish from CI with PyPI Trusted Publishing rather than a stored token. The
job needs `id-token: write`; without that permission `uv publish` falls back
to an unauthenticated upload that PyPI rejects after the job looks successful.

## Verify the published artifact

Install it as a stranger would, outside the project:

```bash
uv run --with <package> --no-project -- python -c "import <package>"
```

Add `--refresh-package <package>` when a cached version shadows the new one.
Verifying an import from the built wheel catches the two failures a green
build hides: a missing subpackage in the wheel, and a runtime dependency that
is only listed as a dev dependency.

## Versioning

- Semantic versioning against `__all__`, not against the whole module tree.
- A change in validation strictness, a default value, or an exception type is
  a breaking change even when the signature is unchanged.
- Deprecate before removing: keep the old name working for one minor release
  and emit `DeprecationWarning` with the replacement named in the message.
