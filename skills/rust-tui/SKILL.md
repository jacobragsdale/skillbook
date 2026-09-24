---
name: rust-tui
description: "Build Rust ratatui + crossterm TUIs in Jacob's mouse-first house style. Use when the user starts or changes a terminal UI (panes, mouse, scrolling, theme, workers, tokio, perf), even if they don't say ratatui. Not for plain CLIs."
---

# Rust TUI

Scaffold and extend ratatui 0.30 + crossterm 0.29 apps the way az-tui,
sql-bench and ticket-tui (all in `~/dev`) are built: mouse-first, clean,
fast, pure state, verified headlessly. These rules replace generic ratatui
tutorial patterns (ratatui's `Table`/`Scrollbar`/stateful widgets for
interactive lists, an async `EventStream` loop, redrawing every tick,
colours inline).

## Workflow

### A new app

1. Run the scaffolder. It copies `assets/template`, renames the crate, lib
   path and env vars, formats, runs clippy, tests and the replay smoke run,
   then makes the first commit:

   ```bash
   uv run <this-skill-dir>/scripts/new_tui.py <name> --description "<one line>"
   ```

   Default parent is `~/dev`. The result is a working two-pane directory
   browser; `--help` covers the flags.
2. Replace the domain and keep the shell. Domain: `worker.rs` (`Request`,
   `Event`, `Entry`, `serve`), the columns in `app/mod.rs` and
   `ui::columns`, the details fields, and the rows in `ui::list`. Shell,
   kept as is: the loop, `pointer.rs`, `theme.rs`, `trace.rs`, replay, the
   status bar, help, tests' helpers.
3. Update `KEYS`, the README keys table (a test checks it) and the app's
   `smoke.keys` replay in the same change as the keys themselves.
4. Create the GitHub repo and push only when the user asks.

### An existing app

Read the repo's `AGENTS.md`/`CLAUDE.md` first; its rules win over this
skill (sql-bench freezes dependencies and tags commits `[T2.1]`). Find the
existing pattern (`Hits`/`PointerRegion`, `KEYS`/`COMMANDS`, the theme
tokens) and extend it rather than importing the template's version.

## The rules

1. **The UI thread never blocks.** All IO runs on a named `std::thread`
   worker that answers over `std::sync::mpsc`; the loop only `try_recv`s.
2. **The app is pure.** `app/` turns events into state and returns
   `Outcome { actions, repaint }`; it reads no clock (every `Instant` is a
   parameter) and does no IO. `ui::render(&mut Frame, &App, &Theme) -> Hits`
   changes nothing. `run/` owns the terminal, workers, time and `Action`s.
3. **Mouse first.** Everything a key does, something on screen does, and
   every button *is* a key: `Target::Button(KeyEvent)` calls `App::key`.
   Draw a button only where its key acts. Clicks fire on release on the
   pressed spot; the wheel scrolls what is under the pointer and never moves
   focus; focus follows the click.
4. **Redraw only when dirty.** An idle app draws no frames; hover repaints
   only when the lit target changes; a press paints nothing.
5. **Tokens, not colours.** Only `ui/theme.rs` names a `Color`. ANSI-16
   first; everything must read under `NO_COLOR` (mono preset).
6. **Verify headlessly.** `--replay` scripts and `TestBackend` line asserts.
   Screenshots are never the verification.
7. **Measure, don't guess.** `<APP>_TRACE=<file>`; key-to-frame < 16 ms and
   draw cost independent of row count, held by `#[ignore]` timing tests.

## Checklist: adding a feature

Copy this and tick it off:

```
- [ ] Key in KEYS (name parses with key_named) and in the README table
- [ ] A clickable way to do it: Button(key), a Target variant, or a menu entry
- [ ] App::acts(name) true only where the key acts; footer hint if it earns one
- [ ] IO as an Action -> Driver::dispatch -> worker; answer echoes its key
- [ ] Empty, loading and error states in one line, in the source's words
- [ ] Draws at the minimum size, 80x24 and wide; NO_COLOR still reads
- [ ] Render test (whole lines) + mouse test; the button invariant test still passes
- [ ] A replay script reaches it with expect lines; the smoke replay still passes
```

## Decision rules

