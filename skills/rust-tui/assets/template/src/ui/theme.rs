//! The only module that names a `Color`. Everything else asks for a token,
//! so a preset, `NO_COLOR` or the `theme` tool's palette restyles it all.

use anyhow::{Result, bail};
use ratatui::style::{Color, Modifier, Style};

use crate::config::{Palette, ThemeConfig};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Theme {
    pub text: Style,
    pub muted: Style,
    pub accent: Style,
    pub header: Style,
    pub border: Style,
    pub border_focused: Style,
    pub selected: Style,
    pub hover: Style,
    pub ok: Style,
    pub error: Style,
}

pub const PRESETS: &[&str] = &["terminal", "terminal-light", "mono", "custom"];

impl Theme {
    /// ANSI-16 only, so the terminal's own palette shows through, over SSH too.
    #[must_use]
    pub fn terminal() -> Self {
        Self {
            text: Style::new(),
            muted: Style::new().fg(Color::DarkGray),
            accent: Style::new().fg(Color::Cyan).add_modifier(Modifier::BOLD),
            header: Style::new()
                .fg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
            border: Style::new().fg(Color::DarkGray),
            border_focused: Style::new().fg(Color::Cyan),
            selected: Style::new()
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
            hover: Style::new().bg(Color::DarkGray).fg(Color::White),
            ok: Style::new().fg(Color::Green),
            error: Style::new().fg(Color::Red),
        }
    }

    #[must_use]
    pub fn terminal_light() -> Self {
        Self {
            accent: Style::new().fg(Color::Blue).add_modifier(Modifier::BOLD),
            border_focused: Style::new().fg(Color::Blue),
            selected: Style::new()
                .bg(Color::Indexed(253))
                .add_modifier(Modifier::BOLD),
            hover: Style::new().bg(Color::Indexed(252)),
            ..Self::terminal()
        }
    }

    /// `NO_COLOR`: weight, reverse video and glyphs carry every distinction.
    #[must_use]
    pub fn mono() -> Self {
        Self {
            text: Style::new(),
            muted: Style::new().add_modifier(Modifier::DIM),
            accent: Style::new().add_modifier(Modifier::BOLD),
            header: Style::new().add_modifier(Modifier::BOLD),
            border: Style::new().add_modifier(Modifier::DIM),
            border_focused: Style::new(),
            selected: Style::new().add_modifier(Modifier::REVERSED | Modifier::BOLD),
            hover: Style::new().add_modifier(Modifier::UNDERLINED),
            ok: Style::new(),
            error: Style::new().add_modifier(Modifier::BOLD),
        }
    }

    pub fn from_palette(palette: &Palette) -> Result<Self> {
        let fg = hex(&palette.fg)?;
        Ok(Self {
            text: Style::new().fg(fg),
            muted: Style::new().fg(hex(&palette.muted)?),
            accent: Style::new()
                .fg(hex(&palette.accent)?)
                .add_modifier(Modifier::BOLD),
            header: Style::new()
                .fg(hex(&palette.subtle)?)
                .add_modifier(Modifier::BOLD),
            border: Style::new().fg(hex(&palette.overlay)?),
            border_focused: Style::new().fg(hex(&palette.accent)?),
            selected: Style::new()
                .bg(hex(&palette.overlay)?)
                .fg(fg)
                .add_modifier(Modifier::BOLD),
            hover: Style::new().bg(hex(&palette.surface)?).fg(fg),
            ok: Style::new().fg(hex(&palette.green)?),
            error: Style::new().fg(hex(&palette.red)?),
        })
    }

    /// `NO_COLOR`, then `--theme`, then `TUI_TEMPLATE_THEME`, then the file's
    /// preset, then `custom` when the file has a palette, then `terminal`.
    /// An unknown name is a startup error, not a silent fallback.
    pub fn select(
        flag: Option<&str>,
        config: &ThemeConfig,
        env: impl Fn(&str) -> Option<String>,
    ) -> Result<Self> {
        if env("NO_COLOR").is_some_and(|value| !value.is_empty()) {
            return Ok(Self::mono());
        }
        let from_env = env("TUI_TEMPLATE_THEME").filter(|value| !value.is_empty());
        let name = flag
            .map(str::to_owned)
            .or(from_env)
            .or_else(|| config.preset.clone())
            .unwrap_or_else(|| {
                if config.custom.is_some() {
                    "custom"
                } else {
                    "terminal"
                }
                .to_owned()
            });
        match name.as_str() {
            "terminal" => Ok(Self::terminal()),
            "terminal-light" => Ok(Self::terminal_light()),
            "mono" => Ok(Self::mono()),
            "custom" => match &config.custom {
                Some(palette) => Self::from_palette(palette),
                None => bail!("theme `custom` needs a [theme.custom] table in the config"),
            },
            other => bail!(
                "unknown theme `{other}`; expected one of {}",
                PRESETS.join(", ")
            ),
        }
    }
}

fn hex(text: &str) -> Result<Color> {
    let digits = text.strip_prefix('#').unwrap_or(text);
    if digits.len() != 6 {
        bail!("`{text}` is not a #rrggbb colour");
    }
    let channel = |at: usize| u8::from_str_radix(&digits[at..at + 2], 16);
    match (channel(0), channel(2), channel(4)) {
        (Ok(r), Ok(g), Ok(b)) => Ok(Color::Rgb(r, g, b)),
        _ => bail!("`{text}` is not a #rrggbb colour"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn none(_: &str) -> Option<String> {
        None
    }

    #[test]
    fn no_color_beats_every_other_choice() {
        let env = |key: &str| (key == "NO_COLOR").then(|| "1".to_owned());
        let theme = Theme::select(Some("terminal"), &ThemeConfig::default(), env).unwrap();
        assert_eq!(theme, Theme::mono());
    }

    #[test]
    fn an_unknown_theme_is_named_in_the_error() {
        let error = Theme::select(Some("neon"), &ThemeConfig::default(), none).unwrap_err();
        assert!(
            error.to_string().contains("unknown theme `neon`"),
            "{error}"
        );
    }

    #[test]
    fn a_palette_in_the_file_is_used_without_a_preset() {
        let config = crate::config::parse(
            "[theme.custom]\nsurface = \"#111111\"\noverlay = \"#222222\"\nfg = \"#eeeeee\"\n\
             subtle = \"#aaaaaa\"\nmuted = \"#777777\"\naccent = \"#c07cff\"\n\
             red = \"#ff5f87\"\ngreen = \"#4ef5a4\"\nbg = \"#000000\"\n",
        )
        .unwrap();
        let theme = Theme::select(None, &config.theme, none).unwrap();
        assert_eq!(theme.accent.fg, Some(Color::Rgb(0xc0, 0x7c, 0xff)));
    }
}
