# Architecture: the split, the loop, workers, state

Read when adding IO, a worker, a timer, persistence, config, a subcommand,
or anything that touches `src/run/`. Line refs are to the three source apps
under `~/dev`; open them when a pattern here is not enough.

## Contents

- [The split](#the-split)
- [The loop](#the-loop)
- [Workers](#workers)
- [Tokio inside a worker](#tokio-inside-a-worker)
- [Stale answers and cancellation](#stale-answers-and-cancellation)
- [Cache, session, config](#cache-session-config)
- [Handing the terminal away](#handing-the-terminal-away)
- [Growing past one screen](#growing-past-one-screen)

## The split

| Module | Owns | Never |
|---|---|---|
| `app/` | state, key and mouse handling, `Action`s out | IO, threads, the clock, the terminal |
| `ui/` | `render(&mut Frame, &App, &Theme) -> Hits` | mutating the app, IO, reading the clock |
| `run/` | terminal, worker handles, `Instant::now()`, executing `Action`s | business logic |
| `worker.rs` (or `db/`, `azure/`…) | every blocking call | touching app state |

- Side effects are data: `App::key`/`App::pointer` return an `Outcome
  { actions, repaint }`, and `Driver::dispatch` is the only place an
  `Action` becomes IO. This is what makes every screen testable without fakes.
- Every `Instant` enters as a parameter (`apply(event, now)`,
  `settle(now)`, `pointer(.., now, ..)`). Tests pass made-up instants for
  double-clicks and expiry.
- The renderer does not know the app's scroll state ahead of time: it
  clamps the app's `top` hint with `ui::window`, then `App::drawn(&hits)`
  records the drawn window so `PageDown` knows a page (sql-bench
  `Results::window`, `App::drawn`).
- `main.rs` is under 15 lines: parse, call `run::main`, print `error:
  {error:#}`, exit nonzero. `lib.rs` is only `pub mod` lines, so tests and
  headless subcommands reuse everything.
- Split a file when it passes ~1,000 lines (az-tui rule). Tests mirror the
  tree (`ui/tests/<file>.rs` once `ui/tests.rs` grows).

## The loop

`Driver::turn` in the template is the house loop (sql-bench
`run/mod.rs:539`, ticket-tui `run/events.rs:38`):

1. Drain every worker with `try_recv`/`try_event`; `dirty |= app.apply(..)`.
2. Timers: `dirty |= app.settle(now)` (note expiry, spinner frames, debounced
   saves).
3. Paint only `if dirty`; store the returned `Hits`; call `app.drawn`.
4. Timeout = min of `app.wakeup(now)` and `IDLE` (250 ms). Worker answers do
   not wake the loop, so `IDLE` bounds their latency; while anything is in
   flight the spinner's 100 ms wakeup takes over.
5. Wait for one event, then drain the queue with `next(Duration::ZERO)`
   until empty or `DRAIN_LIMIT` (50 ms): a burst of keys is one frame.
6. A mouse event arriving while `dirty` is **held** until the next frame is
   painted, so a click behind a layout-changing key lands on the new layout.

Rules the tests hold the loop to: an idle app draws no frames; resting the
pointer costs at most one frame; a press paints nothing.

Terminal claim and release (template `run/mod.rs`):

- `ratatui::try_init()` (raw mode, alternate screen, panic hook), then a
  `Restore` drop guard, then `EnableMouseCapture, EnableBracketedPaste`.
- Release order is fixed: `DisableMouseCapture, DisableBracketedPaste`,
  *then* `ratatui::restore()`. Mouse capture left on after the alternate
  screen is gone floods the shell with escape codes.
- The panic hook restores only for the `main` thread; a worker's panic goes
  to the trace and surfaces as `Event::Stopped`, the UI keeps running.
- Handle `KeyEventKind::Press` only (Windows sends release and repeat).
- `Event::Resize` just marks dirty; `Terminal::draw` resizes the buffer.
- Slow startup work (connecting, first fetch) is requested *after* the first
  frame is on screen — nobody should watch a blank terminal.
- Signals: sql-bench catches SIGTERM/SIGHUP on a `signals` thread with a
  current-thread tokio runtime (`run/mod.rs:212`); add it when the app holds
  state worth saving on a kill.

## Workers

One handle shape everywhere (template `worker.rs`, ticket-tui
`sync.rs:1041`, az-tui `worker.rs:125`):

```rust
pub struct Worker { requests: Sender<Request>, events: Receiver<Event>, stopped: Cell<bool> }
pub fn spawn() -> io::Result<Self>              // named thread: thread::Builder::new().name(..)
pub fn send(&self, request: Request)            // ignores a closed channel
pub fn try_event(&self) -> Option<Event>        // Disconnected -> one Event::Stopped
```

- `std::thread` + `std::sync::mpsc` by default. No crossbeam, no async
  channels, no `Arc<Mutex<App>>`.
- Errors cross the thread as `Result<T, String>`, formatted at the source
  with `{error:#}` so the cause chain survives.
- Latest wins: after one blocking `recv`, drain with `try_iter()` and keep the
  newest (template `serve`); az-tui collapses a batch of `Refresh`es into one.
- Long walks pump the inbox between items so a detail request mid-refresh
  waits one round trip, not the whole walk (az-tui `worker.rs:253`).
- Stream big results in batches (sql-bench: `Columns`, then `Rows` of 500,
  then exactly one `Done` or `Error`), and drain every batch before one paint.
- Periodic reads use a `Cadence { base, current, due }` that doubles on
  failure up to a cap and a `recv_timeout(until_due)` loop (az-tui
  `kube.rs:1166`, ticket-tui `watch.rs:658`).
- Fan-out: `thread::scope` plus an `AtomicUsize` work index, about 30 lines
  (az-tui `parallel.rs:16`). No rayon.
- Subprocesses: own process group (`process_group(0)`), both pipes drained
  on their own threads, `try_wait` polled, killed at a cap (az-tui
  `kube.rs:839`).
- Dropping a handle never joins a busy worker on the UI thread: quitting must
  not wait on a 30 s timeout. Join from a helper thread with a grace period
  if a child must be killed (az-tui `kube.rs` `Drop`).

## Tokio inside a worker

Default: none. Add tokio only when a driver is async-only (tiberius,
reqwest-only APIs, many concurrent sockets). The runtime lives inside the
worker thread; the UI thread never sees a future. Features: `rt`, `time`,
`macros` (for `select!`), plus `net`/`signal` if used. Verified pattern:

```rust
thread::Builder::new().name("db".into()).spawn(move || {
    let runtime = match tokio::runtime::Builder::new_current_thread().enable_all().build() {
        Ok(runtime) => runtime,
        Err(error) => {
            let _ = outbox.send(Event::Failed(format!("could not start tokio: {error}")));
            return;
        }
    };
    while let Ok(request) = inbox.recv() {
        let event = runtime.block_on(async {
            tokio::select! {
                event = serve(request, &outbox) => event,     // streams batches through outbox
                () = cancelled(&flag) => Event::Cancelled,
            }
        });
        if outbox.send(event).is_err() {
            return;
        }
    }
})?;

async fn cancelled(flag: &AtomicBool) {
    while !flag.load(Ordering::Relaxed) {
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
}
```

The handle clears the flag in `query()` before sending, so ordering is
guaranteed (sql-bench `db/mod.rs:36-160`). A full async event loop
(`EventStream` + `select!` on the UI thread) is not the house style: it
makes replay nondeterministic and the app impure.

## Stale answers and cancellation

Pick the lightest guard that works:

| Situation | Guard |
|---|---|
| Answer is about a thing (dir, vault, row) | Echo the key in the event; drop it if the app moved on (template `apply`, az-tui `on_value`) |
| One job at a time | `Option<Receiver<..>>` per request; replacing or dropping it is the cancel (sql-bench `pending`) |
| Rapid re-queries (search as you type) | `generation: u64` bumped per submit; the worker keeps the newest; the app drops `generation != current` (ticket-tui `search.rs`) |
| Work in progress must stop | `Arc<AtomicBool>` polled by the worker; the worker is busy and will not read a message (sql-bench `CANCEL_POLL_MS`) |

After a refresh, restore the cursor by identity (name, id), never by
index (az-tui `ListState::keep_cursor`).

## Cache, session, config

- **Paths.** Config: `$XDG_CONFIG_HOME/<app>/config.toml`, else
  `~/.config/<app>/config.toml`, macOS too. Data (cache, session): `$XDG_DATA_HOME/<app>`,
  else `~/.local/share/<app>` (macOS: `~/Library/Application Support/<app>`).
  Hand-roll this in `config.rs`; no `dirs` crate. Pass the environment as a
  closure so tests can supply their own.
- **Precedence.** Flag, then `<APP>_*` env var, then the file, then the
  default; `NO_COLOR` beats all theme choices. A file named by `--config`
  must exist; the default one missing is a first run.
- **Parsing.** `#[serde(default)]` on every section, unknown keys ignored,
  errors keep toml's line and name the path. Read the config *after*
  `Cli::parse()` so `--help`/`--version` always work. Ship a
  `config.example.toml` with every key commented out, under `# ── Section ──`
  rules.
- **Live reload** (ticket-tui `ConfigWatch`): stat the file's mtime once a
  second in the loop; a broken file mid-run is a footer error, at startup it
  is fatal.
- **Cache: stale-while-revalidate** (az-tui `cache.rs`). A versioned
  snapshot is read *before* the terminal is claimed, the first frame paints
  from it, and the refresh runs behind. A version mismatch or parse failure
  is `None`, silently. A failed source keeps its old rows marked stale
  (muted, with the error in the status bar). Write at most every 30 s on a
  spawned thread, one write in flight, joined on quit.
- **Writes are atomic.** `tempfile::NamedTempFile::new_in(dir)`, write,
  flush, `chmod 0600` for anything sensitive, `persist`.
- **Session** (layout only: tab, sort, columns, split, never the query or
  secrets): debounced with a settle timer (300 ms quiet, or 1 s of continuous
  motion; ticket-tui `Settle`). Unknown keys are kept and skipped.
- **Secrets**: a newtype whose `Debug`/`Display` print `[redacted]` and that
  has no `Serialize` (az-tui `Secret`).

## Handing the terminal away

For `$EDITOR`, `kubectl exec -it` and the like (ticket-tui `run/editor.rs`,
az-tui `run.rs:411`): `release()`, run the child, re-claim (`enable_raw_mode`,
`EnterAlternateScreen`, mouse and paste on), then `terminal.clear()` and
mark dirty. Return a flag from the action so the loop knows to repaint
everything.

## Growing past one screen

- **Tabs**: `App { shell: Shell, tabs: Vec<Tab> }` or one field per screen.
  `Shell` holds what no screen owns: focus, notification, mouse, split,
  help. Screens are an enum and a `match` (az-tui `Screen`); a trait is
  justified only when the screens are many and share the mouse pipeline as
  default methods (ticket-tui `trait Screen`, `app/screen.rs:88`).
- **Modes over flags** once there are more than two (`Browse`, `Search`,
  `Palette`, `Edit`): `match self.mode` first in key routing, `Ctrl-C` before
  it (ticket-tui `work_items/mod.rs:613`).
- **Headless subcommands**: every feature reachable without the TUI
  (`show ID --json`, `list --query`, `doctor`). `Option<Command>` in clap; no
  subcommand opens the TUI. Shared formatting code, so a file is the same
  bytes whichever door it left by (sql-bench `export.rs`).
- **`doctor`**: one aligned line per check, `ok (412 ms)` or a fix hint, exit
  0/1 (az-tui `doctor.rs`). **`setup --write`**: `create_new`, never
  overwrite; print the block if the file exists.
