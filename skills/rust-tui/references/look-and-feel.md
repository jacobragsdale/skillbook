# Look and feel: tokens, layout, chrome, states

Read when drawing a new pane, overlay, table, status, or when touching
colour. ticket-tui `LOOK_AND_FEEL_PLAN.md` is the long-form source.

## Contents

- [Principles](#principles)
- [Theme tokens and presets](#theme-tokens-and-presets)
- [Joining the shared palette](#joining-the-shared-palette)
- [Frame layout](#frame-layout)
- [Panes and focus](#panes-and-focus)
- [Tables](#tables)
- [Details panes](#details-panes)
- [Status bar and tab bar](#status-bar-and-tab-bar)
- [Empty, loading, error](#empty-loading-error)
- [Overlays](#overlays)
- [Glyphs and motion](#glyphs-and-motion)
- [Do not](#do-not)

## Principles

- Colour carries meaning only (focus, state, matches, errors). Everything
  else is `text` or `muted`. Colour reinforces a hierarchy already carried by
  weight, position and glyphs; it never carries meaning alone.
- Design in ANSI-16 first so the terminal's own palette shows through, over
  SSH too. The UI must read under `NO_COLOR`: shapes (`┃ ▲ ›`), bold and
  reverse video carry every distinction.
- One line per row. Separators are ` · `. Titles carry state.
- Progressive disclosure: 3–5 context hints in the footer, everything in
  `?` help.
- Width is terminal cells (`unicode-width`), never `char`s; truncate with `…`.

## Theme tokens and presets

`ui/theme.rs` is the only module that names a `Color`. Tokens are `Style`s
(`text, muted, accent, header, border, border_focused, selected, hover, ok,
error`); add domain tokens (`state_*`, `priority_*`, `tag_palette: [Color;
6]`) as the app needs them, never inline colours.

| Preset | Accent | Muted / border | Selected | Notes |
|---|---|---|---|---|
| `terminal` (default) | Cyan bold | DarkGray | bg DarkGray, bold | ANSI-16 only |
| `terminal-light` | Blue bold | DarkGray | bg `Indexed(253)` | |
| `mono` | bold | DIM | REVERSED + bold | `NO_COLOR`; hover UNDERLINED |
| `custom` | palette `accent` | palette `muted`/`overlay` | bg `overlay` | from `[theme.custom]` |

Selection order: `NO_COLOR` (non-empty) → `--theme` → `<APP>_THEME` → file
`[theme] preset` → `custom` if a palette exists → `terminal`. An unknown
name is a startup error that lists the valid ones.

Pass `&Theme` into `render` (template). az-tui and ticket-tui read a global
`theme()` from `OnceLock<RwLock<Theme>>` with a `thread_local!` under
`cfg(test)`; use that only if live theme reload needs it.

Muted text on the selected background can vanish (DarkGray on DarkGray):
draw the cursor row's weak cells in `text`, or swap to a `body` token
(ticket-tui `muted_on(ground)`).

## Joining the shared palette

Jacob's `theme` tool (`~/dev/theme`) writes one palette into every program.
Today only ticket-tui is a target. To make a new app follow it:

1. The app reads `[theme.custom]` in its own `config.toml` (the template's
   `config::Palette`: `surface, overlay, fg, subtle, muted, accent, red,
   green` required; `bg, bg_deep, blue, cyan, orange, teal, name,
   appearance` also written, ignored unless used).
2. In `~/dev/theme`, add a target next to `ticket-tui` in
   `src/targets/mod.rs` and a writer modelled on `tools::ticket_tui`
   (`src/targets/tools.rs:504`) that writes the table into
   `~/.config/<app>/config.toml` and sets `preset = "custom"`.
3. Optional live repaint: stat the config mtime once a second (ticket-tui
   `ConfigWatch`).

## Frame layout

```
 app-name  /path/to/crumbs                                  ? Help     row 0: title/tab bar
╭ Files ──────────────── ⟳ Reload ─╮╭ Details ──────────────────╮
│ / filter                          ││ name                      │   search row: no box
│   Name ▲          Size  Modified  ││                           │   header: bold muted
│ › d00/               —       now  ││ kind      directory       │   cursor: › + selected
│   f00              0 B    1h ago  ┃│ size      0 B             │   thumb over the border
╰────────────────── 1/3 · Name ▲ ───╯╰───────────────────────────╯   counts on bottom border
 q quit  / filter  Enter open directory             ● 3 entries      hints left, state right
```

- Vertical: `[Length(1) bar, Min(1) body, Length(1) footer]`.
- Breakpoints: side by side at ≥ 80–110 columns (template 80; az-tui and
  ticket-tui 110), stacked at 70–109 when both panes matter, one pane below
  that with `Tab` swapping.
- Below the minimum (template 40×10, az-tui 36×11, sql-bench 60×15) the
  whole screen is one centred muted line: `<app> needs 40x10`.

## Panes and focus

- `Block::bordered().border_type(Rounded).padding(Padding::horizontal(1))`,
  title `" Title "` padded with spaces.
- Focus is the accent border and accent title, nothing else. Unfocused:
  `border` and `muted` title.
- Titles carry state, joined by ` · `: `Results · 10,000 rows · 1,234 ms`,
  `Scratch [modified]`. Counts and sort go right-aligned on the bottom border
  (`title_bottom(..).right_aligned()`): ` 3/412 · Name ▲ `.
- Title-bar chips (` ⟳ Reload `, ` ▶ Run `, ` / Filter `) are buttons,
  right-aligned over the top border, dropped from the left when the title
  needs room.
- Adjacent panes may merge borders (`merge_borders(MergeStrategy::Fuzzy)`,
  az-tui/ticket-tui) or sit as two blocks (template, sql-bench).

## Tables

- Draw rows yourself into column rects from one
  `Layout::horizontal(widths).spacing(2)` shared by header and rows, so a
  header click lands on its column. ratatui's `Table` hides the rects.
- A 2-column cursor gutter is always reserved (`› ` in accent on the cursor
  row), as is the scrollbar column, so the table never shuffles sideways.
- One `Fill(1)` flexible column (name/title, floor ~24 cells); the rest
  fixed. Drop optional columns rightmost-first when the flexible one would
  fall under its floor (az-tui `TableLayout::visible_columns`).
- Numbers right-aligned; sort mark `▲ ▼` after the header text; header click
  sorts ascending, then descending.
- Search matches: `search_match` + bold + underlined.

## Details panes

- Title in accent (or bold `text`), a blank line, then `label  value`
  fields with the label padded (10–14 cells) in `muted`.
- Section rules: `── Versions ────────` in `header`.
- Middle-elide long URLs; wrap paths with `Paragraph::wrap(Wrap { trim:
  false })`. When scrolling or hit-testing wrapped text, count rendered
  rows with `Paragraph::line_count(width)` (feature
  `unstable-rendered-line-info`).
- Hashed chips for tags: FNV-1a of the key into `tag_palette`.

## Status bar and tab bar

- Footer left: hints as buttons (`key` in accent, `does` in muted, two
  spaces apart), only for keys that act now. A notification replaces them:
  `✓ saved` in `ok` for 4 s, `✗ message` in `error` for 8 s; `Esc` dismisses.
- Footer right: state, never truncated: `● 412 entries`, `⠋ reading`,
  `● synced 2m`, `! sync failed`, `◌ stale`, `⊘ offline`. When both do not
  fit, the state wins and hints drop at hint boundaries.
- Tab bar: ` 1 name ` labels, active in accent bold (REVERSED in mono),
  inactive muted, badges like `⚠ 3` in warning. Labels degrade full → short
  → digit so every tab stays clickable. `? Help` (and `Commands`) at the
  right end.

## Empty, loading, error

One line in the pane, most pressing reason first:

- error: `✗ permission denied` in `error`, in the source's own words;
- loading: `⠋ reading…` in `muted`;
- empty: `empty directory`, `nothing has run yet` in `muted`;
- filtered to nothing: `nothing matches · Esc clears the filter`, or a
  clickable accent placeholder `[ Clear filter ]` / `[ Retry ]` /
  `[ Connect ]` that is a `Button`;
- no config: a rounded block showing the config snippet to paste.

Runtime failures become status lines, never panics or exits. Only startup
errors (bad config, unknown theme) abort, with `error: {error:#}`.

## Overlays

`dim_behind` (muted over every cell outside), `Clear`, a rounded box with an
accent border, bold/accent title, ` Esc closes ` or a ` × ` close button on
the border. Help is ~52–56 columns, centred, never taller than the screen,
scrolls with the wheel and `j`/`k`. Buttons inside are filled pills:
` Save ` on `surface`, the primary in accent (REVERSED in mono), disabled
muted with no hit region.

## Glyphs and motion

`● ○ ◐ ✓ ✗ ⚠ ⊘ ◌ ▸ ▾ ▲ ▼ › … ┃ · ⟳ ▶ ■ ✎ ×`, fractional blocks
`▏▎▍▌▋▊▉█` for bars, a braille spinner `⠋⠙⠹⠸⠼⠴⠦⠧` at 100 ms. Nothing
animates while idle; the only other motion is a 220 ms row flash after an
edit lands (ticket-tui).

## Do not

- Nerd Font icons (font dependency), images/sixel, `tachyonfx`, gradients.
- Colour as the only signal; dark grey text meant as "faint" on themes where
  it equals the background (use DIM or `muted`).
- Boxes around single-line inputs; spinners that turn while idle; blank
  frames while connecting.
- Hand-drawn README screenshots: generate the frame with `--replay` (sql-bench
  `scripts/readme-frame.sh`).
