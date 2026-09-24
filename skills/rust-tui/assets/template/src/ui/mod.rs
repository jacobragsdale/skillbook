//! `&App` in, a frame and the `Hits` it drew out. No IO, no clock, and no
//! change to the app: the loop feeds the hits back through `App::drawn`.

#[cfg(test)]
mod tests;
pub mod theme;

use std::borrow::Cow;
use std::path::Component;
use std::time::SystemTime;

use ratatui::Frame;
use ratatui::buffer::Buffer;
use ratatui::layout::{Constraint, Flex, Layout, Position, Rect};
use ratatui::style::Style;
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, BorderType, Clear, Padding, Paragraph, Wrap};
use unicode_width::{UnicodeWidthChar, UnicodeWidthStr};

use crate::app::pointer::{Hits, Target, thumb};
use crate::app::{App, Column, Focus, KEYS, SPINNER, key_named};
pub use theme::Theme;

/// Below this the whole screen is one line saying so.
pub const MIN: (u16, u16) = (40, 10);
/// From this width the list and details sit side by side; below it `Tab` swaps.
pub const TWO_PANES: u16 = 80;
const GUTTER: u16 = 2;
const SPACING: u16 = 2;
const NAME: &str = env!("CARGO_PKG_NAME");

pub fn render(frame: &mut Frame, app: &App, theme: &Theme) -> Hits {
    let area = frame.area();
    let mut hits = Hits::default();
    if area.width < MIN.0 || area.height < MIN.1 {
        let [middle] = Layout::vertical([Constraint::Length(1)])
            .flex(Flex::Center)
            .areas(area);
        let text = format!("{NAME} needs {}x{}", MIN.0, MIN.1);
        frame.render_widget(Paragraph::new(text).style(theme.muted).centered(), middle);
        return hits;
    }
    let [top, body, footer] = Layout::vertical([
        Constraint::Length(1),
        Constraint::Min(1),
        Constraint::Length(1),
    ])
    .areas(area);
    title_bar(frame.buffer_mut(), app, theme, top, &mut hits);
    if body.width >= TWO_PANES {
        let [left, right] = app.split.areas(body);
        list(frame, app, theme, left, &mut hits);
        details(frame, app, theme, right, &mut hits);
        hits.push(Rect { width: 1, ..right }, Target::Seam { body });
    } else if app.focus == Focus::List {
        list(frame, app, theme, body, &mut hits);
    } else {
        details(frame, app, theme, body, &mut hits);
    }
    status_bar(frame.buffer_mut(), app, theme, footer, &mut hits);
    if let Some(top) = app.help {
        help(frame, theme, area, top, &mut hits);
    }
    hover(frame.buffer_mut(), app, theme, &hits);
    hits
}

/// A rounded pane; focus is the accent border and title, and nothing else.
fn pane(title: &str, focused: bool, theme: &Theme) -> Block<'static> {
    let (border, title_style) = if focused {
        (theme.border_focused, theme.accent)
    } else {
        (theme.border, theme.muted)
    };
    Block::bordered()
        .border_type(BorderType::Rounded)
        .border_style(border)
        .padding(Padding::horizontal(1))
        .title(Span::styled(format!(" {title} "), title_style))
}

/// Buttons right-aligned over a pane's top border, dropped from the left
/// when the title needs the room.
fn chips(
    buf: &mut Buffer,
    area: Rect,
    chips: &[(&str, &str)],
    title: u16,
    theme: &Theme,
    hits: &mut Hits,
) {
    let mut x = area.right().saturating_sub(2);
    for (label, name) in chips.iter().rev() {
        let text = format!(" {label} ");
        let width = width_of(&text);
        if x < area.x + 2 + title + width {
            break;
        }
        x -= width;
        buf.set_string(x, area.y, &text, theme.muted);
        if let Some(key) = key_named(name) {
            hits.push(Rect::new(x, area.y, width, 1), Target::Button(key));
        }
    }
}

