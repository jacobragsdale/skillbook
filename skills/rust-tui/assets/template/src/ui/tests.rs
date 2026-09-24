//! Rendered through `TestBackend` and asserted as text. Colours are asserted
//! through theme tokens, and the theme comes from the environment, so CI
//! runs this suite once per preset.

use std::path::PathBuf;
use std::time::{Duration, Instant, SystemTime};

use crossterm::event::{KeyCode, KeyEvent, KeyModifiers, MouseButton, MouseEvent, MouseEventKind};
use ratatui::Terminal;
use ratatui::backend::TestBackend;
use ratatui::layout::{Position, Rect};

use super::{Theme, render, screen_text};
use crate::app::pointer::{Hits, Mouse, Split, Target};
use crate::app::{Action, App, Focus, KEYS, Outcome};
use crate::config::ThemeConfig;
use crate::worker::{Entry, Event};

fn theme() -> Theme {
    Theme::select(None, &ThemeConfig::default(), |key| std::env::var(key).ok())
        .expect("a known theme")
}

const T0: Duration = Duration::from_secs(1_700_000_000);

/// `dirs` directories named d00.., then `files` files named f00..
fn app(dirs: usize, files: usize) -> App {
    let at = SystemTime::UNIX_EPOCH + T0;
    let entry = |name: String, dir: bool, i: u64| Entry {
        name,
        dir,
        size: i * 1024,
        modified: Some(at - Duration::from_secs(i * 3_600)),
    };
    let mut entries: Vec<Entry> = (0..dirs)
        .map(|i| entry(format!("d{i:02}"), true, i as u64))
        .collect();
    entries.extend((0..files).map(|i| entry(format!("f{i:02}"), false, i as u64)));
    let mut app = App::new(PathBuf::from("/demo/dir"));
    let _ = app.start();
    let dir = app.dir.clone();
    let result = Ok(entries);
    app.apply(Event::Listed { dir, at, result }, Instant::now());
    app
}

fn draw(app: &mut App, width: u16, height: u16) -> (Terminal<TestBackend>, Hits) {
    let mut terminal = Terminal::new(TestBackend::new(width, height)).unwrap();
    let mut hits = Hits::default();
    terminal
        .draw(|frame| hits = render(frame, app, &theme()))
        .unwrap();
    app.drawn(&hits);
    (terminal, hits)
}

fn line(terminal: &Terminal<TestBackend>, y: usize) -> String {
    screen_text(terminal.backend().buffer())
        .lines()
        .nth(y)
        .unwrap_or_default()
        .to_owned()
}

fn mouse(
    app: &mut App,
    hits: &Hits,
    kind: MouseEventKind,
    (x, y): (u16, u16),
    now: Instant,
) -> Outcome {
    let event = MouseEvent {
        kind,
        column: x,
        row: y,
        modifiers: KeyModifiers::NONE,
    };
    app.pointer(event, now, hits)
}

fn click(app: &mut App, hits: &Hits, at: (u16, u16), now: Instant) -> Outcome {
    let _ = mouse(app, hits, MouseEventKind::Down(MouseButton::Left), at, now);
    mouse(app, hits, MouseEventKind::Up(MouseButton::Left), at, now)
}

fn rect(hits: &Hits, pick: impl Fn(&Target) -> bool) -> Rect {
    hits.iter()
        .find(|(_, target)| pick(target))
        .map(|(rect, _)| *rect)
        .expect("the target was drawn")
}

fn press(app: &mut App, code: KeyCode) -> Outcome {
    app.key(KeyEvent::new(code, KeyModifiers::NONE))
}

#[test]
fn the_first_frame_shows_the_path_the_rows_and_the_hints() {
    let mut app = app(1, 2);
    let (terminal, _) = draw(&mut app, 80, 10);
    let title = line(&terminal, 0);
    let name = format!(" {}  /demo/dir ", env!("CARGO_PKG_NAME"));
    assert!(
        title.starts_with(&name) && title.ends_with(" ? Help"),
        "{title}"
    );
    let expected = [
        "╭ Files ──────────────────────── ⟳ Reload ─╮╭ Details ─────────────────────────╮",
        "│ / filter                                 ││ d00                              │",
        "│   Name ▲               Size    Modified  ││                                  │",
        "│ › d00/                     —         now ││ kind      directory              │",
        "│   f00                    0 B         now ││ size      0 B                    │",
        "│   f01                  1.0 K      1h ago ││ modified  now                    │",
        "│                                          ││ path      /demo/dir/d00          │",
        "╰──────────────────────────── 1/3 · Name ▲ ╯╰──────────────────────────────────╯",
        " q quit  / filter  Enter open directory  Backspace parent directory ● 3 entries",
    ];
    for (y, want) in expected.iter().enumerate().map(|(y, want)| (y + 1, want)) {
        assert_eq!(line(&terminal, y), *want, "row {y}");
    }
}

#[test]
fn below_the_minimum_the_screen_says_so() {
    let mut app = app(1, 1);
    let (terminal, hits) = draw(&mut app, 30, 8);
    assert!(screen_text(terminal.backend().buffer()).contains("tui-template needs 40x10"));
    assert_eq!(hits, Hits::default(), "nothing to click");
}

