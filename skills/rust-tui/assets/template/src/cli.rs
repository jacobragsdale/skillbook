use std::path::PathBuf;

use anyhow::{Context, Result, bail};
use clap::Parser;

/// With no replay file the TUI opens; everything else is a flag, so
/// `--help` and `--version` answer before any config is read.
#[derive(Debug, Parser)]
#[command(version, about)]
pub struct Cli {
    /// Directory to open.
    #[arg(default_value = ".")]
    pub dir: PathBuf,
    /// Colour preset: terminal, terminal-light, mono or custom.
    /// Overrides TUI_TEMPLATE_THEME and the config file.
    #[arg(long, value_name = "NAME")]
    pub theme: Option<String>,
    /// Config file (default: $XDG_CONFIG_HOME/tui-template/config.toml).
    #[arg(long, value_name = "FILE", env = "TUI_TEMPLATE_CONFIG")]
    pub config: Option<PathBuf>,
    /// Drive the real loop headlessly from a script of keys and clicks.
    #[arg(long, value_name = "FILE")]
    pub replay: Option<PathBuf>,
    /// Terminal size for --replay, as COLSxROWS.
    #[arg(long, value_name = "COLSxROWS", default_value = "100x30", value_parser = parse_size)]
    pub size: (u16, u16),
    /// Where --replay writes `frame` snapshots (default: stdout).
    #[arg(long, value_name = "DIR")]
    pub frames_dir: Option<PathBuf>,
}

/// `100x30` into (100, 30).
pub fn parse_size(text: &str) -> Result<(u16, u16)> {
    let Some((cols, rows)) = text.split_once('x') else {
        bail!("expected COLSxROWS, like 100x30");
    };
    let cols = cols.parse().context("columns must be a number")?;
    let rows = rows.parse().context("rows must be a number")?;
    Ok((cols, rows))
}
