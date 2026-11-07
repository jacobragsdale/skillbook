#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Run herdr-app against the person's Herdr window from any machine.

`herdr-app` reaches the window only through a socket on the computer that
shows it (herdrdev/herdr-app#311). This wrapper takes the same arguments and
picks the route:

  1. --host DEST or HERDR_WINDOW_HOST=DEST: that SSH destination
     (HERDR_WINDOW_HOST=local forces this machine).
  2. A herdr-app window socket on this machine: run herdr-app here.
  3. Exactly one Herdr core connected in over SSH (the window's machine
     dialed this one): run herdr-app there over SSH.

Extra commands:
  route               print the route as JSON, without touching the window
  here                this terminal's terminal/pane/tab/space IDs and machine
                      name, as the window names them
  shot [file.png]     the window's last frame, copied to this machine;
                      prints the local path

Everything else (ls, status, commands, do ..., --skill, --version, check,
feedback) goes to herdr-app unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import NoReturn, Optional

# Remote side: herdr-app on PATH, else where the macOS app links it.
REMOTE_APP = 'p=$(command -v herdr-app 2>/dev/null || printf %s "$HOME/.local/bin/herdr-app"); '
SSH = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]


def die(message: str, code: int = 1) -> NoReturn:
    print(f"herdr-win: {message}", file=sys.stderr)
    sys.exit(code)


def app_home() -> Path:
    home = os.environ.get("HERDR_APP_HOME")
    if home:
        return Path(home)
    config = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(config) / "herdr-app"


def local_app() -> Optional[str]:
    found = shutil.which("herdr-app")
    if found:
        return found
    linked = Path.home() / ".local/bin/herdr-app"
    return str(linked) if linked.exists() else None


def is_socket(path: Path) -> bool:
    try:
        return stat.S_ISSOCK(path.stat().st_mode)
    except OSError:
        return False


def inbound_hosts() -> list[str]:
    """Client IPs of `herdr-core connect` / `hc connect` sessions that came in over SSH."""
    proc = Path("/proc")
    if not proc.is_dir():
        return []
    uid = os.getuid()
    hosts: set[str] = set()
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != uid:
                continue
            argv = (entry / "cmdline").read_bytes().split(b"\0")
            if len(argv) < 2 or Path(argv[0].decode()).name not in ("herdr-core", "hc") or argv[1] != b"connect":
                continue
            env = (entry / "environ").read_bytes().split(b"\0")
        except OSError:
            continue
        for var in env:
            if var.startswith((b"SSH_CONNECTION=", b"SSH_CLIENT=")):
                hosts.add(var.split(b"=", 1)[1].split()[0].decode())
                break
    return sorted(hosts)


def route(host: Optional[str]) -> dict:
    host = host or os.environ.get("HERDR_WINDOW_HOST") or None
    if host == "local":
        return {"via": "local", "reason": "HERDR_WINDOW_HOST=local"}
    if host:
        return {"via": "ssh", "host": host, "reason": "--host or HERDR_WINDOW_HOST"}
    sock = app_home() / "herdr-app.sock"
    if local_app() and is_socket(sock):
        return {"via": "local", "reason": f"window socket {sock}"}
    hosts = inbound_hosts()
    if len(hosts) == 1:
        return {"via": "ssh", "host": hosts[0], "reason": "the only Herdr core connected to this machine over SSH"}
    if hosts:
        die(f"Herdr cores from several machines are connected ({', '.join(hosts)}); "
            "set HERDR_WINDOW_HOST to the SSH destination of the one showing the window")
    die("no Herdr window here and no Herdr core connected to this machine over SSH; "
        "set HERDR_WINDOW_HOST to the SSH destination of the machine showing the window")


def remote_command(args: list[str]) -> str:
    return REMOTE_APP + 'exec "$p" ' + " ".join(shlex.quote(a) for a in args)


def ssh_failed(host: str) -> NoReturn:
    die(f"ssh to {host} failed (exit 255). This machine needs key-based SSH to the window's machine; "
        "set HERDR_WINDOW_HOST to a destination that works, such as user@host", 255)


