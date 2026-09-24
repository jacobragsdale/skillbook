# Performance and verification

Read when a change could cost frames (big lists, filters, sorting, wrapped
text), when writing tests, or before calling a TUI change done.

## Contents

- [Budgets](#budgets)
- [Staying fast](#staying-fast)
- [Measuring](#measuring)
- [Render tests](#render-tests)
- [Replay](#replay)
- [Beyond replay](#beyond-replay)
- [Gate and CI](#gate-and-ci)

## Budgets

| What | Budget | How it is checked |
|---|---|---|
| Key to frame | < 16 ms | trace `frame draw_ms`, ignored timing test |
| Draw cost | independent of row count | timing test at 100k rows |
| Filter keystroke | < 16 ms at 100k rows | timing test |
| Startup to first frame | < 50 ms | trace `start` → first `frame` |
| Idle | zero frames | `run/tests.rs` frame counter |
| Pointer resting / press | ≤ 1 frame / 0 frames | loop tests |

Timing tests are `#[ignore = "a timing: cargo test --release -- --ignored"]`,
use made-up rows (no network, no database), and assert against the budget
(sql-bench asserts 2× budget to absorb CI noise).

## Staying fast

- Format only the visible window: iterate `visible.iter().skip(top)` zipped
  with the row range. Never build a `Vec<Row>` for the whole list.
- Precompute per listing, not per keystroke: lower-cased haystacks, a
  `sorted: Vec<usize>` rebuilt only when sort or rows change, `visible`
  rebuilt only when the query changes (az-tui `ListState`, template `App`).
- Column widths: incremental over each new batch only, capped (sql-bench
  `WIDTH_CAP = 40`), measured in cells.
- No allocation in comparisons: `cmp_ignore_ascii_case`, index tiebreaks.
- Fuzzy search: `nucleo-matcher` with pre-converted `Utf32String`s in an
  `Arc<Vec<_>>`, scored on a worker, generation-guarded (ticket-tui). Plain
  substring over lower-cased names is enough below ~50k rows (az-tui:
  40k rows in ~2 ms); mark the ceiling with `// ponytail:`.
- Hash indexes for lookups by key; windowed trees (siblings ±3, children
  capped with `… N more`).
- Cap held text: `LOG_LINE_CAP` lines, byte budgets with oldest-first
  eviction.
- Batch channel traffic (500 rows per message) and drain everything queued
  before one paint; `DRAIN_LIMIT` 50 ms stops a flood from starving frames.
- Debounce writes (session, cache) with a settle timer; stat files at most
  once a second.

## Measuring

`<APP>_TRACE=<file>` (template `trace.rs`) appends `unix_ms\tkind\tk=v`.
When unset, no clock is read and nothing is formatted; check `is_on()`
before building fields. Kinds: `frame draw_ms`, `turn draw_ms input_ms`
(only turns ≥ 30 ms), `panic message`; add `start`, `connect`, `query` as the
app grows. Durations are fractional ms (`{:.3}`).

```sh
TUI_TEMPLATE_TRACE=/tmp/t.tsv cargo run --release -- ~/big-dir
awk -F'\t' '$2=="frame"{split($3,a,"=");print a[2]}' /tmp/t.tsv | sort -n | awk '{v[NR]=$1}END{print "p95", v[int(NR*0.95)]}'
```

Record measured numbers with the commit hash when they change (sql-bench
`scripts/perf.sh` → `docs/PERF.md`).

## Render tests

Helpers (template `ui/tests.rs`):

```rust
fn theme() -> Theme            // Theme::select(None, &default, real env): CI's preset matrix reaches it
fn app(dirs, files) -> App     // App::new + apply(Event::Listed { .. }) with fixed SystemTimes
fn draw(&mut App, w, h) -> (Terminal<TestBackend>, Hits)   // also calls app.drawn(&hits)
fn line(&terminal, y) -> String                           // one row, right-trimmed
fn click / mouse(app, &hits, kind, (x, y), now)           // synthetic MouseEvents
fn rect(&hits, |t| matches!(t, Target::Rows { .. }))      // find things by target, not coordinates
```

- Assert whole lines over substrings. Keep lines that depend on the app
  name or the clock out of exact asserts, or build them with
  `env!("CARGO_PKG_NAME")`.
- Assert colours through tokens (`theme().selected.bg`), never named colours,
  so the suite passes under every preset.
- Locate targets through `Hits`, not hard-coded coordinates, so layout
  changes do not break unrelated tests.
- Test names are sentences: `a_click_outside_help_closes_it_and_reaches_nothing_underneath`.
- Parity tests: every `KEYS` name parses with `key_named`; the README lists
  every key; every key a screen handles is in `KEYS` (sql-bench).
- Fakes enter through closures or an enum, never a trait with one
  implementation. When a trait does earn it (two real backends, or a
  connector plus a test fake), tests pass a `Box<dyn ..>` fake (ticket-tui
  `SourceConnector`, az-tui `Transport`).

## Replay

`--replay FILE [--size CxR] [--frames-dir DIR]` steps the real
`Driver::turn` with a `Queue` input source against a `TestBackend`. This is
how an agent sees the app. Grammar (template `run/replay.rs` header):

```
key <name>        type <text>      paste <text>      resize <C>x<R>
click|double-click|hover <x> <y>|on <text>           scroll up|down <x> <y>|on <text>
drag <x1> <y1> <x2> <y2>           wait              frame <name>
expect <text>     expect-not <text>
```

Exit codes: 0 ok, 3 a `wait` timed out, 4 an `expect` failed (the screen
goes to stderr). After each command the driver turns until the queue and
any held click are handled, then once more to paint.

Workflow for a UI change:

1. Write or extend a `.keys` script that reaches the change (`click on
   <label>` survives layout changes better than coordinates).
2. `cargo run -- --replay scripts/<x>.keys --size 100x30` and read the
   printed frames. Check 40x10 (the minimum), 80x24 and a wide size.
3. Add the `expect` lines that would have caught the bug; keep the script
   in `scripts/` and run it in CI.

sql-bench adds `--frame-styles` (writes `<row> <from>..<to> fg= bg= mod=`
runs for style diffs, used to compare NO_COLOR frames) and waits on text
(`wait text <s>`); add them when needed.

## Beyond replay

- **pty walk** (az-tui `scripts/walk.py`): a PEP 723 script with `pyte`,
  `pty.fork()`, `TIOCSWINSZ`, scratch `XDG_*` dirs and fake CLIs first on
  `PATH`; asserts the screen and the exact external calls. Use when the app
  shells out or the terminal handshake itself matters.
- **Terminal hygiene** (sql-bench `scripts/qa/`): mouse capture on
  (`\e[?1000h`, `\e[?1006h`) and off before the alternate screen is left;
  panic restores the terminal (a hidden debug-only `--panic-after-ms`);
  stdin EOF quits cleanly.
- **Headless subcommands** give every feature a non-TUI door for scripted
  checks (`show --json`, `query`, `doctor`).

## Gate and CI

Before every commit:

```sh
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-targets
NO_COLOR=1 cargo test --all-targets
cargo run -- --replay scripts/smoke.keys src
```

CI (template `.github/workflows/ci.yml`): ubuntu + macOS, `fail-fast:
false`, `dtolnay/rust-toolchain@stable` with clippy and rustfmt,
`Swatinem/rust-cache@v2`, the gate above, the suite again per preset
(`NO_COLOR=1`, `<APP>_THEME=terminal-light`), `cargo build --release`, the
ignored timing tests in release, the replay smoke run. az-tui also proves
the README install path: `cargo install --path . --locked --root
$RUNNER_TEMP/install` then `--version`.

Clippy is the default lint set with `-D warnings`; there is no `[lints]`
table. The code is still written pedantic-clean by hand: `#[must_use]` on
getters and constructors, `const fn` where possible, `u16::try_from(..)
.unwrap_or(..)` and `saturating_*` instead of `as`, and any `#[allow]` is
local with a comment saying why.
