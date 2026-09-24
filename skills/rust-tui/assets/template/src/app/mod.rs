//! Pure state. Nothing here touches the terminal, a thread, a file or the
//! clock: events come in, `Action`s go out, and every `Instant` is passed in.

pub mod pointer;

use std::cmp::Ordering;
use std::path::PathBuf;
use std::time::{Duration, Instant, SystemTime};

use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyModifiers};

use crate::worker::{Entry, Event};
use pointer::{Hits, Mouse, Split, Target};

/// One table: help, footer hints, the README and the tests all read it.
/// Every `name` parses with `key_named`, so a button can press it.
pub struct Key {
    pub name: &'static str,
    pub does: &'static str,
    /// Shown in the footer, where its key does something.
    pub hint: bool,
}

const fn key(name: &'static str, does: &'static str, hint: bool) -> Key {
    Key { name, does, hint }
}

pub const KEYS: &[Key] = &[
    key("q", "quit", true),
    key("?", "help", false),
    key("/", "filter", true),
    key("Enter", "open directory", true),
    key("Backspace", "parent directory", true),
    key("j", "down (also ↓)", false),
    key("k", "up (also ↑)", false),
    key("PageDown", "page down", false),
    key("PageUp", "page up", false),
    key("g", "first (also Home)", false),
    key("G", "last (also End)", false),
    key("Tab", "switch pane", false),
    key("s", "sort by the next column", false),
    key("S", "reverse the sort", false),
    key("r", "reload", false),
    key("Esc", "close, clear the filter", false),
    key("Ctrl-C", "quit, even while typing", false),
];

/// Every side effect leaves the app through here; `run` carries it out.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Action {
    Load(PathBuf),
}

/// What an input did: the side effects, and whether the frame changed.
#[derive(Debug, Default, Eq, PartialEq)]
pub struct Outcome {
    pub actions: Vec<Action>,
    pub repaint: bool,
}

impl Outcome {
    #[must_use]
    pub const fn repaint(repaint: bool) -> Self {
        Self {
            actions: Vec::new(),
            repaint,
        }
    }