fn title_bar(buf: &mut Buffer, app: &App, theme: &Theme, area: Rect, hits: &mut Hits) {
    let name = format!(" {NAME} ");
    buf.set_string(area.x, area.y, &name, theme.accent);
    let help = " ? Help ";
    let help_rect = Rect {
        x: area.right().saturating_sub(width_of(help)),
        width: width_of(help),
        ..area
    };
    buf.set_string(help_rect.x, area.y, help, theme.muted);
    if let Some(key) = key_named("?") {
        hits.push(help_rect, Target::Button(key));
    }

    // The path, each directory clickable; the deepest part wins the room.
    let start = area.x + width_of(&name) + 1;
    let end = help_rect.x.saturating_sub(1);
    let parts: Vec<(String, bool)> = app
        .dir
        .components()
        .map(|part| {
            (
                part.as_os_str().to_string_lossy().into_owned(),
                matches!(part, Component::RootDir),
            )
        })
        .collect();
    let joined = |from: usize| -> u16 {
        let text: u16 = parts[from..]
            .iter()
            .map(|(part, root)| width_of(part) + u16::from(!root))
            .sum();
        text + if from > 0 { 2 } else { 0 }
    };
    let mut first = 0;
    while first + 1 < parts.len() && start + joined(first) > end {
        first += 1;
    }
    let mut x = start;
    if first > 0 {
        buf.set_string(x, area.y, "…/", theme.muted);
        x += 2;
    }
    for (depth, (part, root)) in parts.iter().enumerate().skip(first) {
        let last = depth + 1 == parts.len();
        let width = width_of(part);
        if x + width > end {
            break;
        }
        buf.set_string(x, area.y, part, if last { theme.text } else { theme.muted });
        hits.push(Rect::new(x, area.y, width, 1), Target::Crumb(depth + 1));
        x += width;
        if !last && !root {
            buf.set_string(x, area.y, "/", theme.muted);
            x += 1;
        }
    }
}

fn list(frame: &mut Frame, app: &App, theme: &Theme, area: Rect, hits: &mut Hits) {
    let focused = app.focus == Focus::List;
    let arrow = if app.sort.desc { "▼" } else { "▲" };
    let position = if app.visible.is_empty() {
        0
    } else {
        app.list.cursor + 1
    };
    let count = format!(
        " {position}/{} · {} {arrow} ",
        app.visible.len(),
        app.sort.column.title()
    );
    let block = pane("Files", focused, theme)
        .title_bottom(Line::styled(count, theme.muted).right_aligned());
    let inner = block.inner(area);
    frame.render_widget(block, area);
    hits.push(area, Target::Pane(Focus::List));
    chips(
        frame.buffer_mut(),
        area,
        &[("⟳ Reload", "r")],
        width_of(" Files "),
        theme,
        hits,
    );

    let [filter_row, header_row, rows] = Layout::vertical([
        Constraint::Length(1),
        Constraint::Length(1),
        Constraint::Min(0),
    ])
    .areas(inner);
    filter(frame, app, theme, filter_row, hits);
    let columns = columns(header_row);
    let buf = frame.buffer_mut();
    for (column, rect) in Column::ALL.into_iter().zip(columns) {
        let mark = if app.sort.column == column { arrow } else { "" };
        cell(
            buf,
            rect,
            &format!("{} {mark}", column.title()),
            theme.header,
            column != Column::Name,
        );
        hits.push(rect, Target::Header(column));
    }

    let viewport = usize::from(rows.height);
    let top = window(app.list.cursor, app.list.top, viewport, app.visible.len());
    hits.push(rows, Target::Rows { top });
    if let Some((text, style)) = empty_state(app, theme) {
        cell(buf, Rect { height: 1, ..rows }, &text, style, false);
    }
    // Only the visible window is formatted, whatever the row count.
    for (y, &index) in (rows.y..rows.bottom()).zip(app.visible.iter().skip(top)) {
        let entry = &app.entries[index];
        let cursor = app.list.cursor == top + usize::from(y - rows.y);
        let weak = if cursor { theme.text } else { theme.muted };
        let [name, size, modified] = columns.map(|rect| Rect { y, ..rect });
        let label = if entry.dir {
            Cow::Owned(format!("{}/", entry.name))
        } else {
            Cow::Borrowed(entry.name.as_str())
        };
        cell(buf, name, &label, theme.text, false);
        let bytes = if entry.dir {
            "—".to_owned()
        } else {
            human_size(entry.size)
        };
        cell(buf, size, &bytes, weak, true);
        cell(
            buf,
            modified,
            &age(app.listed_at, entry.modified),
            weak,
            true,
        );
        if cursor {
            buf.set_string(rows.x, y, "›", theme.accent);
            buf.set_style(
                Rect {
                    y,
                    height: 1,
                    ..rows
                },
                theme.selected,
            );
        }
    }
    scrollbar(
        buf,
        area,
        rows,
        top,
        app.visible.len(),
        if focused {
            theme.border_focused
        } else {
            theme.border
        },
        hits,
    );
}

