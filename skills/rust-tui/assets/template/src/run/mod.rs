//! The only module that blocks: it owns the terminal, the worker and the
//! clock, and carries out the `Action`s the app returns.

mod replay;
#[cfg(test)]
mod tests;

use std::io::stdout;
use std::process::ExitCode;
use std::thread;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use crossterm::event::{
    self, DisableBracketedPaste, DisableMouseCapture, EnableBracketedPaste, EnableMouseCapture,
    Event,
};
use crossterm::execute;
use ratatui::Terminal;
use ratatui::backend::Backend;

use crate::app::pointer::Hits;
use crate::app::{Action, App, Outcome};
use crate::cli::Cli;
use crate::config::{self, Config};
use crate::trace::{Trace, ms};
use crate::ui::{self, Theme};
use crate::worker::{Request, Worker};

/// With nothing to do the loop still wakes this often, to collect worker
/// answers (they do not wake it).
const IDLE: Duration = Duration::from_millis(250);
/// A burst of input becomes one frame, but never holds a frame back longer.
const DRAIN_LIMIT: Duration = Duration::from_millis(50);
const SLOW_TURN: Duration = Duration::from_millis(30);

pub fn main(cli: Cli) -> Result<ExitCode> {
    let env = |key: &str| std::env::var(key).ok();
    let config = match &cli.config {
        Some(path) => config::load(path, true)?,
        None => match config::default_path(env) {
            Some(path) => config::load(&path, false)?,
            None => Config::default(),
        },
    };
    let theme = Theme::select(cli.theme.as_deref(), &config.theme, env)?;
    let dir = std::fs::canonicalize(&cli.dir)
        .with_context(|| format!("cannot open {}", cli.dir.display()))?;
    let app = App::new(dir);
    let driver = Driver::new(
        theme,
        Worker::spawn().context("could not start the worker")?,
    );
    if let Some(script) = &cli.replay {
        return replay::run(script, cli.size, cli.frames_dir.as_deref(), app, driver);
    }
    interactive(app, driver)?;
    Ok(ExitCode::SUCCESS)
}

/// Where events come from: the terminal, or a replay queue.
pub trait InputSource {
    fn next(&mut self, timeout: Duration) -> Result<Option<Event>>;
}

struct TerminalInput;

impl InputSource for TerminalInput {
    fn next(&mut self, timeout: Duration) -> Result<Option<Event>> {
        Ok(if event::poll(timeout)? {
            Some(event::read()?)
        } else {
            None
        })
    }
}

pub struct Driver {
    theme: Theme,
    worker: Worker,
    trace: Trace,
    /// What the last frame drew; the next click is read against it.
    hits: Hits,
    dirty: bool,
    /// A click that arrived behind a change not yet painted waits for the
    /// frame, so it lands on what the user will have seen.
    held: Option<Event>,
    pub frames: usize,
}

impl Driver {
    #[must_use]
    pub fn new(theme: Theme, worker: Worker) -> Self {
        Self {
            theme,
            worker,
            trace: Trace::from_env(),
            hits: Hits::default(),
            dirty: true,
            held: None,
            frames: 0,
        }
    }

    pub fn dispatch(&self, actions: Vec<Action>) {
        for action in actions {
            match action {
                Action::Load(dir) => self.worker.send(Request::List(dir)),
            }
        }
    }

    /// One pass: collect answers, run timers, paint if anything changed,
    /// then wait for input and drain what queued. `false` once quitting.
    pub fn turn<B>(
        &mut self,
        terminal: &mut Terminal<B>,
        app: &mut App,
        input: &mut impl InputSource,
    ) -> Result<bool>
    where
        B: Backend,
        B::Error: Send + Sync + 'static,
    {
        while let Some(event) = self.worker.try_event() {
            self.dirty |= app.apply(event, Instant::now());
        }
        let now = Instant::now();
        self.dirty |= app.settle(now);
        let mut draw_ms = Duration::ZERO;
        if self.dirty {
            let started = Instant::now();
            terminal.draw(|frame| self.hits = ui::render(frame, app, &self.theme))?;
            app.drawn(&self.hits);
            self.dirty = false;
            self.frames += 1;
            draw_ms = started.elapsed();
            if self.trace.is_on() {
                self.trace.event("frame", &[("draw_ms", ms(draw_ms))]);
            }
        }
        if app.should_quit {
            return Ok(false);
        }
        let timeout = app.wakeup(now).map_or(IDLE, |due| due.min(IDLE));
        let mut next = match self.held.take() {
            Some(event) => Some(event),
            None => input.next(timeout)?,
        };
        let handling = Instant::now();
        while let Some(event) = next {
            if self.dirty && matches!(event, Event::Mouse(_)) {
                self.held = Some(event);
                break;
            }
            self.handle(app, event);
            if app.should_quit || handling.elapsed() >= DRAIN_LIMIT {
                break;
            }
            next = input.next(Duration::ZERO)?;
        }
        let input_ms = handling.elapsed();
        if self.trace.is_on() && draw_ms + input_ms >= SLOW_TURN {
            self.trace.event(
                "turn",
                &[("draw_ms", ms(draw_ms)), ("input_ms", ms(input_ms))],
            );
        }
        Ok(!app.should_quit)
    }

    fn handle(&mut self, app: &mut App, event: Event) {
        let outcome = match event {
            Event::Key(key) => app.key(key),
            Event::Mouse(mouse) => app.pointer(mouse, Instant::now(), &self.hits),
            Event::Paste(text) => Outcome::repaint(app.paste(&text)),
            // `draw` resizes the buffer itself; the frame only needs painting.
            Event::Resize(..) => Outcome::repaint(true),
            Event::FocusGained | Event::FocusLost => Outcome::default(),
        };
        self.dirty |= outcome.repaint;
        self.dispatch(outcome.actions);
    }

    #[must_use]
    pub const fn settled(&self) -> bool {
        self.held.is_none()
    }
}

fn interactive(mut app: App, mut driver: Driver) -> Result<()> {
    let mut terminal = ratatui::try_init().context("could not take the terminal")?;
    let _restore = Restore;
    keep_the_screen_on_worker_panics();
    execute!(stdout(), EnableMouseCapture, EnableBracketedPaste)?;
    driver.dispatch(app.start());
    while driver.turn(&mut terminal, &mut app, &mut TerminalInput)? {}
    Ok(())
}

/// Every exit path, `?` and unwinding included, gives the terminal back.
struct Restore;

impl Drop for Restore {
    fn drop(&mut self) {
        release();
    }
}

/// Mouse capture goes off before the alternate screen is left, or the shell
/// receives the escape codes of every mouse move.
fn release() {
    let _ = execute!(stdout(), DisableMouseCapture, DisableBracketedPaste);
    ratatui::restore();
}

/// `ratatui::try_init`'s hook restores the terminal on any panic. A worker's
/// panic must not: the UI keeps running and reports the worker stopped, and
/// the message goes to the trace instead of over the screen.
fn keep_the_screen_on_worker_panics() {
    let restore_and_print = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        if thread::current().name() == Some("main") {
            let _ = execute!(stdout(), DisableMouseCapture, DisableBracketedPaste);
            restore_and_print(info);
        } else {
            Trace::from_env().event("panic", &[("message", info.to_string())]);
        }
    }));
}