#[test]
fn a_narrow_terminal_shows_one_pane_and_tab_swaps_it() {
    let mut app = app(1, 1);
    let (terminal, _) = draw(&mut app, 60, 12);
    assert!(line(&terminal, 1).contains("Files") && !line(&terminal, 1).contains("Details"));
    let _ = press(&mut app, KeyCode::Tab);
    let (terminal, _) = draw(&mut app, 60, 12);
    assert!(line(&terminal, 1).contains("Details"));
}

/// Every button is its key: clicking it leaves the app exactly as pressing
/// the key would, and it is only drawn where that key does something.
#[test]
fn every_button_drawn_is_exactly_its_key_and_does_something() {
    let mut states = vec![app(3, 40), app(0, 0)];
    let mut filtered = app(3, 40);
    for c in "f1".chars() {
        let _ = press(&mut filtered, KeyCode::Char(c));
    }
    filtered.filtering = false;
    states.push(filtered);
    let mut on_file = app(1, 40);
    let _ = press(&mut on_file, KeyCode::End);
    states.push(on_file);

    let mut checked = 0;
    for state in &mut states {
        for (width, height) in [(100, 20), (60, 14)] {
            let (_, hits) = draw(state, width, height);
            for &(rect, target) in hits.iter() {
                let Target::Button(key) = target else {
                    continue;
                };
                let at = Position::new(rect.x, rect.y);
                if hits.at(at).map(|(_, on)| on) != Some(target) {
                    continue; // covered by something drawn later
                }
                let (mut clicked, mut pressed) = (state.clone(), state.clone());
                let by_click = click(&mut clicked, &hits, (at.x, at.y), Instant::now());
                let by_key = pressed.key(key);
                clicked.mouse = Mouse::default();
                pressed.mouse = Mouse::default();
                assert_eq!(clicked, pressed, "{key:?} at {at:?}");
                assert_eq!(by_click.actions, by_key.actions, "{key:?}");
                assert!(
                    pressed != *state || !by_key.actions.is_empty(),
                    "{key:?} at {at:?} does nothing"
                );
                checked += 1;
            }
        }
    }
    assert!(checked >= 30, "only {checked} buttons checked");
}

#[test]
fn a_click_selects_a_row_and_a_double_click_opens_a_directory() {
    let mut app = app(3, 3);
    let (_, hits) = draw(&mut app, 100, 20);
    let rows = rect(&hits, |t| matches!(t, Target::Rows { .. }));
    let now = Instant::now();
    let _ = click(&mut app, &hits, (rows.x + 3, rows.y + 1), now);
    assert_eq!(app.list.cursor, 1);
    let second = click(
        &mut app,
        &hits,
        (rows.x + 3, rows.y + 1),
        now + Duration::from_millis(200),
    );
    assert_eq!(
        second.actions,
        vec![Action::Load(PathBuf::from("/demo/dir/d01"))]
    );
}

#[test]
fn a_press_that_slides_off_its_row_is_not_a_click() {
    let mut app = app(0, 10);
    let (_, hits) = draw(&mut app, 100, 20);
    let rows = rect(&hits, |t| matches!(t, Target::Rows { .. }));
    let now = Instant::now();
    let _ = mouse(
        &mut app,
        &hits,
        MouseEventKind::Down(MouseButton::Left),
        (rows.x, rows.y + 2),
        now,
    );
    let _ = mouse(
        &mut app,
        &hits,
        MouseEventKind::Drag(MouseButton::Left),
        (rows.x, rows.y + 5),
        now,
    );
    let _ = mouse(
        &mut app,
        &hits,
        MouseEventKind::Up(MouseButton::Left),
        (rows.x, rows.y + 2),
        now,
    );
    assert_eq!(app.list.cursor, 0);
}

#[test]
fn the_wheel_scrolls_the_pane_under_the_pointer_and_leaves_the_focus() {
    let mut app = app(0, 100);
    app.focus = Focus::Details;
    let (_, hits) = draw(&mut app, 100, 20);
    let rows = rect(&hits, |t| matches!(t, Target::Rows { .. }));
    let scrolled = mouse(
        &mut app,
        &hits,
        MouseEventKind::ScrollDown,
        (rows.x, rows.y),
        Instant::now(),
    );
    assert!(scrolled.repaint);
    assert_eq!(
        (app.list.top, app.list.cursor),
        (3, 3),
        "the cursor follows only to stay on screen"
    );
    assert_eq!(app.focus, Focus::Details);
}

