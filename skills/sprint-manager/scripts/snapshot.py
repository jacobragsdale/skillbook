#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Print one JSON snapshot of Jacob's sprint for the sprint-manager skill.

Joins three live sources. Any of them may fail without stopping the rest;
"sources" names each one's error.
  herdr      every pane except this one: workspace/tab, folder, agent, status
  git        each pane folder's repo, branch, default branch, uncommitted files
  agent-cli  @me's work items in the current sprint with their PR, branch and
             blocker links, and @me's PRs opened in the last --days

A ticket links to work by any evidence: an ADO link from either side, its id
in a PR's source branch or title, or its id in a tab's branch or folder name.
None of these is required, and a missing one is not an error.

Keys, in order:
  now          local time and weekday
  sources      "ok" or the error, per source
  sprint       name, start, finish, working_days_left (null if unavailable)
  mine         @me's sprint tickets counted by state
  tabs         panes with an agent, a git repo, or a ticket id in the folder;
               "free" is true when the folder can take a new ticket, "why"
               says why or why not, "screen" is the agent's last lines when it
               is blocked, done, or idle on unfinished work
  tickets      @me's open tickets (not Closed, Removed or Done), by priority
  other_prs    @me's active PRs tied to no ticket in the sprint
  conventions  the conventions file's text, or null when it does not exist
Ticket flags: new_with_work, pr_not_linked:<pr>, all_prs_merged,
no_evidence, blocker_closed:<id>.

Lists print one entry per line. Stdlib only, so it runs where no package
index is reachable. Exit codes: 0 printed (failed sources are listed, not
fatal), 2 bad arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar
from urllib.parse import unquote

CONVENTIONS = Path("~/.config/sprint-manager/conventions.md")
DONE_STATES = frozenset({"Closed", "Removed", "Done"})
STATE_ORDER = {"Active": 0, "New": 1, "Resolved": 2}
AGENT_BUSY = {
    "working": "agent is working",
    "blocked": "agent is blocked on a question or approval",
    "done": "agent finished a turn you have not seen",
    "unknown": "agent state unknown",
}
# A ticket id is 3-7 digits not glued to letters, digits or dots, so
# 48201-fix, feature/48201 and AB#48201 match while v1.4.2 and 2026.10 don't.
ID_RE = re.compile(r"(?<![A-Za-z0-9.])\d{3,7}(?![A-Za-z0-9.])")
# Terminal chrome in an agent's screen: rules, box edges, an empty prompt.
CHROME = re.compile(r"[\s─━│┃╌┄┈═┌┐└┘├┤┬┴┼╭╮╯╰❯>·]*")
WORKERS = 8
T = TypeVar("T")


class SourceError(Exception):
    """A source failed, or answered in a shape this script does not know."""


@dataclass(frozen=True)
class Pane:
    pane: str
    where: str
    cwd: str
    agent: str | None
    status: str | None
    title: str


@dataclass(frozen=True)
class Git:
    repo: str
    branch: str
    default: str
    dirty: int


@dataclass(frozen=True)
class Item:
    id: int
    type: str
    title: str
    state: str
    priority: int | None
    tags: tuple[str, ...]
    changed: datetime
    rev: int


@dataclass(frozen=True)
class Links:
    prs: frozenset[int]
    branches: tuple[str, ...]
    blocked_by: tuple[int, ...]


@dataclass(frozen=True)
class PR:
    id: int
    repo: str
    title: str
    status: str
    source: str
    draft: bool
    votes: tuple[tuple[str, str], ...]
    open_threads: int | None
    work_items: frozenset[int]


# --- I/O boundary: commands and the JSON they print -------------------------


def run(cmd: list[str], timeout: float = 90) -> str:
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        msg = f"{cmd[0]} is not on PATH"
        raise SourceError(msg) from exc
    except subprocess.TimeoutExpired as exc:
        msg = f"{' '.join(cmd[:4])} timed out after {timeout:.0f}s"
        raise SourceError(msg) from exc
    if done.returncode != 0:
        lines = (done.stderr.strip() or done.stdout.strip()).splitlines()
        msg = f"{' '.join(cmd[:4])} exited {done.returncode}: {lines[0] if lines else 'no output'}"
        raise SourceError(msg)
    return done.stdout


