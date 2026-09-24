# tui-template — conventions for every contributor

Rust, ratatui 0.30, crossterm 0.29, edition 2024. Scaffolded from the
`rust-tui` skill; that skill's references explain every pattern here.

## The rules

1. **The UI thread never blocks on IO.** IO runs on a worker thread
   (`src/worker.rs`) and answers over `std::sync::mpsc`; the loop only polls.
   An async-only driver gets a current-thread tokio runtime *inside* its
   worker thread; nothing async leaves that module.
2. **The app is pure.** `src/app/` turns events into state and `Action`s and
   reads no clock (every `Instant` is passed in). `src/ui/` renders `&App`
   and returns the `Hits` it drew. `src/run/` owns the terminal, the worker
   and time, and carries out `Action`s.
3. **Mouse first.** Everything a key does, something on screen does too. A
   button is `Target::Button(key)`: clicking it is exactly pressing that key,
   and it is drawn only where the key acts. Clicks fire on release, on the
   spot that was pressed. The wheel scrolls what is under the pointer and
   never moves the focus.
4. **Redraw only when something changed.** An idle app draws nothing.
5. **Verify headlessly.** `--replay FILE` drives the real loop against a
   `TestBackend` and prints frames as text. Screenshots are never the
   verification.
6. **Measure, don't guess.** `TUI_TEMPLATE_TRACE=<file>` logs frame times.
   Budgets: key-to-frame < 16 ms, draw cost independent of row count.

## Checks before any commit

```
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-targets
NO_COLOR=1 cargo test --all-targets
cargo run -- --replay scripts/smoke.keys src
```

## Style

- Colours live only in `src/ui/theme.rs`; everything else asks for a token.
  Design in ANSI-16 first; the UI must read under `NO_COLOR`.
- Keys live only in `KEYS` (`src/app/mod.rs`); help, footer, README and
  tests read it.
- Widths are terminal cells (`unicode-width`), never `char`s.
- No trait with one implementation; an enum or a match instead.
- `anyhow` at the edges; worker errors cross threads as `String`s.
- Tests assert whole lines of rendered text and colours through tokens.
- Doc comments explain why, not what. Mark deliberate shortcuts with a
  `// ponytail:` comment naming the ceiling and the upgrade path.