#[test]
fn dragging_the_thumb_scrolls_and_the_track_below_it_pages() {
    let mut app = app(0, 100);
    let (_, hits) = draw(&mut app, 100, 20);
    let on = rect(&hits, |t| matches!(t, Target::Thumb { .. }));
    let now = Instant::now();
    let _ = mouse(
        &mut app,
        &hits,
        MouseEventKind::Down(MouseButton::Left),
        (on.x, on.y),
        now,
    );
    let dragged = mouse(
        &mut app,
        &hits,
        MouseEventKind::Drag(MouseButton::Left),
        (on.x, on.y + 6),
        now,
    );
    let _ = mouse(
        &mut app,
        &hits,
        MouseEventKind::Up(MouseButton::Left),
        (on.x, on.y + 6),
        now,
    );
    assert!(dragged.repaint && app.list.top > 30, "top {}", app.list.top);

    let mut app = super::tests::app(0, 100);
    let (_, hits) = draw(&mut app, 100, 20);
    let below = rect(
        &hits,
        |t| matches!(t, Target::Button(k) if k.code == KeyCode::PageDown),
    );
    let _ = click(&mut app, &hits, (below.x, below.y), now);
    assert_eq!(app.list.cursor, app.list.viewport - 1);
}

#[test]
fn dragging_the_seam_resizes_and_a_double_click_resets_it() {
    let mut app = app(1, 1);
    let (_, hits) = draw(&mut app, 100, 20);
    let seam = rect(&hits, |t| matches!(t, Target::Seam { .. }));
    let now = Instant::now();
    let _ = mouse(
        &mut app,
        &hits,
        MouseEventKind::Down(MouseButton::Left),
        (seam.x, 5),
        now,
    );
    let _ = mouse(
        &mut app,
        &hits,
        MouseEventKind::Drag(MouseButton::Left),
        (30, 5),
        now,
    );
    let _ = mouse(
        &mut app,
        &hits,
        MouseEventKind::Up(MouseButton::Left),
        (30, 5),
        now,
    );
    assert_eq!(app.split.list, 30);

    let (_, hits) = draw(&mut app, 100, 20);
    let seam = rect(&hits, |t| matches!(t, Target::Seam { .. }));
    let _ = click(&mut app, &hits, (seam.x, 5), now);
    let _ = click(
        &mut app,
        &hits,
        (seam.x, 5),
        now + Duration::from_millis(100),
    );
    assert_eq!(app.split, Split::default());
}

#[test]
fn hover_repaints_only_when_the_lit_target_changes() {
    let mut app = app(1, 5);
    let (_, hits) = draw(&mut app, 100, 20);
    let help = rect(
        &hits,
        |t| matches!(t, Target::Button(k) if k.code == KeyCode::Char('?')),
    );
    let rows = rect(&hits, |t| matches!(t, Target::Rows { .. }));
    let now = Instant::now();
    let moved = |app: &mut App, at| mouse(app, &hits, MouseEventKind::Moved, at, now).repaint;
    assert!(!moved(&mut app, (rows.x, rows.y)), "rows do not light up");
    assert!(moved(&mut app, (help.x, help.y)));
    assert!(
        !moved(&mut app, (help.x + 1, help.y)),
        "same button, same frame"
    );
    let (terminal, _) = draw(&mut app, 100, 20);
    let lit = terminal.backend().buffer()[(help.x, help.y)].style();
    assert_eq!(lit.bg, theme().hover.bg.or(lit.bg));
    assert!(lit.add_modifier.contains(theme().hover.add_modifier));
}

#[test]
fn a_click_outside_help_closes_it_and_reaches_nothing_underneath() {
    let mut app = app(0, 10);
    let _ = press(&mut app, KeyCode::Char('?'));
    let (_, hits) = draw(&mut app, 100, 30);
    let _ = click(&mut app, &hits, (3, 7), Instant::now());
    assert_eq!(app.help, None);
    assert_eq!(
        app.list.cursor, 0,
        "the row under the overlay was not clicked"
    );
}

#[test]
fn the_cursor_row_is_painted_with_the_selected_token() {
    let mut app = app(0, 3);
    let (terminal, hits) = draw(&mut app, 100, 20);
    let rows = rect(&hits, |t| matches!(t, Target::Rows { .. }));
    let style = terminal.backend().buffer()[(rows.x + 4, rows.y)].style();
    let selected = theme().selected;
    assert_eq!(style.bg, selected.bg.or(style.bg));
    assert!(style.add_modifier.contains(selected.add_modifier));
}

#[test]
fn the_readme_lists_every_key() {
    let readme = include_str!("../../README.md");
    for key in KEYS {
        assert!(
            readme.contains(&format!("| `{}` |", key.name)),
            "README is missing `{}`",
            key.name
        );
    }
}

/// Budgets: a frame and a filter keystroke under 16 ms at 100k rows.
/// `cargo test --release -- --ignored`
#[test]
#[ignore = "a timing: cargo test --release -- --ignored"]
fn draw_and_filter_cost_is_independent_of_rows() {
    let mut app = app(0, 100_000);
    let started = Instant::now();
    let _ = draw(&mut app, 200, 60);
    let drawn = started.elapsed();
    let started = Instant::now();
    let _ = press(&mut app, KeyCode::Char('/'));
    let _ = press(&mut app, KeyCode::Char('9'));
    let filtered = started.elapsed();
    assert!(drawn < Duration::from_millis(16), "draw {drawn:?}");
    assert!(filtered < Duration::from_millis(16), "filter {filtered:?}");
}
