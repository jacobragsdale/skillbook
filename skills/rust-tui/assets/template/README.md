# tui-template

A fast, mouse-first terminal app.

```sh
cargo run -- [DIR]
```

Everything a key does, something on screen does too: click a row to select
it, double-click a directory to open it, click a header to sort, drag the
seam between panes or the scrollbar thumb, and wheel over whatever you want
to scroll.

## Keys

| Key | Does |
|---|---|
| `q` | quit |
| `?` | help |
| `/` | filter |
| `Enter` | open directory |
| `Backspace` | parent directory |
| `j` | down (also ↓) |
| `k` | up (also ↑) |
| `PageDown` | page down |
| `PageUp` | page up |
| `g` | first (also Home) |
| `G` | last (also End) |
| `Tab` | switch pane |
| `s` | sort by the next column |
| `S` | reverse the sort |
| `r` | reload |
| `Esc` | close, clear the filter |
| `Ctrl-C` | quit, even while typing |

## Configuration

`$XDG_CONFIG_HOME/tui-template/config.toml` (default `~/.config/...`) is
optional. See `config.example.toml`.

A flag beats an environment variable, which beats the file:
`--theme` / `TUI_TEMPLATE_THEME` / `[theme] preset` pick one of `terminal`,
`terminal-light`, `mono` and `custom`. `NO_COLOR` always means `mono`.

## Verifying

```sh
cargo run -- --replay scripts/smoke.keys src           # frames to stdout
TUI_TEMPLATE_TRACE=trace.tsv cargo run                  # frame timings
cargo test --release -- --ignored                       # timing budgets
```
