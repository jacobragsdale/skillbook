use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde::Deserialize;

/// `config.toml`. Every section defaults, unknown keys are ignored so the
/// file can grow, and a missing default file is a first run, not an error.
#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct Config {
    pub theme: ThemeConfig,
}

#[derive(Clone, Debug, Default, Deserialize)]
#[serde(default)]
pub struct ThemeConfig {
    /// terminal, terminal-light, mono or custom.
    pub preset: Option<String>,
    /// Written by the `theme` tool (~/dev/theme); unknown keys are ignored.
    pub custom: Option<Palette>,
}

/// The `theme` tool's vocabulary, as `#rrggbb` strings. Only the keys the
/// theme reads are required.
#[derive(Clone, Debug, Deserialize)]
pub struct Palette {
    pub name: Option<String>,
    pub surface: String,
    pub overlay: String,
    pub fg: String,
    pub subtle: String,
    pub muted: String,
    pub accent: String,
    pub red: String,
    pub green: String,
}

/// `$XDG_CONFIG_HOME/tui-template/config.toml`, else `~/.config/...`, on
/// macOS too. The environment is a closure so tests can pass their own.
#[must_use]
pub fn default_path(env: impl Fn(&str) -> Option<String>) -> Option<PathBuf> {
    let base = env("XDG_CONFIG_HOME")
        .filter(|dir| !dir.is_empty())
        .map(PathBuf::from)
        .or_else(|| env("HOME").map(|home| Path::new(&home).join(".config")))?;
    Some(base.join("tui-template").join("config.toml"))
}

/// A file named by `--config` must exist; the default one may not.
pub fn load(path: &Path, named: bool) -> Result<Config> {
    match std::fs::read_to_string(path) {
        Ok(text) => parse(&text).with_context(|| format!("in {}", path.display())),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound && !named => {
            Ok(Config::default())
        }
        Err(error) => Err(error).with_context(|| format!("could not read {}", path.display())),
    }
}

pub fn parse(text: &str) -> Result<Config> {
    Ok(toml::from_str(text)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn an_empty_file_is_the_default_and_unknown_keys_are_ignored() {
        assert!(parse("").unwrap().theme.preset.is_none());
        let config = parse("later = 1\n[theme]\npreset = \"mono\"\n").unwrap();
        assert_eq!(config.theme.preset.as_deref(), Some("mono"));
    }

    #[test]
    fn xdg_config_home_wins_over_home() {
        let env = |key: &str| match key {
            "XDG_CONFIG_HOME" => Some("/x".to_owned()),
            "HOME" => Some("/h".to_owned()),
            _ => None,
        };
        let path = default_path(env).unwrap();
        assert_eq!(path, Path::new("/x/tui-template/config.toml"));
    }
}