    fn actions(actions: Vec<Action>) -> Self {
        Self {
            actions,
            repaint: true,
        }
    }
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum Focus {
    #[default]
    List,
    Details,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum Column {
    #[default]
    Name,
    Size,
    Modified,
}

impl Column {
    pub const ALL: [Self; 3] = [Self::Name, Self::Size, Self::Modified];

    #[must_use]
    pub const fn title(self) -> &'static str {
        match self {
            Self::Name => "Name",
            Self::Size => "Size",
            Self::Modified => "Modified",
        }
    }

    const fn next(self) -> Self {
        match self {
            Self::Name => Self::Size,
            Self::Size => Self::Modified,
            Self::Modified => Self::Name,
        }
    }
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Sort {
    pub column: Column,
    pub desc: bool,
}

/// The cursor, and the window the renderer last drew around it. `top` is a
/// hint: the renderer clamps it so the cursor is always on screen.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct ListView {
    pub cursor: usize,
    pub top: usize,
    pub viewport: usize,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Note {
    pub text: String,
    pub error: bool,
    until: Instant,
}

const NOTE_FOR: Duration = Duration::from_secs(4);
const ERROR_FOR: Duration = Duration::from_secs(8);
pub const SPIN_EVERY: Duration = Duration::from_millis(100);
pub const SPINNER: [&str; 8] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"];

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct App {
    pub dir: PathBuf,
    pub entries: Vec<Entry>,
    /// Lower-cased names, built once per listing so a keystroke allocates nothing.
    lower: Vec<String>,
    /// `entries` indexes in sort order, rebuilt only when the sort or rows change.
    sorted: Vec<usize>,
    /// `sorted` filtered: what the list shows. Indexes into `entries`.
    pub visible: Vec<usize>,
    pub listed_at: Option<SystemTime>,
    pub loading: bool,
    pub error: Option<String>,
    /// After going up, land on the directory we came from.
    reselect: Option<String>,
    pub list: ListView,
    pub filter: String,
    pub filtering: bool,
    pub sort: Sort,
    pub focus: Focus,
    /// `Some(top row)` while the help overlay is open.
    pub help: Option<usize>,
    pub note: Option<Note>,
    pub spinner: usize,
    spun_at: Option<Instant>,
    pub split: Split,
    pub mouse: Mouse,
    pub should_quit: bool,
}

impl App {
    #[must_use]
    pub fn new(dir: PathBuf) -> Self {
        Self {
            dir,
            ..Self::default()
        }
    }

    /// The first request, sent by `run` once the terminal is claimed.
    pub fn start(&mut self) -> Vec<Action> {
        self.load(self.dir.clone())
    }

    fn load(&mut self, dir: PathBuf) -> Vec<Action> {
        if dir != self.dir {
            self.reselect = self
                .dir
                .strip_prefix(&dir)
                .ok()
                .and_then(|rest| rest.components().next())
                .map(|name| name.as_os_str().to_string_lossy().into_owned());
            self.dir.clone_from(&dir);
            self.entries.clear();
            self.lower.clear();
            self.filter.clear();
            self.filtering = false;
            self.list = ListView::default();
            self.resort();
        }
        self.loading = true;
        self.error = None;
        vec![Action::Load(dir)]
    }

    /// A worker answer. One for a directory we have left is dropped, never
    /// shown under the wrong path.
    pub fn apply(&mut self, event: Event, now: Instant) -> bool {
        match event {
            Event::Listed { dir, at, result } => {
                if dir != self.dir {
                    return false;
                }
                self.loading = false;
                self.listed_at = Some(at);
                let keep = self.selected().map(|entry| entry.name.clone());
                match result {
                    Ok(entries) => {
                        self.lower = entries.iter().map(|e| e.name.to_lowercase()).collect();
                        self.entries = entries;
                    }
                    Err(message) => {
                        self.entries.clear();
                        self.lower.clear();
                        self.error = Some(message);
                    }
                }
                self.resort();
                if let Some(name) = self.reselect.take().or(keep) {
                    self.select_named(&name);
                }
            }
            Event::Stopped => {
                self.loading = false;
                self.notify("the worker stopped; restart to read again", true, now);
            }
        }
        true
    }

    pub fn notify(&mut self, text: impl Into<String>, error: bool, now: Instant) {
        let until = now + if error { ERROR_FOR } else { NOTE_FOR };
        self.note = Some(Note {
            text: text.into(),
            error,
            until,
        });
    }

    /// Timers. Returns whether the frame changed.
    pub fn settle(&mut self, now: Instant) -> bool {
        let mut changed = false;
        if self.note.as_ref().is_some_and(|note| now >= note.until) {
            self.note = None;
            changed = true;
        }
        if self.loading {
            if self
                .spun_at
                .is_none_or(|at| now.duration_since(at) >= SPIN_EVERY)
            {
                self.spinner = (self.spinner + 1) % SPINNER.len();
                self.spun_at = Some(now);
                changed = true;
            }
        } else {
            self.spun_at = None;
        }
        changed
    }

    /// When the loop must wake even with no input. `None`: only input matters.
    #[must_use]
    pub fn wakeup(&self, now: Instant) -> Option<Duration> {
        let note = self
            .note
            .as_ref()
            .map(|note| note.until.saturating_duration_since(now));
        let spin = self.loading.then_some(SPIN_EVERY);
        note.into_iter().chain(spin).min()
    }

    /// The renderer reports the window it drew, so paging knows a page.
    pub fn drawn(&mut self, hits: &Hits) {
        if let Some((rect, Target::Rows { top })) = hits
            .iter()
            .find(|(_, target)| matches!(target, Target::Rows { .. }))
        {
            self.list.top = *top;
            self.list.viewport = usize::from(rect.height);
        }
    }

    #[must_use]
    pub fn selected(&self) -> Option<&Entry> {
        self.visible
            .get(self.list.cursor)
            .map(|&index| &self.entries[index])
    }

    pub fn key(&mut self, key: KeyEvent) -> Outcome {
        if key.kind != KeyEventKind::Press {
            return Outcome::default();
        }
        if key.modifiers.contains(KeyModifiers::CONTROL) && key.code == KeyCode::Char('c') {
            self.should_quit = true;
            return Outcome::repaint(true);
        }
        if self.help.is_some() {
            self.help_key(key);
            return Outcome::repaint(true);
        }
        if self.filtering {
            self.filter_key(key);
            return Outcome::repaint(true);
        }
        Outcome::actions(self.browse_key(key))
    }

    fn help_key(&mut self, key: KeyEvent) {
        let Some(top) = self.help.as_mut() else {
            return;
        };
        match key.code {
            KeyCode::Char('j') | KeyCode::Down => *top = (*top + 1).min(KEYS.len() - 1),
            KeyCode::Char('k') | KeyCode::Up => *top = top.saturating_sub(1),
            KeyCode::Esc | KeyCode::Char('?' | 'q') | KeyCode::F(1) => self.help = None,
            _ => {}
        }
    }

    fn filter_key(&mut self, key: KeyEvent) {
        let ctrl = key.modifiers.contains(KeyModifiers::CONTROL);
        match key.code {
            KeyCode::Enter | KeyCode::Tab => self.filtering = false,
            KeyCode::Esc => self.set_filter(String::new()),
            KeyCode::Down => self.move_by(1),
            KeyCode::Up => self.move_by(-1),
            KeyCode::Backspace => {
                let mut text = self.filter.clone();
                text.pop();
                self.set_filter(text);
            }
            KeyCode::Char('u') if ctrl => self.set_filter(String::new()),
            KeyCode::Char('w') if ctrl => {
                let text = self.filter.trim_end();
                let cut = text.rfind(' ').map_or(0, |at| at + 1);
                self.set_filter(text[..cut].to_owned());
            }
            KeyCode::Char(c)
                if !key
                    .modifiers
                    .intersects(KeyModifiers::CONTROL | KeyModifiers::ALT) =>
            {
                let mut text = self.filter.clone();
                text.push(c);
                self.set_filter(text);
            }
            _ => {}
        }
    }

    fn browse_key(&mut self, key: KeyEvent) -> Vec<Action> {
        if key
            .modifiers
            .intersects(KeyModifiers::CONTROL | KeyModifiers::ALT)
        {
            return Vec::new();
        }
        let page = isize::try_from(self.list.viewport.saturating_sub(1).max(1)).unwrap_or(1);
        match key.code {
            KeyCode::Char('q') => self.should_quit = true,
            KeyCode::Char('?') | KeyCode::F(1) => self.help = Some(0),
            KeyCode::Char('/') => {
                self.focus = Focus::List;
                self.filtering = true;
            }
            KeyCode::Tab | KeyCode::BackTab => {
                self.focus = match self.focus {
                    Focus::List => Focus::Details,
                    Focus::Details => Focus::List,
                };
            }
            KeyCode::Char('j') | KeyCode::Down => self.move_by(1),
            KeyCode::Char('k') | KeyCode::Up => self.move_by(-1),
            KeyCode::PageDown => self.move_by(page),
            KeyCode::PageUp => self.move_by(-page),
            KeyCode::Char('g') | KeyCode::Home => self.list.cursor = 0,
            KeyCode::Char('G') | KeyCode::End => {
                self.list.cursor = self.visible.len().saturating_sub(1)
            }
            KeyCode::Enter => {
                if let Some(entry) = self.selected().filter(|entry| entry.dir) {
                    let dir = self.dir.join(&entry.name);
                    return self.load(dir);
                }
            }
            KeyCode::Backspace | KeyCode::Char('h') | KeyCode::Left => {
                if let Some(parent) = self.dir.parent().map(PathBuf::from) {
                    return self.load(parent);
                }
            }
            KeyCode::Char('r') => return self.load(self.dir.clone()),
            KeyCode::Char('s') => self.sort_by(self.sort.column.next(), false),
            KeyCode::Char('S') => self.sort_by(self.sort.column, !self.sort.desc),
            KeyCode::Esc => {
                if self.filter.is_empty() {
                    self.note = None;
                } else {
                    self.set_filter(String::new());
                }
            }
            _ => {}
        }
        Vec::new()
    }

    /// Whether `name` does something right now, so a hint is drawn only where
    /// its key would act.
    #[must_use]
    pub fn acts(&self, name: &str) -> bool {
        match name {
            "Enter" => self.selected().is_some_and(|entry| entry.dir),
            "Backspace" => self.dir.parent().is_some(),
            _ => true,
        }
    }

    pub fn paste(&mut self, text: &str) -> bool {
        if !self.filtering {
            return false;
        }
        let clean: String = text
            .chars()
            .map(|c| if c.is_control() { ' ' } else { c })
            .collect();
        self.set_filter(format!("{}{clean}", self.filter));
        true
    }

    fn move_by(&mut self, delta: isize) {
        let last = self.visible.len().saturating_sub(1);
        self.list.cursor = self.list.cursor.saturating_add_signed(delta).min(last);
    }

    /// Scroll the view under the pointer; the cursor follows only as far as
    /// it must to stay on screen, so what a key acts on is always visible.
    pub fn wheel(&mut self, delta: isize) -> bool {
        if self.list.viewport == 0 {
            return false;
        }
        let before = self.list;
        let most = self.visible.len().saturating_sub(self.list.viewport);
        self.list.top = self.list.top.saturating_add_signed(delta).min(most);
        let bottom = (self.list.top + self.list.viewport).saturating_sub(1);
        self.list.cursor = self
            .list
            .cursor
            .clamp(self.list.top, bottom.max(self.list.top));
        self.list.cursor = self.list.cursor.min(self.visible.len().saturating_sub(1));
        self.list != before
    }

    pub fn sort_by(&mut self, column: Column, desc: bool) {
        let keep = self.selected().map(|entry| entry.name.clone());
        self.sort = Sort { column, desc };
        self.resort();
        if let Some(name) = keep {
            self.select_named(&name);
        }
    }

    fn set_filter(&mut self, text: String) {
        let keep = self.selected().map(|entry| entry.name.clone());
        self.filter = text;
        if self.filter.is_empty() {
            self.filtering = false;
        }
        self.refilter();
        match keep {
            Some(name) => self.select_named(&name),
            None => self.list.cursor = 0,
        }
    }

    fn resort(&mut self) {
        let Sort { column, desc } = self.sort;
        let entries = &self.entries;
        self.sorted = (0..entries.len()).collect();
        self.sorted.sort_by(|&a, &b| {
            let (a, b) = (&entries[a], &entries[b]);
            let order = match column {
                Column::Name => Ordering::Equal,
                Column::Size => a.size.cmp(&b.size),
                Column::Modified => a.modified.cmp(&b.modified),
            };
            let order = order.then_with(|| a.name.cmp(&b.name));
            // Directories first whichever way the rest runs.
            b.dir
                .cmp(&a.dir)
                .then(if desc { order.reverse() } else { order })
        });
        self.refilter();
    }

    fn refilter(&mut self) {
        let query = self.filter.to_lowercase();
        self.visible.clear();
        self.visible.extend(
            self.sorted
                .iter()
                .copied()
                .filter(|&index| self.lower[index].contains(&query)),
        );
        self.list.cursor = self.list.cursor.min(self.visible.len().saturating_sub(1));
    }

    fn select_named(&mut self, name: &str) {
        if let Some(at) = self
            .visible
            .iter()
            .position(|&index| self.entries[index].name == name)
        {
            self.list.cursor = at;
        } else {
            self.list.cursor = self.list.cursor.min(self.visible.len().saturating_sub(1));
        }
    }

    /// The directory `depth` components deep in the current path.
    #[must_use]
    pub fn ancestor(&self, depth: usize) -> PathBuf {
        self.dir.components().take(depth).collect()
    }
}

/// `Ctrl-C`, `Shift-Tab`, `Enter`, `F1`, `PageDown`, `q`: the names `KEYS`,
/// replay scripts and buttons use.
#[must_use]
pub fn key_named(name: &str) -> Option<KeyEvent> {
    let (modifiers, base) = if let Some(rest) = name.strip_prefix("Ctrl-") {
        (KeyModifiers::CONTROL, rest)
    } else if let Some(rest) = name.strip_prefix("Alt-") {
        (KeyModifiers::ALT, rest)
    } else if name == "Shift-Tab" {
        return Some(KeyEvent::new(KeyCode::BackTab, KeyModifiers::SHIFT));
    } else {
        (KeyModifiers::NONE, name)
    };
    let code = match base {
        "Enter" => KeyCode::Enter,
        "Esc" => KeyCode::Esc,
        "Tab" => KeyCode::Tab,
        "Backspace" => KeyCode::Backspace,
        "Delete" => KeyCode::Delete,
        "Space" => KeyCode::Char(' '),
        "Up" => KeyCode::Up,
        "Down" => KeyCode::Down,
        "Left" => KeyCode::Left,
        "Right" => KeyCode::Right,
        "Home" => KeyCode::Home,
        "End" => KeyCode::End,
        "PageUp" => KeyCode::PageUp,
        "PageDown" => KeyCode::PageDown,
        other => {
            let mut chars = other.chars();
            match (chars.next(), chars.next()) {
                (Some(c), None) => KeyCode::Char(if modifiers.is_empty() {
                    c
                } else {
                    c.to_ascii_lowercase()
                }),
                (Some('F'), Some(_)) => KeyCode::F(other[1..].parse().ok()?),
                _ => return None,
            }
        }
    };
    Some(KeyEvent::new(code, modifiers))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_key_in_the_table_has_a_name_a_button_can_press() {
        for key in KEYS {
            assert!(key_named(key.name).is_some(), "{} does not parse", key.name);
        }
        assert_eq!(
            key_named("Ctrl-C"),
            Some(KeyEvent::new(KeyCode::Char('c'), KeyModifiers::CONTROL))
        );
        assert_eq!(
            key_named("F1"),
            Some(KeyEvent::new(KeyCode::F(1), KeyModifiers::NONE))
        );
        assert_eq!(key_named("nonsense"), None);
    }
}
