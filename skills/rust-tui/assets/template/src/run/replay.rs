//! `--replay FILE`: the real loop against a `TestBackend`, driven by a script
//! of keys and clicks, writing frames as text. This is how a change is
//! verified; screenshots never are.
//!
//! One command per line, `#` comments:
//!   key <name>            Enter, Esc, Ctrl-C, PageDown, q (names as in KEYS)
//!   type <text>           each character as a key
//!   paste <text>
//!   click|double-click|hover <x> <y>   or   ... on <text>
//!   scroll up|down <x> <y>             or   ... on <text>
//!   drag <x> <y> <x> <y>
//!   resize <cols>x<rows>
//!   wait                  until nothing is loading (exit 3 after 5 s)
//!   frame <name>          write the screen (to --frames-dir, else stdout)
//!   expect <text>         exit 4, printing the screen, unless it is shown
//!   expect-not <text>

use std::collections::VecDeque;
use std::fmt::Write as _;
use std::path::Path;
use std::process::ExitCode;
use std::time::{Duration, Instant};

use anyhow::{Context, Result, bail};
use crossterm::event::{
    Event, KeyCode, KeyEvent, KeyModifiers, MouseButton, MouseEvent, MouseEventKind,
};
use ratatui::Terminal;
use ratatui::backend::TestBackend;
use ratatui::buffer::Buffer;

use super::{Driver, InputSource};
use crate::app::{App, key_named};
use crate::cli::parse_size;
use crate::ui::screen_text;

const WAIT_LIMIT: Duration = Duration::from_secs(5);

#[derive(Default)]
pub struct Queue(pub(super) VecDeque<Event>);

impl InputSource for Queue {
    fn next(&mut self, _timeout: Duration) -> Result<Option<Event>> {
        Ok(self.0.pop_front())
    }
}

pub fn run(
    script: &Path,
    size: (u16, u16),
    frames: Option<&Path>,
    mut app: App,
    mut driver: Driver,
) -> Result<ExitCode> {
    let text = std::fs::read_to_string(script)
        .with_context(|| format!("could not read {}", script.display()))?;
    let mut terminal = Terminal::new(TestBackend::new(size.0, size.1))?;
    let mut queue = Queue::default();
    driver.dispatch(app.start());
    driver.turn(&mut terminal, &mut app, &mut queue)?;
    for (number, line) in text.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let (command, rest) = line.split_once(' ').unwrap_or((line, ""));
        let screen = terminal.backend().buffer().clone();
        let fail =
            |message: String| anyhow::anyhow!("{}:{}: {message}", script.display(), number + 1);
        match command {
            "key" => queue.0.push_back(Event::Key(
                key_named(rest).ok_or_else(|| fail(format!("no key named `{rest}`")))?,
            )),
            "type" => {
                for c in rest.chars() {
                    queue.0.push_back(Event::Key(KeyEvent::new(
                        KeyCode::Char(c),
                        KeyModifiers::NONE,
                    )));
                }
            }
            "paste" => queue.0.push_back(Event::Paste(rest.to_owned())),
            "click" | "double-click" | "hover" => {
                let (x, y) = place(&screen, rest).map_err(|error| fail(error.to_string()))?;
                let presses = match command {
                    "click" => 1,
                    "double-click" => 2,
                    _ => 0,
                };
                queue.0.push_back(mouse(MouseEventKind::Moved, x, y));
                for _ in 0..presses {
                    queue
                        .0
                        .push_back(mouse(MouseEventKind::Down(MouseButton::Left), x, y));
                    queue
                        .0
                        .push_back(mouse(MouseEventKind::Up(MouseButton::Left), x, y));
                }
            }
            "scroll" => {
                let (way, at) = rest.split_once(' ').unwrap_or((rest, ""));
                let kind = match way {
                    "up" => MouseEventKind::ScrollUp,
                    "down" => MouseEventKind::ScrollDown,
                    _ => return Err(fail(format!("scroll up or down, not `{way}`"))),
                };
                let (x, y) = place(&screen, at).map_err(|error| fail(error.to_string()))?;
                queue.0.push_back(mouse(kind, x, y));
            }
            "drag" => {
                let numbers: Vec<u16> = rest
                    .split_whitespace()
                    .filter_map(|n| n.parse().ok())
                    .collect();
                let [x1, y1, x2, y2] = numbers[..] else {
                    return Err(fail("drag takes four numbers: x y x y".to_owned()));
                };
                queue
                    .0
                    .push_back(mouse(MouseEventKind::Down(MouseButton::Left), x1, y1));
                queue
                    .0
                    .push_back(mouse(MouseEventKind::Drag(MouseButton::Left), x2, y2));
                queue
                    .0
                    .push_back(mouse(MouseEventKind::Up(MouseButton::Left), x2, y2));
            }
            "resize" => {
                let (cols, rows) = parse_size(rest).map_err(|error| fail(error.to_string()))?;
                terminal.backend_mut().resize(cols, rows);
                queue.0.push_back(Event::Resize(cols, rows));
            }
            "wait" => {
                let deadline = Instant::now() + WAIT_LIMIT;
                while app.loading {
                    if Instant::now() >= deadline {
                        eprintln!("{}", screen_text(terminal.backend().buffer()));
                        eprintln!(
                            "{}:{}: still loading after 5 s",
                            script.display(),
                            number + 1
                        );
                        return Ok(ExitCode::from(3));
                    }
                    std::thread::sleep(Duration::from_millis(5));
                    driver.turn(&mut terminal, &mut app, &mut queue)?;
                }
            }
            "frame" => write_frame(frames, rest, &screen)?,
            "expect" | "expect-not" => {
                let shown = screen_text(&screen).contains(rest);
                if shown != (command == "expect") {
                    eprintln!("{}", screen_text(&screen));
                    let verb = if shown { "is shown" } else { "is not shown" };
                    eprintln!("{}:{}: `{rest}` {verb}", script.display(), number + 1);
                    return Ok(ExitCode::from(4));
                }
            }
            other => return Err(fail(format!("unknown command `{other}`"))),
        }
        // Turn until every queued event is handled, then once more to paint.
        while !queue.0.is_empty() || !driver.settled() {
            driver.turn(&mut terminal, &mut app, &mut queue)?;
        }
        if !driver.turn(&mut terminal, &mut app, &mut queue)? {
            break;
        }
    }
    Ok(ExitCode::SUCCESS)
}

