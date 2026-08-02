#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Validate and render one Mermaid source file with Mermaid CLI."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

PINNED_MERMAID_CLI_VERSION = "11.16.0"
SUPPORTED_OUTPUTS = {".svg", ".png", ".pdf"}
VERSION_PATTERN = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+-]*")
RunnerChoice = Literal["auto", "mmdc", "npx"]


@dataclass(frozen=True)
class RenderOptions:
    source: Path
    output: Path
    runner: RunnerChoice
    mermaid_version: str
    width: int
    height: int
    background: str
    timeout_seconds: int


@dataclass(frozen=True)
class Runner:
    command: tuple[str, ...]
    label: str


def parse_args() -> RenderOptions:
    parser = argparse.ArgumentParser(
        description=(
            "Render a .mmd file with an installed mmdc, falling back to an "
            "npx-pinned Mermaid CLI. A successful render validates syntax."
        )
    )
    _ = parser.add_argument("input", type=Path, help="Mermaid .mmd source file")
    _ = parser.add_argument(
        "--output",
        type=Path,
        help="output .svg, .png, or .pdf path (default: <input>.svg)",
    )
    _ = parser.add_argument(
        "--runner",
        choices=("auto", "mmdc", "npx"),
        default="auto",
        help="renderer command selection (default: auto)",
    )
    _ = parser.add_argument(
        "--mermaid-version",
        default=PINNED_MERMAID_CLI_VERSION,
        help=(
            "Mermaid CLI version used by the npx runner "
            f"(default: {PINNED_MERMAID_CLI_VERSION})"
        ),
    )
    _ = parser.add_argument("--width", type=positive_int, default=1600)
    _ = parser.add_argument("--height", type=positive_int, default=1200)
    _ = parser.add_argument(
        "--background",
        default="white",
        help="SVG/PNG background accepted by mmdc (default: white)",
    )
    _ = parser.add_argument(
        "--timeout-seconds",
        type=positive_int,
        default=120,
        help="maximum render time, including npx startup (default: 120)",
    )
    namespace = parser.parse_args()
    source = cast(Path, namespace.input).expanduser()
    output_argument = cast(Path | None, namespace.output)
    output = (
        output_argument.expanduser()
        if output_argument is not None
        else source.with_suffix(".svg")
    )
    return RenderOptions(
        source=source,
        output=output,
        runner=cast(RunnerChoice, namespace.runner),
        mermaid_version=cast(str, namespace.mermaid_version),
        width=cast(int, namespace.width),
        height=cast(int, namespace.height),
        background=cast(str, namespace.background),
        timeout_seconds=cast(int, namespace.timeout_seconds),
    )


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def choose_runner(selection: RunnerChoice, version: str) -> Runner:
    mmdc = shutil.which("mmdc")
    npx = shutil.which("npx")

    if selection in {"auto", "mmdc"} and mmdc is not None:
        return Runner(command=(mmdc,), label=f"installed mmdc at {mmdc}")
    if selection == "mmdc":
        raise RuntimeError("mmdc was requested but is not on PATH")
    if npx is not None:
        package = f"@mermaid-js/mermaid-cli@{version}"
        return Runner(command=(npx, "-y", package), label=f"npx {package}")
    raise RuntimeError("no Mermaid renderer found; install mmdc or make npx available")


def validate_paths(source: Path, output: Path) -> None:
    if not source.is_file():
        raise RuntimeError(f"input file does not exist: {source}")
    if source.suffix.lower() != ".mmd":
        raise RuntimeError(f"input must end in .mmd: {source}")
    if source.stat().st_size == 0:
        raise RuntimeError(f"input file is empty: {source}")
    if output.suffix.lower() not in SUPPORTED_OUTPUTS:
        allowed = ", ".join(sorted(SUPPORTED_OUTPUTS))
        raise RuntimeError(f"output must end in {allowed}: {output}")
    if source.resolve() == output.resolve():
        raise RuntimeError("input and output paths must differ")


def render(options: RenderOptions) -> Path:
    validate_paths(options.source, options.output)
    if VERSION_PATTERN.fullmatch(options.mermaid_version) is None:
        raise RuntimeError(
            "Mermaid CLI version must be an npm tag or version containing only "
            "letters, digits, dots, plus signs, or hyphens"
        )
    if options.background.strip() == "":
        raise RuntimeError("background cannot be empty")
    options.output.parent.mkdir(parents=True, exist_ok=True)

    runner = choose_runner(options.runner, options.mermaid_version)
    command = [
        *runner.command,
        "--input",
        str(options.source),
        "--output",
        str(options.output),
        "--width",
        str(options.width),
        "--height",
        str(options.height),
        "--backgroundColor",
        options.background,
        "--quiet",
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=options.timeout_seconds,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        if stderr != "":
            details = stderr
        elif stdout != "":
            details = stdout
        else:
            details = "no diagnostic"
        raise RuntimeError(f"Mermaid render failed via {runner.label}:\n{details}")
    if not options.output.is_file() or options.output.stat().st_size == 0:
        raise RuntimeError(
            "Mermaid reported success via "
            f"{runner.label} but produced no output: {options.output}"
        )

    print(f"rendered {options.source} -> {options.output} via {runner.label}")
    return options.output


def main() -> int:
    try:
        _ = render(parse_args())
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