fn empty_state(app: &App, theme: &Theme) -> Option<(String, Style)> {
    if !app.visible.is_empty() {
        return None;
    }
    Some(if let Some(error) = &app.error {
        (format!("✗ {error}"), theme.error)
    } else if app.loading {
        (format!("{} reading…", SPINNER[app.spinner]), theme.muted)
    } else if app.entries.is_empty() {
        ("empty directory".to_owned(), theme.muted)
    } else {
        (
            "nothing matches · Esc clears the filter".to_owned(),
            theme.muted,
        )
    })
}

fn filter(frame: &mut Frame, app: &App, theme: &Theme, area: Rect, hits: &mut Hits) {
    hits.push(area, Target::Filter);
    let (glyph, glyph_style) = if app.filtering {
        ("› ", theme.accent)
    } else {
        ("/ ", theme.muted)
    };
    let text = if app.filter.is_empty() && !app.filtering {
        Span::styled("filter", theme.muted)
    } else {
        Span::styled(app.filter.as_str(), theme.text)
    };
    let clear = if app.filter.is_empty() { 0 } else { 3 };
    // ponytail: a filter wider than the pane shows its start; scroll it by
    // whole characters (az-tui's field_window) if long filters matter.
    let line = Line::from(vec![Span::styled(glyph, glyph_style), text]);
    frame
        .buffer_mut()
        .set_line(area.x, area.y, &line, area.width.saturating_sub(clear));
    if app.filtering {
        let caret =
            (area.x + GUTTER + width_of(&app.filter)).min(area.right().saturating_sub(clear + 1));
        frame.set_cursor_position(Position::new(caret, area.y));
    }
    if clear > 0 {
        let rect = Rect {
            x: area.right() - clear,
            width: clear,
            ..area
        };
        frame
            .buffer_mut()
            .set_string(rect.x, rect.y, " × ", theme.muted);
        if let Some(key) = key_named("Esc") {
            hits.push(rect, Target::Button(key));
        }
    }
}

/// Name, Size, Modified, after the cursor gutter. Header and rows share it,
/// so a header click lands on the column it names.
fn columns(area: Rect) -> [Rect; 3] {
    let cells = Rect {
        x: area.x + GUTTER,
        width: area.width.saturating_sub(GUTTER),
        ..area
    };
    Layout::horizontal([
        Constraint::Fill(1),
        Constraint::Length(7),
        Constraint::Length(10),
    ])
    .spacing(SPACING)
    .areas(cells)
}

/// The first row to draw so the cursor is on screen, starting from the hint.
#[must_use]
pub fn window(cursor: usize, hint: usize, viewport: usize, len: usize) -> usize {
    if viewport == 0 {
        return 0;
    }
    let top = hint.min(len.saturating_sub(viewport));
    if cursor < top {
        cursor
    } else if cursor >= top + viewport {
        cursor + 1 - viewport
    } else {
        top
    }
}

