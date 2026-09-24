use std::path::PathBuf;
use std::time::{Duration, Instant};

use crossterm::event::{
    Event, KeyCode, KeyEvent, KeyModifiers, MouseButton, MouseEvent, MouseEventKind,
};
use ratatui::Terminal;
use ratatui::backend::TestBackend;

use super::Driver;
use super::replay::Queue;
use crate::app::App;
use crate::ui::Theme;
use crate::worker::Worker;

fn loaded() -> (Driver, App, Terminal<TestBackend>, Queue) {
    let mut driver = Driver::new(Theme::mono(), Worker::spawn().unwrap());
    let mut app = App::new(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src"));
    let mut terminal = Terminal::new(TestBackend::new(100, 30)).unwrap();
    let mut queue = Queue::default();
    driver.dispatch(app.start());
    let deadline = Instant::now() + Duration::from_secs(5);
    while app.loading || driver.dirty {
        assert!(Instant::now() < deadline, "the listing never arrived");
        driver.turn(&mut terminal, &mut app, &mut queue).unwrap();
    }
    (driver, app, terminal, queue)
}

#[test]
fn an_idle_app_draws_nothing_more() {
    let (mut driver, mut app, mut terminal, mut queue) = loaded();
    let frames = driver.frames;
    for _ in 0..5 {
        driver.turn(&mut terminal, &mut app, &mut queue).unwrap();
    }
    assert_eq!(driver.frames, frames);
}

#[test]
fn a_click_behind_a_key_that_changed_the_layout_lands_on_the_new_layout() {
    let (mut driver, mut app, mut terminal, mut queue) = loaded();
    let at = |kind| {
        Event::Mouse(MouseEvent {
            kind,
            column: 5,
            row: 6,
            modifiers: KeyModifiers::NONE,
        })
    };
    // `?` opens help over the rows; the click that follows at once is behind it.
    queue.0.push_back(Event::Key(KeyEvent::new(
        KeyCode::Char('?'),
        KeyModifiers::NONE,
    )));
    queue
        .0
        .push_back(at(MouseEventKind::Down(MouseButton::Left)));
    queue.0.push_back(at(MouseEventKind::Up(MouseButton::Left)));
    for _ in 0..4 {
        driver.turn(&mut terminal, &mut app, &mut queue).unwrap();
    }
    assert_eq!(app.help, None, "the click closed help");
    assert_eq!(app.list.cursor, 0, "and did not select the row under it");
}
