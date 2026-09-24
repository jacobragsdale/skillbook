//! The only code that touches the filesystem after startup. The UI thread
//! sends a `Request` and polls for an `Event`; it never waits on IO.
//!
//! Replace `Request`, `Event` and `serve` with the app's own IO. When the
//! driver is async-only, build a current-thread tokio runtime inside the
//! spawned thread and `block_on` there; nothing async leaves this module.

use std::cell::Cell;
use std::path::PathBuf;
use std::sync::mpsc::{self, Receiver, Sender, TryRecvError};
use std::thread;
use std::time::SystemTime;

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Entry {
    pub name: String,
    pub dir: bool,
    pub size: u64,
    pub modified: Option<SystemTime>,
}

#[derive(Debug)]
pub enum Request {
    List(PathBuf),
}

#[derive(Debug)]
pub enum Event {
    /// Answers echo what they answer, so the app can drop a stale one.
    Listed {
        dir: PathBuf,
        at: SystemTime,
        result: Result<Vec<Entry>, String>,
    },
    /// The worker thread is gone; reported once.
    Stopped,
}

pub struct Worker {
    requests: Sender<Request>,
    events: Receiver<Event>,
    stopped: Cell<bool>,
}

impl Worker {
    pub fn spawn() -> std::io::Result<Self> {
        let (requests, inbox) = mpsc::channel();
        let (outbox, events) = mpsc::channel();
        thread::Builder::new()
            .name("worker".into())
            .spawn(move || serve(&inbox, &outbox))?;
        Ok(Self {
            requests,
            events,
            stopped: Cell::new(false),
        })
    }

    /// A closed channel surfaces as `Event::Stopped`, so this never fails.
    pub fn send(&self, request: Request) {
        let _ = self.requests.send(request);
    }

    #[must_use]
    pub fn try_event(&self) -> Option<Event> {
        match self.events.try_recv() {
            Ok(event) => Some(event),
            Err(TryRecvError::Empty) => None,
            Err(TryRecvError::Disconnected) => {
                (!self.stopped.replace(true)).then_some(Event::Stopped)
            }
        }
    }
}

// Dropping `Worker` drops the sender, which ends `serve` after the request in
// flight. Nothing joins it: quitting must never wait on slow IO.

fn serve(inbox: &Receiver<Request>, outbox: &Sender<Event>) {
    while let Ok(mut request) = inbox.recv() {
        // Latest wins: a burst of requests costs one read.
        for newer in inbox.try_iter() {
            request = newer;
        }
        let event = match request {
            Request::List(dir) => {
                let result = list(&dir).map_err(|error| format!("{}: {error}", dir.display()));
                Event::Listed {
                    dir,
                    at: SystemTime::now(),
                    result,
                }
            }
        };
        if outbox.send(event).is_err() {
            return;
        }
    }
}

fn list(dir: &std::path::Path) -> std::io::Result<Vec<Entry>> {
    let mut entries = Vec::new();
    for item in std::fs::read_dir(dir)? {
        let item = item?;
        let meta = item.metadata()?;
        entries.push(Entry {
            name: item.file_name().to_string_lossy().into_owned(),
            dir: meta.is_dir(),
            size: meta.len(),
            modified: meta.modified().ok(),
        });
    }
    Ok(entries)
}
