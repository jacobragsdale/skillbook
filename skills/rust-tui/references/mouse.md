# Mouse-first: hits, clicks, drags, the wheel

Read when adding anything clickable, scrollable or draggable, an overlay,
a menu, or text selection. The template's `src/app/pointer.rs` is the
working baseline; sql-bench `app/pointer.rs` and ticket-tui `src/pointer.rs`
are the full versions.

## Contents

- [The contract](#the-contract)
- [Hits](#hits)
- [Targets](#targets)
- [Press, release, double-click](#press-release-double-click)
- [Drag](#drag)
- [Wheel](#wheel)
- [Scrollbar](#scrollbar)
- [Hover](#hover)
- [Overlays and menus](#overlays-and-menus)
- [Text: carets and selection](#text-carets-and-selection)
- [Tests that hold it together](#tests-that-hold-it-together)

## The contract

- Everything a key does, something on screen does too, and every clickable
  thing is a key: `Target::Button(KeyEvent)` calls `App::key(key)`. A button
  can do nothing a key cannot, and is drawn only where its key acts
  (`App::acts(name)`).
- Focus follows the click. A click never scrolls the view.
- Clicks fire on **release**, on the spot that was pressed, if the pointer
  never slid off.
- The wheel scrolls what is under the pointer and never moves the focus.
- A click lands on the frame the user saw (the loop holds a click that
  arrives behind an unpainted change).

## Hits

The renderer returns `Hits(Vec<(Rect, Target)>)` in paint order; the loop
keeps the last frame's and passes it to `App::pointer`. The topmost region
is the last pushed (`iter().rev().find(contains)`). No layers are needed:
an overlay pushes a full-frame `Outside` first, so it covers everything
drawn before it.

- `Hits::push` skips empty rects, so zero-width columns never swallow clicks.
- `Spot { target, row }` is the target plus the row within its rect: two
  rows of one list are two spots, which is what double-click compares.
- ticket-tui instead stores regions on the shell with a `PointerLayer {
  Base, Modal, Popup }` and resolves `max_by_key((layer, index))`. Move to
  that only when popups open over modals.

## Targets

One flat `enum Target`, `Copy`, holding **indexes and the window they were
drawn from, never references**: `Rows { top }`, `Cells { column, top, left
}`, `Tab(usize)`, `Header(Column)`, `Thumb { content, viewport, track }`,
`Seam { body }`. A click resolves against the drawn window, so the view never
jumps under the pointer.

Add a variant per new kind of clickable; add it to `Target::hovers()` only
if it acts on a single click.

## Press, release, double-click

```rust
Down(Left)  => press = spot.map(|spot| Press { spot, left: false, grab })
Drag(Left)  => thumb/seam: move it; else if spot != press.spot { press.left = true }
Up(Left)    => if !press.left && spot == Some(press.spot) { click(press.spot, now) }
```

- Double-click is the same `Spot` within `DOUBLE_CLICK` (400 ms). It consumes
  both clicks, so a third click is a single again.
- Double-click on a row = `Enter`. On a seam = reset the split.
- Right-click (sql-bench only): select what is under the pointer, then open a
  context menu at the pointer whose entries are key names, labels read
  from `KEYS`; picking an entry is exactly that key. ticket-tui leaves
  right-click unused. Add it only with a menu that earns it.

## Drag

Drag does something on exactly three kinds of target and nothing elsewhere:

- **Thumb**: store where it was grabbed (`grab = spot.row`) so the thumb
  does not jump; new top = `offset(y - track.y - grab, ..)`.
- **Seam**: `Split` in percent, so a terminal resize keeps proportions;
  `Split::areas` enforces minimums at every size (`NARROWEST`), not only
  after a drag. A double-click resets. ticket-tui shares one border column
  between panes (`Layout::spacing(Spacing::Overlap(1))`) and makes that
  column the seam; the template uses the right pane's left border.
- **Text selection** (see below).

Everything else: a drag cancels the click (`press.left = true`).

## Wheel

- ±3 rows (`WHEEL`) on the scroll surface under the pointer.
- The cursor is dragged along only as far as needed to stay on screen, so
  what a key acts on is always visible (`App::wheel`).
- Shift+wheel or a horizontal wheel moves one column in grids (sql-bench).

## Scrollbar

Custom, not ratatui's `Scrollbar` (its thumb math does not match a drag):

```rust
pub fn thumb(offset: usize, content: usize, viewport: usize, track: u16) -> Range<u16>;
pub fn offset(start: u16, content: usize, viewport: usize, track: u16) -> usize; // the inverse
```

The painter and the drag both call these, so what is drawn is what is hit;
a unit test round-trips every offset. The thumb is `┃` over the pane's
right border in the border style; the track keeps the border glyph. The
track above and below the thumb are `Button(PageUp)` / `Button(PageDown)`.

## Hover

- Only what acts on a single click lights up: buttons, headers, tabs,
  crumbs, thumb, seam, menu items. Panes and plain rows do not.
- Painted after the frame is finished, as a `buf.set_style(rect,
  theme.hover)` pass over the same hits a click reads.
- `Moved` repaints only when the hovered `(Rect, Target)` changed: resting or
  sliding within one button costs no frames.
- ticket-tui tints hovered rows with `hover_background` so coloured cells
  keep their foreground, and sets the OSC 22 pointer shape (`Link` over
  links, `ColResize` over seams), written only when the shape changes
  (`run/pointer.rs`). Both are optional polish.

## Overlays and menus

- Push `Outside` over the whole frame, dim it (`set_style(area,
  theme.muted)`), `Clear` the box, push `Overlay` over the box, then its
  buttons. A click beside the overlay closes it and reaches nothing
  underneath. A click inside on nothing is swallowed.
- Help rows are `HelpRow(key)`: close help, then press the key.
- Drop-downs anchor under the rect of what opened them (`Hits` lookup by
  target), opening right-and-down and flipping at the edges (sql-bench
  `open_from`, ticket-tui `OverlayAnchor::{Centered, Below, Above}`).
- An open overlay takes the pointer first, then an open menu, then the base
  (az-tui `handle_mouse` order).

## Text: carets and selection

- Caret placement (ticket-tui `TextInput::click(column, width)`): map the
  clicked column through the same `field_window(text, cursor, width) ->
  (first_char, caret_col)` the renderer used, scrolling by whole characters
  so a wide glyph is never cut (az-tui `text_input.rs:247`).
- Selection (ticket-tui `capture_selectable`): the renderer snapshots the
  symbols of a selectable surface; a drag becomes a `TextSelection`; release
  returns `Action::Copy(text)`. Paint the selection `REVERSED`.
- Copy goes out via OSC 52 (hand-rolled base64, no crate) plus a clipboard
  tool if present (`wl-copy`, `xclip`, `pbcopy`).

## Tests that hold it together

Put these in every app (template `ui/tests.rs`):

- `every_button_drawn_is_exactly_its_key_and_does_something`: across several
  states and sizes, click every reachable `Button`, press its key on a
  clone, assert the apps are equal (after resetting `mouse`), the actions
  are equal, and something changed. Assert a minimum count so the test
  cannot pass vacuously.
- A press that slides off is not a click; a click outside an overlay
  reaches nothing; the wheel leaves the focus; thumb drag and track paging;
  seam drag and double-click reset; hover repaints only on change.
- Loop level (`run/tests.rs`): an idle app draws no more frames; a click
  queued behind a layout-changing key lands on the new layout.
- sql-bench `ui/tests/mouse.rs` adds: every context-menu entry is exactly
  its key; the pointer resting on one cell costs one frame and a press costs
  none; `scripts/qa/mouse-bytes.sh` feeds raw SGR `\e[<0;x;yM` into a pty and
  asserts `\e[?1000l` precedes `\e[?1049l`.
