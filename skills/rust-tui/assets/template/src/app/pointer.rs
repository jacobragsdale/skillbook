//! The mouse. The renderer returns what it drew as `Hits`; the loop keeps
//! the last frame's and hands them here, so a click lands on what the user
//! saw. Targets hold indexes and the window they were drawn from, never
//! references.

use std::ops::Range;
use std::time::{Duration, Instant};

use crossterm::event::{KeyEvent, MouseButton, MouseEvent, MouseEventKind};
use ratatui::layout::{Position, Rect};

use super::{App, Column, Focus, Outcome};

pub const DOUBLE_CLICK: Duration = Duration::from_millis(400);
const WHEEL: isize = 3;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Target {
    /// Clicking it is exactly pressing the key: a button can do nothing a key cannot.
    Button(KeyEvent),
    /// A help row: closes help, then presses the key.
    HelpRow(KeyEvent),
    Pane(Focus),
    /// The list's visible rows, drawn from `top`.
    Rows {
        top: usize,
    },
    Header(Column),
    Filter,
    /// A directory in the title bar's path, by how many components deep.
    Crumb(usize),
    Thumb {
        content: usize,
        viewport: usize,
        track: Rect,
    },
    Seam {
        body: Rect,
    },
    /// An overlay's own area: swallows clicks that hit nothing inside it.
    Overlay,
    /// Everything behind an overlay: a click here closes it and reaches nothing.
    Outside,
}

impl Target {
    /// Only what acts on a click lights up under the pointer.
    #[must_use]
    pub const fn hovers(self) -> bool {
        matches!(
            self,
            Self::Button(_)
                | Self::HelpRow(_)
                | Self::Header(_)
                | Self::Crumb(_)
                | Self::Thumb { .. }
                | Self::Seam { .. }
        )
    }
}

/// Regions in paint order; the last one pushed is on top.
#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct Hits(Vec<(Rect, Target)>);

impl Hits {
    pub fn push(&mut self, rect: Rect, target: Target) {
        if !rect.is_empty() {
            self.0.push((rect, target));
        }
    }

    #[must_use]
    pub fn at(&self, at: Position) -> Option<(Rect, Target)> {
        self.0
            .iter()
            .rev()
            .find(|(rect, _)| rect.contains(at))
            .copied()
    }

    #[must_use]
    pub fn spot(&self, at: Position) -> Option<Spot> {
        self.at(at).map(|(rect, target)| Spot {
            target,
            row: at.y - rect.y,
        })
    }

    pub fn iter(&self) -> impl Iterator<Item = &(Rect, Target)> {
        self.0.iter()
    }
}

/// A target and the row within it: two rows of one list are two spots.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Spot {
    pub target: Target,
    pub row: u16,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Mouse {
    pub pointer: Option<Position>,
    press: Option<Press>,
    last: Option<(Spot, Instant)>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Press {
    spot: Spot,
    /// The pointer slid off the spot: releasing is no longer a click.
    left: bool,
    /// Where on the thumb it was grabbed, so dragging does not jump.
    grab: u16,
}

/// The list's share of the body in percent, so a resize keeps the proportion.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Split {
    pub list: u16,
}

impl Default for Split {
    fn default() -> Self {
        Self { list: 55 }
    }
}

/// No pane is ever narrower than this, at any terminal size.
pub const NARROWEST: u16 = 24;

impl Split {
    #[must_use]
    pub fn areas(self, body: Rect) -> [Rect; 2] {
        let most = body.width.saturating_sub(NARROWEST).max(NARROWEST);
        let list = u16::try_from(u32::from(body.width) * u32::from(self.list) / 100)
            .unwrap_or(u16::MAX)
            .clamp(NARROWEST, most)
            .min(body.width);
        let (left, right) = (
            Rect {
                width: list,
                ..body
            },
            Rect {
                x: body.x + list,
                width: body.width - list,
                ..body
            },
        );
        [left, right]
    }