fn mouse(kind: MouseEventKind, column: u16, row: u16) -> Event {
    Event::Mouse(MouseEvent {
        kind,
        column,
        row,
        modifiers: KeyModifiers::NONE,
    })
}

/// `12 3`, or `on <text>`: the first cell of the first place the text shows.
fn place(screen: &Buffer, spec: &str) -> Result<(u16, u16)> {
    if let Some(needle) = spec.strip_prefix("on ") {
        return find(screen, needle).with_context(|| format!("`{needle}` is not on screen"));
    }
    let mut numbers = spec.split_whitespace().map(str::parse::<u16>);
    match (numbers.next(), numbers.next()) {
        (Some(Ok(x)), Some(Ok(y))) => Ok((x, y)),
        _ => bail!("expected `<x> <y>` or `on <text>`, got `{spec}`"),
    }
}

#[must_use]
pub fn find(screen: &Buffer, needle: &str) -> Option<(u16, u16)> {
    let area = screen.area;
    for y in area.top()..area.bottom() {
        let mut row = String::new();
        let mut starts = Vec::new();
        for x in area.left()..area.right() {
            starts.push((row.len(), x));
            row.push_str(screen[(x, y)].symbol());
        }
        if let Some(at) = row.find(needle) {
            let x = starts
                .iter()
                .rev()
                .find(|(start, _)| *start <= at)
                .map_or(0, |(_, x)| *x);
            return Some((x, y));
        }
    }
    None
}

fn write_frame(dir: Option<&Path>, name: &str, screen: &Buffer) -> Result<()> {
    let mut text = String::new();
    let _ = writeln!(
        text,
        "# {name} {}x{}",
        screen.area.width, screen.area.height
    );
    text.push_str(&screen_text(screen));
    text.push('\n');
    match dir {
        Some(dir) => {
            std::fs::create_dir_all(dir)?;
            let path = dir.join(format!("{name}.txt"));
            std::fs::write(&path, text)
                .with_context(|| format!("could not write {}", path.display()))
        }
        None => {
            print!("{text}");
            Ok(())
        }
    }
}