/// A thumb over the pane's right border. The track above and below it is
/// PageUp and PageDown, so it is buttons like everything else.
fn scrollbar(
    buf: &mut Buffer,
    pane: Rect,
    rows: Rect,
    top: usize,
    content: usize,
    style: Style,
    hits: &mut Hits,
) {
    let viewport = usize::from(rows.height);
    if content <= viewport {
        return;
    }
    let track = Rect {
        x: pane.right() - 1,
        width: 1,
        ..rows
    };
    let range = thumb(top, content, viewport, track.height);
    for y in range.clone() {
        buf.set_string(track.x, track.y + y, "┃", style);
    }
    let len = range.end - range.start;
    let above = Rect {
        height: range.start,
        ..track
    };
    let on = Rect {
        y: track.y + range.start,
        height: len,
        ..track
    };
    let below = Rect {
        y: track.y + range.end,
        height: track.height - range.end,
        ..track
    };
    for (rect, name) in [(above, "PageUp"), (below, "PageDown")] {
        if let Some(key) = key_named(name) {
            hits.push(rect, Target::Button(key));
        }
    }
    hits.push(
        on,
        Target::Thumb {
            content,
            viewport,
            track,
        },
    );
}

fn details(frame: &mut Frame, app: &App, theme: &Theme, area: Rect, hits: &mut Hits) {
    let block = pane("Details", app.focus == Focus::Details, theme);
    let inner = block.inner(area);
    frame.render_widget(block, area);
    hits.push(area, Target::Pane(Focus::Details));
    let Some(entry) = app.selected() else {
        frame
            .buffer_mut()
            .set_string(inner.x, inner.y, "nothing selected", theme.muted);
        return;
    };
    let field = |label: &str, value: String| {
        Line::from(vec![
            Span::styled(format!("{label:<10}"), theme.muted),
            Span::styled(value, theme.text),
        ])
    };
    let lines = vec![
        Line::styled(entry.name.clone(), theme.accent),
        Line::default(),
        field(
            "kind",
            if entry.dir { "directory" } else { "file" }.to_owned(),
        ),
        field("size", human_size(entry.size)),
        field("modified", age(app.listed_at, entry.modified)),
        field("path", app.dir.join(&entry.name).display().to_string()),
    ];
    frame.render_widget(Paragraph::new(lines).wrap(Wrap { trim: false }), inner);
}

/// Hints on the left, state on the right; a note replaces the hints.
fn status_bar(buf: &mut Buffer, app: &App, theme: &Theme, area: Rect, hits: &mut Hits) {
    let state = if app.loading {
        format!("{} reading ", SPINNER[app.spinner])
    } else if app.filter.is_empty() {
        format!("● {} entries ", app.entries.len())
    } else {
        format!("● {} of {} ", app.visible.len(), app.entries.len())
    };
    let state_x = area.right().saturating_sub(width_of(&state));
    buf.set_string(state_x, area.y, &state, theme.muted);
    let end = state_x.saturating_sub(1);
    if let Some(note) = &app.note {
        let (glyph, style) = if note.error {
            ("✗", theme.error)
        } else {
            ("✓", theme.ok)
        };
        let text = format!(" {glyph} {}", note.text);
        buf.set_string(area.x, area.y, fit(&text, end - area.x), style);
        return;
    }
    let mut x = area.x + 1;
    for key in KEYS.iter().filter(|key| key.hint && app.acts(key.name)) {
        let width = width_of(key.name) + 1 + width_of(key.does);
        if x + width > end {
            break;
        }
        buf.set_string(x, area.y, key.name, theme.accent);
        buf.set_string(x + width_of(key.name) + 1, area.y, key.does, theme.muted);
        if let Some(event) = key_named(key.name) {
            hits.push(Rect::new(x, area.y, width, 1), Target::Button(event));
        }
        x += width + 2;
    }
}