def load(raw: str, what: str) -> object:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"{what} printed something other than JSON"
        raise SourceError(msg) from exc


def as_dict(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        msg = f"{what}: expected a JSON object"
        raise SourceError(msg)
    return {str(key): val for key, val in value.items()}


def as_list(value: object, what: str) -> list[object]:
    # agent-cli drops empty fields, so a missing list is an empty one.
    if value is None:
        return []
    if not isinstance(value, list):
        msg = f"{what}: expected a JSON list"
        raise SourceError(msg)
    return list(value)


def text(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        msg = f"{key}: expected text, got {type(value).__name__}"
        raise SourceError(msg)
    return value


def number(row: dict[str, object], key: str) -> int | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"{key}: expected a whole number, got {type(value).__name__}"
        raise SourceError(msg)
    return value


def ids(values: list[object], what: str) -> list[int]:
    found: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            msg = f"{what}: expected ids"
            raise SourceError(msg)
        found.append(value)
    return found


def acli(*args: str) -> object:
    return load(run(["agent-cli", *args]), f"agent-cli {' '.join(args[:3])}")


def herdr(*args: str) -> dict[str, object]:
    reply = as_dict(load(run(["herdr", *args], timeout=15), f"herdr {args[0]}"), "herdr")
    return as_dict(reply.get("result"), f"herdr {' '.join(args)}")


def read_panes(own_pane: str) -> list[Pane]:
    spaces = {text(w, "workspace_id"): text(w, "label") for w in (as_dict(v, "workspace") for v in as_list(herdr("workspace", "list").get("workspaces"), "workspaces"))}
    tabs = {text(t, "tab_id"): text(t, "label") for t in (as_dict(v, "tab") for v in as_list(herdr("tab", "list").get("tabs"), "tabs"))}
    panes: list[Pane] = []
    for value in as_list(herdr("pane", "list").get("panes"), "panes"):
        row = as_dict(value, "pane")
        pane_id = text(row, "pane_id")
        if pane_id == own_pane:
            continue
        cwd = text(row, "foreground_cwd") or text(row, "cwd")
        agent = text(row, "agent") or None
        tab = tabs.get(text(row, "tab_id"), "")
        # Unnamed tabs are numbered; the folder says more than "2".
        if not tab or tab.isdigit():
            tab = Path(cwd).name
        panes.append(
            Pane(
                pane=pane_id,
                where=f"{spaces.get(text(row, 'workspace_id'), '?')}/{tab}",
                cwd=cwd,
                agent=agent,
                # herdr reports a plain shell as "unknown"; only an agent has a status.
                status=text(row, "agent_status") or None if agent else None,
                title=text(row, "terminal_title_stripped"),
            )
        )
    return panes


def screen(pane: str, keep: int = 12) -> list[str]:
    # A blocked agent's history can't be scrolled, only its visible screen read.
    try:
        out = run(["herdr", "agent", "read", pane, "--source", "recent-unwrapped", "--lines", "60"], timeout=15)
    except SourceError:
        try:
            out = run(["herdr", "agent", "read", pane, "--source", "visible"], timeout=15)
        except SourceError:
            return []
    lines = [line.strip()[:200] for line in out.splitlines() if not CHROME.fullmatch(line)]
    return lines[-keep:]


def git(cwd: str, *args: str) -> str:
    return run(["git", "-C", cwd, *args], timeout=15).strip()


def read_git(cwd: str) -> Git | None:
    try:
        root = git(cwd, "rev-parse", "--show-toplevel")
    except SourceError:
        return None
    branch = git(cwd, "branch", "--show-current")
    dirty = len(git(cwd, "status", "--porcelain").splitlines())
    try:
        remote = git(cwd, "remote", "get-url", "origin")
    except SourceError:
        remote = ""
    repo = unquote(remote.rstrip("/").removesuffix(".git").rsplit("/", 1)[-1].rsplit(":", 1)[-1]) or Path(root).name
    try:
        default = git(cwd, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").removeprefix("origin/")
    except SourceError:
        local = git(cwd, "branch", "--list", "main", "master", "--format=%(refname:short)").split()
        default = local[0] if local else "main"
    return Git(repo=repo, branch=branch, default=default, dirty=dirty)


def parse_time(raw: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError as exc:
        msg = f"unreadable time {raw!r}"
        raise SourceError(msg) from exc
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)


def read_items() -> list[Item]:
    rows = as_list(acli("ado", "workitem", "list", "--assignee", "@me", "--iteration", "@current", "--limit", "500", "--fields", "id,type,title,state,priority,tags,changed,rev"), "work items")
    items: list[Item] = []
    for value in rows:
        row = as_dict(value, "work item")
        item_id = number(row, "id")
        if item_id is None:
            msg = "work item without an id"
            raise SourceError(msg)
        tags = tuple(str(tag) for tag in as_list(row.get("tags"), "tags"))
        items.append(Item(item_id, text(row, "type"), text(row, "title"), text(row, "state"), number(row, "priority"), tags, parse_time(text(row, "changed")), number(row, "rev") or 0))
    return items


def read_links(item_id: int) -> Links:
    row = as_dict(acli("ado", "workitem", "get", str(item_id), "--fields", "pull_requests,branches,blocked_by"), "work item links")
    prs = frozenset(number(as_dict(pr, "pull request link"), "id") or 0 for pr in as_list(row.get("pull_requests"), "pull_requests"))
    branches = tuple(f"{text(b, 'repo')}:{text(b, 'name')}" for b in (as_dict(v, "branch link") for v in as_list(row.get("branches"), "branches")))
    return Links(prs - {0}, branches, tuple(ids(as_list(row.get("blocked_by"), "blocked_by"), "blocked_by")))


def parse_pr(value: object) -> PR:
    row = as_dict(value, "pull request")
    pr_id = number(row, "id")
    if pr_id is None:
        msg = "pull request without an id"
        raise SourceError(msg)
    votes = tuple((text(r, "name"), text(r, "vote")) for r in (as_dict(v, "reviewer") for v in as_list(row.get("reviewers"), "reviewers")))
    return PR(
        id=pr_id,
        repo=text(row, "repo"),
        title=text(row, "title"),
        status=text(row, "status"),
        source=text(row, "source").removeprefix("refs/heads/"),
        draft=row.get("is_draft") is True,
        votes=votes,
        open_threads=number(row, "open_threads"),
        work_items=frozenset(ids(as_list(row.get("work_items"), "work_items"), "work_items")),
    )


def read_my_prs(days: int) -> list[PR]:
    rows = acli("ado", "pr", "list", "--author", "@me", "--status", "all", "--since", f"{days}d", "--limit", "200", "--fields", "id,repo,title,status,source,is_draft,reviewers")
    return [parse_pr(value) for value in as_list(rows, "pull requests")]


def read_pr(pr_id: int) -> PR:
    return parse_pr(acli("ado", "pr", "get", str(pr_id), "--fields", "id,repo,title,status,source,is_draft,reviewers,open_threads,work_items"))


def read_state(item_id: int) -> str:
    return text(as_dict(acli("ado", "workitem", "get", str(item_id), "--fields", "state"), "blocker"), "state")


def read_sprint() -> dict[str, object]:
    return as_dict(acli("ado", "sprint", "get", "@current", "--fields", "name,start,finish,working_days_left"), "sprint")


# --- Linking: pure, so --self-check can hold it ------------------------------


def ids_in(*texts: str) -> list[int]:
    return [int(match) for value in texts for match in ID_RE.findall(value)]


def pr_ticket_ids(pr: PR) -> set[int]:
    return set(ids_in(pr.source, pr.title)) | pr.work_items


def tab_state(status: str | None, repo: Git | None, ticket_state: str | None, branch_prs: list[PR]) -> tuple[bool, str]:
    """Whether a folder can take a new ticket. Jacob waits on PRs instead of switching branches."""
    if status in AGENT_BUSY:
        return False, AGENT_BUSY[status]
    if repo is None:
        return False, "not a git repo (analysis or scratch folder)"
    if repo.dirty:
        return False, f"{repo.dirty} uncommitted file{'s' if repo.dirty != 1 else ''}"
    active = [pr for pr in branch_prs if pr.status == "active"]
    if active:
        return False, f"PR {active[0].id} is open on this branch: waiting on review"
    if not repo.branch:
        return False, "detached HEAD"
    if repo.branch == repo.default:
        return True, f"on {repo.default}, clean"
    if branch_prs:
        return True, f"this branch's PRs are done: switch to {repo.default} first"
    if ticket_state in DONE_STATES:
        return True, f"this branch's ticket is {ticket_state}: switch to {repo.default} first"
    return False, "work in progress on this branch, no PR yet"


def compact(row: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in row.items() if value not in (None, "", [], {}, ())}


def pr_view(pr: PR, linked: bool | None = None) -> dict[str, object]:
    return compact(
        {
            "id": pr.id,
            "repo": pr.repo,
            "status": pr.status + (" draft" if pr.draft else ""),
            "linked": linked,
            "source": pr.source,
            "votes": dict(pr.votes),
            "open_threads": pr.open_threads if pr.status == "active" else None,
        }
    )


def build(
    items: list[Item],
    links: Mapping[int, Links],
    prs: Mapping[int, PR],
    panes: list[Pane],
    gits: Mapping[str, Git | None],
    blockers: Mapping[int, str],
    screens: Mapping[str, list[str]],
    now: datetime,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """Join tickets, PRs and panes. Returns (tabs, tickets, other_prs)."""
    by_id = {item.id: item for item in items}
    # A branch linked in ADO ties a tab to its ticket even when the name has no id.
    linked_branches = {branch: item_id for item_id, link in links.items() for branch in link.branches}
    agents_per_folder = Counter(pane.cwd for pane in panes if pane.agent)

    tabs: list[dict[str, object]] = []
    tab_tickets: dict[int, list[str]] = {}
    for pane in panes:
        repo = gits.get(pane.cwd)
        found = ids_in(repo.branch if repo else "", Path(pane.cwd).name)
        if not (pane.agent or repo or found):
            continue
        ticket = next((i for i in found if i in by_id), None) or (linked_branches.get(f"{repo.repo}:{repo.branch}") if repo else None)
        branch_prs = [pr for pr in prs.values() if repo and pr.repo == repo.repo and pr.source == repo.branch and repo.branch != repo.default]
        free, why = tab_state(pane.status, repo, by_id[ticket].state if ticket else None, branch_prs)
        if ticket:
            tab_tickets.setdefault(ticket, []).append(pane.where)
        tabs.append(
            compact(
                {
                    "where": pane.where,
                    "pane": pane.pane,
                    "folder": pane.cwd.replace(str(Path.home()), "~", 1),
                    "repo": repo.repo if repo else None,
                    "branch": repo.branch if repo else None,
                    "agent": f"{pane.agent} {pane.status}" if pane.agent else None,
                    "title": pane.title if pane.agent else None,
                    "ticket": ticket,
                    "other_ids": [i for i in found if i not in by_id],
                    "prs": [pr.id for pr in branch_prs],
                    "free": free,
                    "why": why,
                    "warning": f"{agents_per_folder[pane.cwd]} agents share this folder" if agents_per_folder[pane.cwd] > 1 else None,
                    # An idle agent on unfinished work may be waiting on a question.
                    "screen": screens.get(pane.pane) if pane.status in {"blocked", "done"} or not free else None,
                }
            )
        )

    tickets: list[dict[str, object]] = []
    claimed: set[int] = set()
    open_items = sorted((i for i in items if i.state not in DONE_STATES), key=lambda i: (i.priority or 9, STATE_ORDER.get(i.state, 3), i.id))
    for item in open_items:
        link = links.get(item.id, Links(frozenset(), (), ()))
        mine = [pr for pr in prs.values() if item.id in pr_ticket_ids(pr) or pr.id in link.prs]
        claimed.update(pr.id for pr in mine)
        flags: list[str] = []
        evidence = bool(mine or link.branches or tab_tickets.get(item.id))
        if item.state == "New" and evidence:
            flags.append("new_with_work")
        flags.extend(f"pr_not_linked:{pr.id}" for pr in mine if pr.id not in link.prs and item.id not in pr.work_items)
        if mine and all(pr.status != "active" for pr in mine) and any(pr.status == "completed" for pr in mine):
            flags.append("all_prs_merged")
        if item.state != "New" and not evidence:
            flags.append("no_evidence")
        flags.extend(f"blocker_closed:{b}" for b in link.blocked_by if blockers.get(b) in DONE_STATES)
        tickets.append(
            compact(
                {
                    "id": item.id,
                    "type": item.type,
                    "title": item.title,
                    "state": item.state,
                    "priority": item.priority,
                    "tags": list(item.tags),
                    "rev": item.rev,
                    "changed_days_ago": (now - item.changed).days,
                    "prs": [pr_view(pr, pr.id in link.prs or item.id in pr.work_items) for pr in mine],
                    "tabs": tab_tickets.get(item.id),
                    "ado_branches": list(link.branches),
                    "blocked_by": [{"id": b, "state": blockers.get(b, "?")} for b in link.blocked_by],
                    "flags": flags,
                }
            )
        )

    sprint_ids = set(by_id)
    other = [pr_view(pr) | {"title": pr.title} for pr in prs.values() if pr.status == "active" and pr.id not in claimed and not pr_ticket_ids(pr) & sprint_ids]
    return tabs, tickets, other


# --- Orchestration ------------------------------------------------------------


def attempt(sources: dict[str, str], name: str, fallback: T, call: Callable[[], T]) -> T:
    """Run a source call; on SourceError record the error under name and return fallback."""
    try:
        result = call()
    except SourceError as exc:
        sources[name] = str(exc)
        return fallback
    sources.setdefault(name, "ok")
    return result


def snapshot(days: int, conventions: Path, own_pane: str, now: datetime) -> dict[str, object]:
    sources: dict[str, str] = {}
    with ThreadPoolExecutor(WORKERS) as pool:
        f_panes = pool.submit(read_panes, own_pane)
        f_items = pool.submit(read_items)
        f_prs = pool.submit(read_my_prs, days)
        f_sprint = pool.submit(read_sprint)
        panes: list[Pane] = attempt(sources, "herdr", [], f_panes.result)
        items: list[Item] = attempt(sources, "ado work items", [], f_items.result)
        my_prs: list[PR] = attempt(sources, "ado pull requests", [], f_prs.result)
        sprint: dict[str, object] | None = attempt(sources, "ado sprint", None, f_sprint.result)

        open_items = [i for i in items if i.state not in DONE_STATES]
        folders = sorted({p.cwd for p in panes})
        f_gits = {cwd: pool.submit(read_git, cwd) for cwd in folders}
        f_links = {i.id: pool.submit(read_links, i.id) for i in open_items}
        f_screens = {p.pane: pool.submit(screen, p.pane) for p in panes if p.status in {"blocked", "done", "idle"}}
        gits: dict[str, Git | None] = {cwd: attempt(sources, "git", None, f.result) for cwd, f in f_gits.items()}
        links = {item_id: attempt(sources, "ado links", Links(frozenset(), (), ()), f.result) for item_id, f in f_links.items()}
        screens = {pane: f.result() for pane, f in f_screens.items()}

        # Fetch in full every PR that may touch an open ticket, plus every active one.
        open_ids = {i.id for i in open_items}
        wanted = {pr.id for pr in my_prs if pr.status == "active" or pr_ticket_ids(pr) & open_ids}
        wanted |= {pr_id for link in links.values() for pr_id in link.prs}
        blocker_ids = {b for link in links.values() for b in link.blocked_by}
        f_full = {pr_id: pool.submit(read_pr, pr_id) for pr_id in wanted}
        f_blockers = {b: pool.submit(read_state, b) for b in blocker_ids}
        prs = {pr.id: pr for pr in my_prs}
        for pr_id, f in f_full.items():
            full = attempt(sources, "ado pull requests", None, f.result)
            if full:
                prs[pr_id] = full
        blockers = {b: attempt(sources, "ado links", "?", f.result) for b, f in f_blockers.items()}

    tabs, tickets, other_prs = build(items, links, prs, panes, gits, blockers, screens, now)
    path = conventions.expanduser()
    return {
        "now": now.astimezone().strftime("%Y-%m-%d %H:%M %a"),
        "sources": sources,
        "sprint": sprint,
        "mine": dict(Counter(item.state for item in items)),
        "tabs": tabs,
        "tickets": tickets,
        "other_prs": other_prs,
        "conventions": path.read_text(encoding="utf-8") if path.is_file() else None,
    }


def emit(data: dict[str, object]) -> str:
    """Valid JSON with each list entry on its own line: readable, and few tokens."""

    def one(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    parts = []
    for key, value in data.items():
        if isinstance(value, list) and value:
            parts.append(f"{one(key)}:[\n  " + ",\n  ".join(one(v) for v in value) + "]")
        else:
            parts.append(f"{one(key)}:{one(value)}")
    return "{" + ",\n".join(parts) + "}\n"


def self_check() -> None:
    assert ids_in("48201-fix-retry", "feature/48202", "AB#48203 v1.4.2 release/2026.10") == [48201, 48202, 48203]
    now = datetime(2026, 10, 7, 12, tzinfo=UTC)
    items = [
        Item(100, "Task", "started", "New", 2, (), now, 1),
        Item(101, "Bug", "merged", "Active", 1, ("blocked",), now, 4),
        Item(102, "Task", "forgotten", "Active", 3, (), datetime(2026, 9, 27, tzinfo=UTC), 2),
        Item(103, "Task", "done", "Closed", 2, (), now, 9),
    ]
    links = {100: Links(frozenset(), (), ()), 101: Links(frozenset({7}), (), (900,)), 102: Links(frozenset(), ("lab:spike-x",), ())}
    prs = {
        7: PR(7, "api", "Fix it", "completed", "101-fix", False, (), None, frozenset({101})),
        8: PR(8, "api", "Start it", "active", "100-start", False, (("Sam", "waiting"),), 2, frozenset()),
        9: PR(9, "web", "Spike", "active", "spike", False, (), 0, frozenset()),
    }
    panes = [
        Pane("w1:p1", "plat/api", "/r/api", "claude", "idle", "x"),
        Pane("w1:p2", "plat/web", "/r/web", None, None, ""),
        Pane("w1:p3", "plat/old", "/r/old", "claude", "blocked", "y"),
        Pane("w1:p4", "plat/lab", "/r/lab", "claude", "idle", "z"),
    ]
    gits = {"/r/api": Git("api", "100-start", "main", 0), "/r/web": Git("web", "main", "main", 0), "/r/old": Git("old", "103-done", "main", 0), "/r/lab": Git("lab", "spike-x", "main", 0)}
    tabs, tickets, other = build(items, links, prs, panes, gits, {900: "Closed"}, {}, now)
    by_where = {t["where"]: t for t in tabs}
    assert by_where["plat/api"]["free"] is False and "PR 8" in str(by_where["plat/api"]["why"])
    assert by_where["plat/web"]["free"] is True
    assert by_where["plat/old"]["free"] is False and "blocked" in str(by_where["plat/old"]["why"])
    flags = {t["id"]: t.get("flags", []) for t in tickets}
    assert flags[100] == ["new_with_work", "pr_not_linked:8"], flags[100]
    assert flags[101] == ["all_prs_merged", "blocker_closed:900"], flags[101]
    assert by_where["plat/lab"]["ticket"] == 102 and flags[102] == [], flags[102]
    assert 103 not in flags and [t["id"] for t in tickets] == [101, 100, 102]
    assert [p["id"] for p in other] == [9]
    assert tab_state(None, Git("api", "101-fix", "main", 0), "Active", [prs[7]]) == (True, "this branch's PRs are done: switch to main first")
    sys.stdout.write("self-check passed\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=30, help="how far back to look for your PRs (default 30)")
    parser.add_argument("--conventions", type=Path, default=CONVENTIONS, help=f"conventions file (default {CONVENTIONS})")
    parser.add_argument("--self-check", action="store_true", help="run the offline linking checks and exit")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if args.days < 1:
        parser.error("--days must be at least 1")
    # Absence is meaningful: outside herdr there is no pane of our own to skip.
    own_pane = os.environ.get("HERDR_PANE_ID", "")
    sys.stdout.write(emit(snapshot(args.days, args.conventions, own_pane, datetime.now(UTC))))


if __name__ == "__main__":
    main()