- **Threads or tokio.** Default std threads and blocking clients (`ureq`,
  `rusqlite`, `std::process`). When a driver is async-only, build a
  current-thread tokio runtime *inside* the worker thread and `block_on`
  there; nothing async leaves that module. Never `#[tokio::main]` around the
  UI. Pattern: `references/architecture.md` → Tokio inside a worker.
- **Stale answers.** Echo the key and drop mismatches by default; a
  generation counter for search-as-you-type; an `AtomicBool` to stop work in
  progress. Restore cursors by identity, never index.
- **Traits.** None with one implementation: enums and `match` (screens,
  backends, clipboards). A trait earns its place with two real
  implementations, or a connector plus a test fake.
- **Dependencies.** The house set: `anyhow`, `clap` (derive), `crossterm`,
  `ratatui`, `serde`, `toml`, `unicode-width`; as needed `serde_json`,
  `tempfile` (atomic writes), `time` or `jiff`, `ureq` 3, `rusqlite`
  (bundled), `nucleo-matcher`, `tokio` (worker only). Hand-roll paths, OSC 52
  and base64 instead of `dirs`/`base64`/`arboard`. Ask before adding one
  outside this list.
- **Files.** Split past ~1,000 lines; tests mirror the tree.
- **Shortcuts.** A deliberate ceiling gets `// ponytail: <ceiling>; <upgrade
  path>`.

## Gotchas

- Turn mouse capture **off before** `ratatui::restore()` leaves the alternate
  screen, or the shell receives every mouse move as escape codes. The
  template's `Restore` guard and panic hook do this; keep them.
- `ratatui::try_init`'s panic hook restores the terminal on *any* thread's
  panic. The template's hook restores only for `main`; worker panics go to
  the trace and arrive as `Event::Stopped`.
- Handle `KeyEventKind::Press` only; Windows also sends release and repeat.
- crossterm folds a fast `Esc` + char into `Alt-char`. Where Esc matters,
  split it back into Esc then the char (az-tui `handle_key`).
- `muted` text on the `selected` background can vanish (DarkGray on
  DarkGray): draw the cursor row's weak cells in `text`.
- `TestBackend` renders are theme-dependent through tokens; CI reruns the
  suite per preset, so never assert a named colour.
- Width is cells: `unicode-width`, `fit()` with `…`; `char` counts break on
  CJK and emoji.
- When stdin is not a TTY, crossterm silently reads `/dev/tty`; check
  before spawning an input reader (sql-bench `run/mod.rs:140`).

## References

Read the one that matches the work; each has a table of contents.

- `references/architecture.md`: **read** when adding IO, a worker, tokio,
  timers, cache/session/config, subcommands, `$EDITOR` hand-off, or tabs.
- `references/mouse.md`: **read** when adding anything clickable,
  draggable, scrollable, an overlay, a menu, or text selection.
- `references/look-and-feel.md`: **read** when drawing panes, tables,
  status/tab bars, overlays, states, or touching colour and the shared
  `theme` palette.
- `references/verification.md`: **read** before calling a UI change done,
  and when a change could cost frames (big lists, filters, sorting).
- `scripts/new_tui.py`: **run** to scaffold a new app.
- `assets/template/`: **read** for the working reference implementation.
  `new_tui.py` copies it; do not edit copies of it in place of the template.

## Validation

A change is done when all of these pass in the app's repo:

```bash
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-targets && NO_COLOR=1 cargo test --all-targets
cargo run -- --replay <app>/scripts/smoke.keys src    # plus the feature's own script
cargo test --release -- --ignored                     # when the change touches lists, filters or drawing
```

If a render test fails after an intended layout change, print the frame
(`screen_text(terminal.backend().buffer())`), check it line by line, then
update the expectation. Never loosen a whole-line assert to a substring to
make it pass.

## Example

Request: "Add a 'hidden files' toggle to the log-view app."

Result:
- `KEYS` gains `key(".", "show hidden files", false)`; the README table
  gains `` | `.` | show hidden files | ``.
- `App` gains `show_hidden: bool`; `refilter` skips names starting with `.`
  unless it is set; `browse_key` flips it on `Char('.')`.
- `ui::list` adds a `("◌ Hidden", ".")` chip over the top border, a
  `Button`, so a click is exactly the key.
- A render test shows `.env` only after pressing `.`; the button invariant
  test now counts the chip.
- A replay run at the repo root: `key .` then `expect .gitignore`.
- The gate passes; the commit message is one sentence stating the outcome.
