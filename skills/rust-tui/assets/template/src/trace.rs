use std::fmt::Write as _;
use std::fs::OpenOptions;
use std::io::Write as _;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

/// `TUI_TEMPLATE_TRACE=<file>` appends one line per frame and per slow turn:
/// `unix_ms<TAB>kind<TAB>k=v ...`. Unset, no clock is read and nothing is
/// formatted, so tracing costs nothing when off.
#[derive(Debug, Default)]
pub struct Trace {
    file: Option<PathBuf>,
}

impl Trace {
    #[must_use]
    pub fn from_env() -> Self {
        let file = std::env::var_os("TUI_TEMPLATE_TRACE")
            .filter(|value| !value.is_empty())
            .map(PathBuf::from);
        Self { file }
    }

    #[must_use]
    pub const fn is_on(&self) -> bool {
        self.file.is_some()
    }

    pub fn event(&self, kind: &str, fields: &[(&str, String)]) {
        let Some(path) = &self.file else { return };
        let ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_or(0, |elapsed| elapsed.as_millis());
        let mut line = format!("{ms}\t{kind}");
        for (key, value) in fields {
            let _ = write!(line, "\t{key}={value}");
        }
        line.push('\n');
        // A trace that cannot be written must never take the app down.
        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
            let _ = file.write_all(line.as_bytes());
        }
    }
}

/// Milliseconds with three decimals, the unit every trace field uses.
#[must_use]
pub fn ms(duration: std::time::Duration) -> String {
    format!("{:.3}", duration.as_secs_f64() * 1000.0)
}