def run_app(r: dict, args: list[str]) -> NoReturn:
    if r["via"] == "local":
        exe = local_app()
        if not exe:
            die("herdr-app is not installed on this machine")
        os.execv(exe, [exe, *args])
    code = subprocess.call([*SSH, r["host"], remote_command(args)])
    if code == 255:
        ssh_failed(r["host"])
    sys.exit(code)


def capture_app(r: dict, args: list[str]) -> str:
    if r["via"] == "local":
        exe = local_app() or die("herdr-app is not installed on this machine")
        cmd = [exe, *args]
    else:
        cmd = [*SSH, r["host"], remote_command(args)]
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode == 255 and r["via"] == "ssh":
        ssh_failed(r["host"])
    if done.returncode != 0:
        die(f"herdr-app {' '.join(args)} failed: {(done.stdout + done.stderr).strip()}", done.returncode)
    return done.stdout


def here(r: dict) -> None:
    terminal = os.environ.get("HC_TERMINAL_ID")
    if not terminal:
        die("HC_TERMINAL_ID is unset: this process is not in a herdr-core terminal")
    hc = shutil.which("hc") or shutil.which("herdr-core") or die("hc is not on PATH")
    got = subprocess.run([hc, "get", terminal, "--json"], capture_output=True, text=True)
    if got.returncode != 0:
        die(f"hc get {terminal} failed: {got.stderr.strip()}")
    labels = json.loads(got.stdout).get("labels") or {}
    space_id = labels.get("herdr.space")
    if not space_id:
        die(f"terminal {terminal} has no herdr.space label: the window does not show it")

    def same(window_id: Optional[str], local_id: str) -> bool:
        return bool(window_id) and (window_id == local_id or window_id.endswith("/" + local_id))

    for space in json.loads(capture_app(r, ["ls"])).get("spaces", []):
        if not same(space.get("id"), space_id):
            continue
        for tab in space.get("tabs", []):
            for term in tab.get("terminals", []):
                if same(term.get("terminal"), terminal):
                    print(json.dumps({
                        "terminal": term["terminal"],
                        "pane": term.get("pane"),
                        "tab": tab["id"],
                        "space": space["id"],
                        "machine": space.get("machine"),
                        "window": r,
                    }, indent=2))
                    return
    die(f"the window does not list terminal {terminal} (space {space_id})")


def shot(r: dict, rest: list[str]) -> None:
    if len(rest) > 1:
        die("usage: shot [file.png]", 2)
    target = Path(rest[0] if rest else "herdr-shot.png").expanduser().absolute()
    if target.suffix.lower() != ".png":
        die("screenshot path must end in .png", 2)
    if r["via"] == "local":
        run_app(r, ["shot", str(target)])
    script = ('d=$(mktemp -d) || exit 1; ' + REMOTE_APP +
              '"$p" shot "$d/shot.png" >&2 && cat "$d/shot.png"; rc=$?; rm -rf "$d"; exit $rc')
    done = subprocess.run([*SSH, r["host"], script], capture_output=True)
    if done.returncode == 255:
        ssh_failed(r["host"])
    if done.returncode != 0 or not done.stdout.startswith(b"\x89PNG"):
        die(f"shot failed on {r['host']}: {done.stderr.decode(errors='replace').strip()}", done.returncode or 1)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(done.stdout)
    print(target)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="herdr-win.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n  herdr-win.py here\n  herdr-win.py do tab.new --space server/sp1 --name logs\n"
               "  HERDR_WINDOW_HOST=me@laptop herdr-win.py status",
    )
    parser.add_argument("--host", help="SSH destination of the machine showing the window, or 'local'")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="herdr-app arguments, or route | here | shot")
    ns, extra = parser.parse_known_args()
    args = extra + ns.command
    if not args:
        parser.print_help()
        sys.exit(2)
    r = route(ns.host)
    if args[0] == "route":
        print(json.dumps(r, indent=2))
    elif args[0] == "here":
        here(r)
    elif args[0] == "shot":
        shot(r, args[1:])
    else:
        run_app(r, args)


if __name__ == "__main__":
    main()