    fn drag_to(&mut self, x: u16, body: Rect) -> bool {
        let before = *self;
        let offset = u32::from(x.saturating_sub(body.x));
        let percent = offset * 100 / u32::from(body.width.max(1));
        self.list = u16::try_from(percent.clamp(10, 90)).unwrap_or(55);
        *self != before
    }
}

/// Where the thumb sits on a track. The painter and the drag both use this
/// and `offset`, so what is drawn is what is hit.
#[must_use]
pub fn thumb(offset: usize, content: usize, viewport: usize, track: u16) -> Range<u16> {
    if content <= viewport || track == 0 {
        return 0..track;
    }
    let track_len = usize::from(track);
    let len = (track_len * viewport / content).clamp(1, track_len);
    let room = track_len - len;
    let start =
        (offset.min(content - viewport) * room + (content - viewport) / 2) / (content - viewport);
    let start = u16::try_from(start).unwrap_or(0);
    start..start + u16::try_from(len).unwrap_or(track)
}

/// The inverse of `thumb`: the offset a thumb starting at `start` shows.
#[must_use]
pub fn offset(start: u16, content: usize, viewport: usize, track: u16) -> usize {
    let len = thumb(0, content, viewport, track).len();
    let room = usize::from(track).saturating_sub(len);
    if room == 0 {
        return 0;
    }
    let scrollable = content.saturating_sub(viewport);
    (usize::from(start).min(room) * scrollable + room / 2) / room
}

impl App {
    pub fn pointer(&mut self, mouse: MouseEvent, now: Instant, hits: &Hits) -> Outcome {
        let at = Position::new(mouse.column, mouse.row);
        let spot = hits.spot(at);
        let hovered = |p: Option<Position>| {
            p.and_then(|p| hits.at(p))
                .filter(|(_, target)| target.hovers())
        };
        let before = hovered(self.mouse.pointer);
        self.mouse.pointer = Some(at);
        match mouse.kind {
            MouseEventKind::Moved => Outcome::repaint(before != hovered(Some(at))),
            MouseEventKind::Down(MouseButton::Left) => {
                self.mouse.press = spot.map(|spot| Press {
                    spot,
                    left: false,
                    grab: self.grab(spot),
                });
                Outcome::default()
            }
            MouseEventKind::Drag(MouseButton::Left) => self.drag(at, spot),
            MouseEventKind::Up(MouseButton::Left) => match self.mouse.press.take() {
                Some(press) if !press.left && spot == Some(press.spot) => {
                    self.click(press.spot, now)
                }
                _ => Outcome::default(),
            },
            MouseEventKind::ScrollDown => self.scroll(spot, WHEEL),
            MouseEventKind::ScrollUp => self.scroll(spot, -WHEEL),
            _ => Outcome::default(),
        }
    }

    fn grab(&self, spot: Spot) -> u16 {
        match spot.target {
            Target::Thumb { .. } => spot.row,
            _ => 0,
        }
    }

    fn drag(&mut self, at: Position, spot: Option<Spot>) -> Outcome {
        let Some(press) = self.mouse.press.as_mut() else {
            return Outcome::default();
        };
        match press.spot.target {
            Target::Thumb {
                content,
                viewport,
                track,
            } => {
                let start = at.y.saturating_sub(track.y).saturating_sub(press.grab);
                let top = offset(start, content, viewport, track.height);
                let before = self.list;
                self.list.top = top;
                let bottom = (top + self.list.viewport).saturating_sub(1);
                self.list.cursor = self.list.cursor.clamp(top, bottom.max(top));
                Outcome::repaint(self.list != before)
            }
            Target::Seam { body } => Outcome::repaint(self.split.drag_to(at.x, body)),
            _ => {
                if spot != Some(press.spot) {
                    press.left = true;
                }
                Outcome::default()
            }
        }
    }

