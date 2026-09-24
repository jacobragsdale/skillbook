use std::process::ExitCode;

use clap::Parser;
use tui_template::cli::Cli;

fn main() -> ExitCode {
    match tui_template::run::main(Cli::parse()) {
        Ok(code) => code,
        Err(error) => {
            eprintln!("error: {error:#}");
            ExitCode::FAILURE
        }
    }
}