/// Dims what is behind, and a click outside closes it and reaches nothing.
fn help(frame: &mut Frame, theme: &Theme, area: Rect, top: usize, hits: &mut Hits) {
    hits.push(area, Target::Outside);
    frame.buffer_mut().set_style(area, theme.muted);
    let rows = u16::try_from(KEYS.len()).unwrap_or(u16::MAX);
    let [rect] = Layout::horizontal([Constraint::Length(52.min(area.width - 4))])
        .flex(Flex::Center)
        .areas(area);
    let [rect] = Layout::vertical([Constraint::Length((rows + 2).min(area.height - 2))])
        .flex(Flex::Center)
        .areas(rect);
    frame.render_widget(Clear, rect);
    let block = Block::bordered()
        .border_type(BorderType::Rounded)
        .border_style(theme.border_focused)
        .padding(Padding::horizontal(1))
        .title(Span::styled(" Help ", theme.accent))
        .title_bottom(Line::styled(" Esc closes ", theme.muted).right_aligned());
    let inner = block.inner(rect);
    frame.render_widget(block, rect);
    hits.push(rect, Target::Overlay);
    let buf = frame.buffer_mut();
    for (y, key) in (inner.y..inner.bottom()).zip(KEYS.iter().skip(top)) {
        buf.set_string(inner.x, y, key.name, theme.accent);
        let does = Rect {
            x: inner.x + 11,
            width: inner.width.saturating_sub(11),
            y,
            height: 1,
        };
        cell(buf, does, key.does, theme.text, false);
        if let Some(event) = key_named(key.name) {
            hits.push(
                Rect {
                    height: 1,
                    y,
                    ..inner
                },
                Target::HelpRow(event),
            );
        }
    }
}

/// Restyled after the frame is finished, from the same hits a click reads.
fn hover(buf: &mut Buffer, app: &App, theme: &Theme, hits: &Hits) {
    if let Some(at) = app.mouse.pointer
        && let Some((rect, target)) = hits.at(at)
        && target.hovers()
    {
        buf.set_style(rect, theme.hover);
    }
}

fn cell(buf: &mut Buffer, rect: Rect, text: &str, style: Style, right: bool) {
    let text = fit(text, rect.width);
    let x = if right {
        rect.right().saturating_sub(width_of(&text))
    } else {
        rect.x
    };
    buf.set_string(x, rect.y, text, style);
}

/// Cut to `width` terminal cells with `…`. Width is cells, never chars.
#[must_use]
pub fn fit(text: &str, width: u16) -> Cow<'_, str> {
    let width = usize::from(width);
    if text.width() <= width {
        return Cow::Borrowed(text);
    }
    if width == 0 {
        return Cow::Borrowed("");
    }
    let mut out = String::new();
    let mut used = 0;
    for c in text.chars() {
        let w = c.width().unwrap_or(0);
        if used + w + 1 > width {
            break;
        }
        used += w;
        out.push(c);
    }
    out.push('…');
    Cow::Owned(out)
}

fn width_of(text: &str) -> u16 {
    u16::try_from(text.width()).unwrap_or(u16::MAX)
}

fn human_size(bytes: u64) -> String {
    const UNITS: [&str; 5] = ["B", "K", "M", "G", "T"];
    let mut value = bytes as f64;
    let mut unit = 0;
    while value >= 1024.0 && unit < UNITS.len() - 1 {
        value /= 1024.0;
        unit += 1;
    }
    match unit {
        0 => format!("{bytes} B"),
        _ if value < 10.0 => format!("{value:.1} {}", UNITS[unit]),
        _ => format!("{value:.0} {}", UNITS[unit]),
    }
}

fn age(now: Option<SystemTime>, then: Option<SystemTime>) -> String {
    let (Some(now), Some(then)) = (now, then) else {
        return "—".to_owned();
    };
    let secs = now
        .duration_since(then)
        .map_or(0, |elapsed| elapsed.as_secs());
    match secs {
        0..60 => "now".to_owned(),
        60..3_600 => format!("{}m ago", secs / 60),
        3_600..86_400 => format!("{}h ago", secs / 3_600),
        86_400..31_536_000 => format!("{}d ago", secs / 86_400),
        _ => format!("{}y ago", secs / 31_536_000),
    }
}

/// The buffer as text, rows right-trimmed: what tests and replay frames assert.
#[must_use]
pub fn screen_text(buffer: &Buffer) -> String {
    let area = buffer.area;
    (area.top()..area.bottom())
        .map(|y| {
            let row: String = (area.left()..area.right())
                .map(|x| buffer[(x, y)].symbol())
                .collect();
            row.trim_end().to_owned()
        })
        .collect::<Vec<_>>()
        .join("\n")
}