    fn click(&mut self, spot: Spot, now: Instant) -> Outcome {
        // A double-click consumes both clicks, so a third is a single again.
        let double = self
            .mouse
            .last
            .take()
            .is_some_and(|(last, at)| last == spot && now.duration_since(at) <= DOUBLE_CLICK);
        if !double {
            self.mouse.last = Some((spot, now));
        }
        match spot.target {
            Target::Button(key) => self.key(key),
            Target::HelpRow(key) => {
                self.help = None;
                self.key(key)
            }
            Target::Outside => {
                self.help = None;
                Outcome::repaint(true)
            }
            Target::Overlay | Target::Thumb { .. } => Outcome::default(),
            Target::Pane(focus) => {
                self.focus = focus;
                Outcome::repaint(true)
            }
            Target::Rows { top } => {
                let index = top + usize::from(spot.row);
                if index >= self.visible.len() {
                    self.focus = Focus::List;
                    return Outcome::repaint(true);
                }
                self.focus = Focus::List;
                self.filtering = false;
                self.list.cursor = index;
                if double {
                    return self.key(super::key_named("Enter").expect("Enter is a key name"));
                }
                Outcome::repaint(true)
            }
            Target::Header(column) => {
                let desc = self.sort.column == column && !self.sort.desc;
                self.sort_by(column, desc);
                Outcome::repaint(true)
            }
            Target::Filter => {
                self.focus = Focus::List;
                self.filtering = true;
                Outcome::repaint(true)
            }
            Target::Crumb(depth) => Outcome {
                actions: self.load(self.ancestor(depth)),
                repaint: true,
            },
            Target::Seam { .. } => {
                if double {
                    self.split = Split::default();
                }
                Outcome::repaint(double)
            }
        }
    }

    /// The wheel scrolls what is under the pointer and never moves the focus.
    fn scroll(&mut self, spot: Option<Spot>, delta: isize) -> Outcome {
        match spot.map(|spot| spot.target) {
            Some(
                Target::Rows { .. }
                | Target::Pane(Focus::List)
                | Target::Header(_)
                | Target::Filter
                | Target::Thumb { .. },
            ) => Outcome::repaint(self.wheel(delta)),
            Some(Target::HelpRow(_) | Target::Overlay) => {
                let Some(top) = self.help.as_mut() else {
                    return Outcome::default();
                };
                let before = *top;
                *top = top.saturating_add_signed(delta).min(super::KEYS.len() - 1);
                Outcome::repaint(*top != before)
            }
            _ => Outcome::default(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_thumb_and_its_inverse_agree_at_every_offset() {
        for offset_at in 0..=90 {
            let range = thumb(offset_at, 100, 10, 10);
            assert_eq!(range.len(), 1);
            let back = offset(range.start, 100, 10, 10);
            assert_eq!(thumb(back, 100, 10, 10), range, "offset {offset_at}");
        }
        assert_eq!(
            thumb(0, 5, 10, 8),
            0..8,
            "content that fits fills the track"
        );
        assert_eq!(
            thumb(90, 100, 10, 10).end,
            10,
            "the last offset reaches the end"
        );
    }

    #[test]
    fn the_last_region_pushed_is_the_one_a_click_lands_on() {
        let mut hits = Hits::default();
        hits.push(Rect::new(0, 0, 10, 10), Target::Pane(Focus::List));
        hits.push(Rect::new(0, 0, 10, 10), Target::Outside);
        hits.push(Rect::new(0, 0, 0, 10), Target::Filter);
        assert_eq!(
            hits.at(Position::new(3, 3)).map(|(_, t)| t),
            Some(Target::Outside)
        );
    }

    #[test]
    fn a_split_keeps_both_panes_at_least_the_narrowest() {
        let body = Rect::new(0, 0, 60, 10);
        for list in [0, 10, 55, 90, 100] {
            let [left, right] = Split { list }.areas(body);
            assert!(
                left.width >= NARROWEST && right.width >= NARROWEST,
                "{list}%"
            );
            assert_eq!(left.width + right.width, 60);
        }
    }
}
