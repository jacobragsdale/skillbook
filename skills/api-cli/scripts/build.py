#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.3,<7"]
# ///
"""Build an agent-first CLI package from OpenAPI 2/3 and AsyncAPI 2/3 specs.

Writes a uv project: src/<pkg>/cli.py (the runtime, copied from the skill's
assets/cli.py.tmpl), src/<pkg>/commands.json (the compiled catalogue), smoke tests,
README, and house tooling config. Run it again with the same --out to pick up
spec or runtime changes; --rebuild DIR repeats the recorded build.

Examples:
  build.py https://api.example.com/openapi.json --name example-api
  build.py openapi.json asyncapi.yaml --name exchange --base-url http://127.0.0.1:3910
  build.py sonarr=sonarr.json radarr=radarr.json --name arr   # one namespace per spec
  build.py --rebuild ~/dev/example-api
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import yaml

type JSON = str | int | float | bool | list[JSON] | dict[str, JSON] | None
type Node = dict[str, JSON]

SKILL = Path(__file__).resolve().parent.parent
METHODS = ("get", "post", "put", "patch", "delete", "head")
RESERVED = {"help", "h", "fields", "paginate", "dry-run", "raw", "input", "output", "yes"}
PAGE_PARAMS = {"page", "per_page", "per-page", "page_size", "pagesize", "limit", "offset", "cursor", "page_token", "pagetoken", "after", "starting_after", "skip"}
MANIFEST = ".api-cli.json"


class BuildError(Exception):
    """A problem with the inputs that the caller must fix."""


class Body(NamedTuple):
    type: str
    schema: JSON
    required: bool


@dataclass
class Channel:
    address: str
    spec: Node
    send: list[Node] = field(default_factory=list)
    recv: list[Node] = field(default_factory=list)
    summary: str = ""


def d(value: JSON) -> Node:
    return value if isinstance(value, dict) else {}


def lst(value: JSON) -> list[JSON]:
    return value if isinstance(value, list) else []


def s(value: JSON) -> str:
    return value if isinstance(value, str) else ""


def load(src: str) -> Node:
    if src.startswith(("http://", "https://")):
        request = urllib.request.Request(src, headers={"User-Agent": "api-cli-build"})
        with urllib.request.urlopen(request, timeout=60) as resp:
            raw: bytes = resp.read()
        text = raw.decode()
    else:
        text = Path(src).expanduser().read_text(encoding="utf-8")
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    doc: JSON = json.loads(text) if text.lstrip().startswith("{") else yaml.load(text, Loader=loader)
    if not isinstance(doc, dict) or not ({"openapi", "swagger", "asyncapi"} & doc.keys()):
        msg = f"{src}: not an OpenAPI, Swagger, or AsyncAPI document"
        raise BuildError(msg)
    return doc


def words(text: str) -> list[str]:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    return [w.lower() for w in re.split(r"[^A-Za-z0-9]+", text) if w]


def kebab(text: str) -> str:
    return "-".join(words(text))


def singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def sentence(text: JSON, limit: int = 160) -> str:
    """First sentence of markdown/HTML text with links and markup removed."""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s(text))
    t = re.sub(r"<[^>]+>", "", t)
    t = " ".join(re.sub(r"[`*>]|\[!\w+\]", "", t).split())
    if m := re.match(r"(.+?[.!?])(\s|$)", t):
        first: str = m.group(1)
        t = first
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


class Doc:
    """A spec document with lazy, cycle-safe local $ref resolution."""

    def __init__(self, root: Node) -> None:
        self.root = root
        self.swagger2 = s(root.get("swagger")).startswith("2")

    def get(self, node: JSON) -> Node:
        seen: set[str] = set()
        while isinstance(node, dict) and isinstance(ref := node.get("$ref"), str):
            if not ref.startswith("#"):
                msg = f"external $ref {ref!r}: bundle the spec into one file first, e.g. `npx @redocly/cli bundle SPEC -o bundled.json`"
                raise BuildError(msg)
            if ref in seen:
                return {}
            seen.add(ref)
            node = self.root
            for part in ref[2:].split("/") if len(ref) > 2 else []:
                node = d(node).get(urllib.parse.unquote(part).replace("~1", "/").replace("~0", "~"))
        return d(node)

    def flat(self, schema: JSON, depth: int = 0) -> Node:
        """The schema with allOf merged and nullable or single-variant oneOf/anyOf unwrapped."""
        sch = self.get(schema)
        if depth > 8:
            return sch
        if "allOf" in sch:
            merged: Node = {k: v for k, v in sch.items() if k != "allOf"}
            props = dict(d(merged.get("properties")))
            required = list(lst(merged.get("required")))
            for part in lst(sch["allOf"]):
                sub = self.flat(part, depth + 1)
                props.update(d(sub.get("properties")))
                required += lst(sub.get("required"))
                for key in ("type", "items", "enum", "description", "format"):
                    if key in sub and key not in merged:
                        merged[key] = sub[key]
            if props:
                merged["properties"] = props
            merged["required"] = required
            return merged
        for key in ("oneOf", "anyOf"):
            if key in sch and "properties" not in sch:
                rest = {k: v for k, v in sch.items() if k != key}
                real = [v for v in (self.flat(x, depth + 1) for x in lst(sch[key])) if v.get("type") != "null"]
                if len(real) == 1:
                    return rest | real[0]
                if real and all("properties" in v for v in real):
                    union: Node = {}
                    for v in real:
                        union.update(d(v["properties"]))
                    return rest | {"type": "object", "properties": union}
                if real and all("enum" in v for v in real):
                    return {"type": real[0].get("type", "string"), "enum": [e for v in real for e in lst(v["enum"])]}
        return sch

    def is_array(self, sch: Node) -> bool:
        return sch.get("type") == "array" or "items" in sch

    def kind(self, schema: JSON) -> Node:
        """How the CLI parses a value: kind, plus items/enum/format when they apply."""
        sch = self.flat(schema)
        t = sch.get("type")
        if isinstance(t, list):
            t = next((x for x in t if x != "null"), "string")
        if self.is_array(sch):
            inner = self.kind(sch.get("items", {}))
            if inner["kind"] in ("json", "array"):
                return {"kind": "json"}
            listed: Node = {"kind": "array", "items": inner["kind"]}
            if "enum" in inner:
                listed["enum"] = inner["enum"]
            return listed
        if t == "object" or "properties" in sch or "additionalProperties" in sch:
            return {"kind": "json"}
        if sch.get("format") == "binary" or t == "file":
            return {"kind": "file"}
        out: Node = {"kind": {"integer": "int", "number": "num", "boolean": "bool"}.get(s(t), "str")}
        if "enum" in sch:
            out["enum"] = [v for v in lst(sch["enum"]) if v is not None]
        if sch.get("format") in ("date", "date-time", "uuid", "email", "uri"):
            out["format"] = sch["format"]
        return out

    def shape(self, schema: JSON, depth: int = 0) -> str:
        """A one-line picture of a response: the fields an agent can pass to --fields."""
        sch = self.flat(schema)
        name = s(d(schema).get("$ref")).rsplit("/", 1)[-1]
        if self.is_array(sch):
            return "array of " + self.shape(sch.get("items", {}), depth + 1) if depth < 3 else "array"
        props = d(sch.get("properties"))
        if not props:
            kind = s(self.kind(sch)["kind"])
            return name or ("object" if kind == "json" else kind)
        expand = len(props) <= 6 and depth < 2
        parts = []
        for prop, sub in props.items():
            if prop.endswith("_url") and prop != "html_url":
                continue
            f = self.flat(sub)
            if self.is_array(f):
                nested = expand and bool(self.flat(f.get("items", {})).get("properties"))
                parts.append(f"{prop}[]" + (" " + self.shape(f.get("items", {}), depth + 1) if nested else ""))
            elif f.get("properties"):
                parts.append(prop + (" " + self.shape(sub, depth + 1) if expand else "{}"))
            else:
                parts.append(prop)
        more = f", …+{len(parts) - 30}" if len(parts) > 30 else ""
        return (name + " " if name else "") + "{" + ", ".join(parts[:30]) + more + "}"

    def field_names(self, schema: JSON, prefix: str = "", depth: int = 0) -> list[str]:
        """Dotted leaf paths usable with --fields (lists are mapped through), shallow first."""
        sch = self.flat(schema)
        if self.is_array(sch):
            sch = self.flat(sch.get("items", {}))
        props = d(sch.get("properties"))
        leaves: list[str] = []
        nested: list[str] = []
        for prop, sub in props.items():
            if (prop.endswith("_url") and prop != "html_url") or prop.startswith("@"):
                continue
            f = self.flat(sub)
            inner = self.flat(f.get("items", {})) if self.is_array(f) else f
            if inner.get("properties") and depth < 2 and len(props) <= 8:
                nested += self.field_names(sub, f"{prefix}{prop}.", depth + 1)
            else:
                leaves.append(prefix + prop)
        return leaves + nested


def pick_content(content: JSON) -> tuple[str | None, Node]:
    types = d(content)
    for ct in [*(c for c in types if "json" in c), "application/x-www-form-urlencoded", "multipart/form-data", *types]:
        if ct in types:
            return ct, d(types[ct])
    return None, {}


def flag_entry(doc: Doc, name: str, loc: str, schema: JSON, *, required: bool, desc: JSON) -> Node:
    entry: Node = {"name": name, "flag": kebab(name) or name.lower(), "loc": loc} | doc.kind(schema)
    if required:
        entry["required"] = True
    if text := sentence(desc, 120):
        entry["desc"] = text
    return entry


def array_separator(p: Node, swagger2: bool) -> str | None:
    if swagger2:
        return {"csv": ",", "ssv": " ", "tsv": "\t", "pipes": "|"}.get(s(p.get("collectionFormat")) or "csv")
    style = s(p.get("style")) or "form"
    return None if p.get("explode", style == "form") else {"spaceDelimited": " ", "pipeDelimited": "|"}.get(style, ",")


def param_entry(doc: Doc, p: Node) -> Node:
    loc = s(p.get("in"))
    schema = p if doc.swagger2 else (p.get("schema") or pick_content(p.get("content"))[1].get("schema") or {})
    entry = flag_entry(doc, s(p.get("name")), loc, schema, required=bool(p.get("required")) or loc == "path", desc=p.get("description") or doc.get(schema).get("description"))
    if entry["kind"] == "array" and (sep := array_separator(p, doc.swagger2)):
        entry["sep"] = sep
    default = doc.get(schema).get("default", p.get("default"))
    if default is not None and not isinstance(default, (dict, list)):
        entry["default"] = default
    return entry


def body_entries(doc: Doc, schema: JSON, loc: str) -> list[Node] | None:
    """Flag entries for top-level body properties; None when the body is not an object."""
    sch = doc.flat(schema)
    props = d(sch.get("properties"))
    if not props:
        return None
    required = set(map(s, lst(sch.get("required"))))
    return [
        flag_entry(doc, name, loc, sub, required=name in required, desc=doc.flat(sub).get("description") or doc.flat(sub).get("title"))
        for name, sub in props.items()
        if not doc.flat(sub).get("readOnly")
    ]


def split_params(doc: Doc, item: Node, op: Node, where: str, warnings: list[str]) -> tuple[list[Node], list[Node], Body | None]:
    """Path/query/header params, Swagger 2 form fields, and a Swagger 2 body param."""
    merged: dict[tuple[str, str], Node] = {}
    for raw in lst(item.get("parameters")) + lst(op.get("parameters")):
        p = doc.get(raw)
        if "name" in p:
            merged[(s(p["name"]), s(p.get("in")))] = p
    params: list[Node] = []
    form: list[Node] = []
    body: Body | None = None
    for p in merged.values():
        loc = s(p.get("in"))
        if doc.swagger2 and loc == "body":
            consumes = [s(x) for x in lst(op.get("consumes") or doc.root.get("consumes"))] or ["application/json"]
            body = Body(next((c for c in consumes if "json" in c), consumes[0]), p.get("schema", {}), bool(p.get("required")))
        elif doc.swagger2 and loc == "formData":
            form.append(flag_entry(doc, s(p["name"]), "form", p, required=bool(p.get("required")), desc=p.get("description")))
        elif loc in ("path", "query", "header"):
            params.append(param_entry(doc, p))
        else:
            warnings.append(f"{where}: {loc} parameter {s(p.get('name'))!r} is not supported")
    return params, form, body


def body_flags(doc: Doc, entry: Node, form: list[Node], body: Body | None) -> list[Node]:
    """Record the request body on the entry; return its per-field flag entries."""
    if form:
        entry["body_type"] = "multipart/form-data" if any(f["kind"] == "file" for f in form) else "application/x-www-form-urlencoded"
        return form
    if body is None:
        return []
    entry["body_type"] = body.type
    if body.required:
        entry["body_required"] = True
    fields = body_entries(doc, body.schema, "form" if "form" in body.type else "body") if ("json" in body.type or "form" in body.type) else None
    if fields is None:
        entry["raw_body"] = True
    return fields or []


def name_flags(params: list[Node], fields: list[Node]) -> None:
    """Keep every flag unique and clear of the global options."""
    taken = {s(p["flag"]) for p in params} | RESERVED
    for f in fields:
        if f["flag"] in taken:
            f["flag"] = f"body-{s(f['flag'])}"
        taken.add(s(f["flag"]))
    for p in params:
        if p["flag"] in RESERVED:
            p["flag"] = f"{s(p['loc'])}-{s(p['flag'])}"


def response_schema(doc: Doc, op: Node) -> tuple[JSON, str | None]:
    """(schema of the first 2xx response, Accept type); the schema is None for no body."""
    responses = d(op.get("responses"))
    code = next((c for c in ("200", "201", "202", "203", "206", "2XX", "2xx") if c in responses), None)
    code = code or next((c for c in responses if c.startswith("2")), None)
    if code is None or code == "204":
        return None, None
    resp = doc.get(responses[code])
    if doc.swagger2:
        produces = [s(x) for x in lst(op.get("produces") or doc.root.get("produces"))] or ["application/json"]
        return resp.get("schema"), next((c for c in produces if "json" in c), None)
    ct, media = pick_content(resp.get("content"))
    return media.get("schema"), ct


def describe(doc: Doc, entry: Node, op: Node) -> None:
    entry["summary"] = sentence(op.get("summary")) or sentence(op.get("description")) or f"{s(entry['method'])} {s(entry['path'])}"
    desc = sentence(op.get("description"), 300)
    if desc and desc != entry["summary"]:
        entry["desc"] = desc
    if op.get("deprecated"):
        entry["deprecated"] = True
    schema, accept = response_schema(doc, op)
    if accept and "json" not in accept:
        entry["returns"] = accept
    elif schema is not None:
        entry["returns"] = doc.shape(schema)
        if names := doc.field_names(schema):
            entry["fields"] = list[JSON](names[:60])
    if accept:
        entry["accept"] = accept
    entry["op_id"] = s(op.get("operationId"))


def openapi_ops(doc: Doc, api_id: str, warnings: list[str]) -> list[Node]:
    tag_desc = {s(t.get("name")): sentence(t.get("description"), 100) for t in map(d, lst(doc.root.get("tags")))}
    ops: list[Node] = []
    for path, raw_item in d(doc.root.get("paths")).items():
        item = doc.get(raw_item)
        for method in METHODS:
            op = d(item.get(method))
            if not op:
                continue
            entry: Node = {"api": api_id, "method": method.upper(), "path": path}
            params, form, body = split_params(doc, item, op, f"{method.upper()} {path}", warnings)
            if not doc.swagger2 and "requestBody" in op:
                request_body = doc.get(op["requestBody"])
                ct, media = pick_content(request_body.get("content"))
                body = Body(ct, media.get("schema", {}), bool(request_body.get("required"))) if ct else None
            fields = body_flags(doc, entry, form, body)
            name_flags(params, fields)
            entry["params"] = list[JSON](params + fields)
            if any(s(p["name"]).lower() in PAGE_PARAMS for p in params if p["loc"] == "query"):
                entry["paged"] = True
            describe(doc, entry, op)
            tag = s(next(iter(lst(op.get("tags"))), ""))
            entry["_tag"], entry["_tag_desc"] = tag, tag_desc.get(tag, "")
            ops.append(entry)
    return ops


def fallback_action(op: Node) -> str:
    path = s(op["path"]).rstrip("/")
    verb = {"GET": "get" if path.endswith("}") else "list", "POST": "create", "PUT": "put", "PATCH": "update", "DELETE": "delete", "HEAD": "head"}[s(op["method"])]
    tail = [kebab(x) for x in path.split("/") if x and not x.startswith("{")][1:]
    return "-".join([verb, *tail])


def action_words(op: Node, variants: set[str]) -> list[str]:
    op_id = s(op["op_id"])
    suffix = re.sub(r"\W", "_", s(op["path"])) + "_" + s(op["method"]).lower()
    if op_id.endswith(suffix) and len(op_id) > len(suffix):  # FastAPI's default ids end in the path and method
        op_id = op_id[: -len(suffix)]
    ns, _, rest = op_id.rpartition("/")
    return words(rest) if ns and kebab(ns) in variants else words(op_id)


def rename_clashes(members: list[Node], rename: Callable[[Node], str]) -> None:
    counts = Counter(s(op["action"]) for op in members)
    for op in members:
        if counts[s(op["action"])] > 1:
            op["action"] = rename(op)


def name_ops(ops: list[Node]) -> None:
    """Group by tag (else first path segment); action from operationId minus the group's words."""
    by_group: dict[str, list[Node]] = {}
    for op in ops:
        tag = s(op.pop("_tag"))
        segs = [x for x in s(op["path"]).split("/") if x and not x.startswith("{") and not re.fullmatch(r"v\d+(\.\d+)?|api", x)]
        op["group"] = kebab(tag) if tag else (kebab(segs[0]) if segs else "root")
        by_group.setdefault(s(op["group"]), []).append(op)
    for group, members in by_group.items():
        variants = {group, singular(group)} | set(group.split("-")) | {singular(w) for w in group.split("-")}
        for op in members:
            ws = action_words(op, variants)
            op["_full"] = "-".join(ws) or fallback_action(op)
            while len(ws) > 1 and (ws[0] in variants or (len(ws[0]) >= 3 and any(v.startswith(ws[0]) for v in variants))):
                ws = ws[1:]
            if len(ws) > 1 and (ws[-1] in variants or singular(ws[-1]) in variants):
                ws = ws[:-1]
            op["action"] = "-".join(ws) if ws and not all(w in variants for w in ws) else fallback_action(op)
        rename_clashes(members, lambda op: s(op["_full"]))
        rename_clashes(members, lambda op: f"{s(op['action'])}-{s(op['method']).lower()}")
        for op in members:
            del op["_full"]


def example_payload(doc: Doc, schema: JSON, depth: int = 0) -> JSON:
    sch = doc.flat(schema)
    for key in ("const", "example", "default"):
        if key in sch:
            return sch[key]
    for key in ("examples", "enum"):
        if lst(sch.get(key)):
            return lst(sch[key])[0]
    if doc.is_array(sch):
        return [example_payload(doc, sch.get("items", {}), depth + 1)] if depth < 3 else []
    props = d(sch.get("properties"))
    if props and depth < 3:
        required = set(map(s, lst(sch.get("required")))) or set(props)
        return {k: example_payload(doc, v, depth + 1) for k, v in props.items() if k in required}
    return {"integer": 0, "number": 0, "boolean": False}.get(s(sch.get("type")), "<value>")


def message_entry(doc: Doc, ref: JSON) -> Node:
    m = doc.get(ref)
    entry: Node = {"name": s(m.get("name")) or s(d(ref).get("$ref")).rsplit("/", 1)[-1] or "message"}
    if desc := sentence(m.get("summary") or m.get("description"), 100):
        entry["desc"] = desc
    examples = [d(x) for x in lst(m.get("examples"))]
    payload = m.get("payload")
    if examples and "payload" in examples[0]:
        entry["example"] = examples[0]["payload"]
    elif payload:
        entry["example"] = example_payload(doc, payload)
    if payload:
        entry["shape"] = doc.shape(payload)
    return entry


def channels(doc: Doc, client_view: bool) -> dict[str, Channel]:
    """Channels with the messages a client sends and receives on each."""
    v2 = s(doc.root.get("asyncapi")).startswith("2")
    found: dict[str, Channel] = {}
    for cid, raw in d(doc.root.get("channels")).items():
        ch = doc.get(raw)
        c = found[cid] = Channel(cid if v2 else s(ch.get("address")) or "/" + cid, ch)
        for key, bucket in (("publish", c.send), ("subscribe", c.recv)) if v2 else ():
            op = d(ch.get(key))
            if op:
                msg = op.get("message", {})
                bucket += [message_entry(doc, r) for r in (lst(doc.get(msg).get("oneOf")) or [msg])]
                c.summary = c.summary or sentence(op.get("summary") or op.get("description"))
    for raw in () if v2 else d(doc.root.get("operations")).values():
        op = doc.get(raw)
        c = found.get(s(d(op.get("channel")).get("$ref")).rsplit("/", 1)[-1])
        if c is None:
            continue
        # Public AsyncAPI 3 docs describe the server, so its "receive" is what a client sends.
        client_sends = (op.get("action") == "receive") != client_view
        refs = lst(op.get("messages")) or list(d(c.spec.get("messages")).values())
        (c.send if client_sends else c.recv).extend(message_entry(doc, r) for r in refs)
        if client_sends or not c.summary:
            c.summary = sentence(op.get("summary") or op.get("description")) or c.summary
    return found


def channel_params(doc: Doc, c: Channel) -> list[Node]:
    params: list[Node] = []
    for pname in re.findall(r"\{([^}]+)\}", c.address):
        pdef = doc.get(d(c.spec.get("parameters")).get(pname))
        entry: Node = {"name": pname, "flag": kebab(pname), "loc": "path", "kind": "str", "required": True}
        for key, value in (("desc", sentence(pdef.get("description"), 120)), ("enum", lst(pdef.get("enum"))), ("default", pdef.get("default"))):
            if value:
                entry[key] = value
        params.append(entry)
    binding = d(d(c.spec.get("bindings")).get("ws"))
    for loc, key in (("query", "query"), ("header", "headers")):
        sch = doc.flat(binding.get(key, {}))
        required = set(map(s, lst(sch.get("required"))))
        for pname, sub in d(sch.get("properties")).items():
            entry = flag_entry(doc, pname, loc, sub, required=pname in required, desc=doc.get(sub).get("description"))
            default = doc.get(sub).get("default")
            if default is not None and not isinstance(default, (dict, list)):
                entry["default"] = default
            params.append(entry)
    return [
        *params,
        {"name": "send", "flag": "send", "loc": "ws", "kind": "array", "items": "str", "desc": "JSON message to send after connecting (repeatable)"},
        {"name": "count", "flag": "count", "loc": "ws", "kind": "int", "default": 10, "desc": "stop after this many matching messages"},
        {"name": "timeout", "flag": "timeout", "loc": "ws", "kind": "num", "default": 10, "desc": "stop after this many seconds"},
        {"name": "match", "flag": "match", "loc": "ws", "kind": "array", "items": "str", "desc": "keep only messages where path=value, e.g. type=trade (repeatable)"},
    ]


def asyncapi_ops(doc: Doc, api_id: str, client_view: bool) -> list[Node]:
    """One `ws <channel>` command per channel."""
    ops: list[Node] = []
    for cid, c in channels(doc, client_view).items():
        entry: Node = {"api": api_id, "method": "WS", "path": c.address, "group": "ws", "action": kebab(cid), "op_id": cid}
        entry["params"] = list[JSON](channel_params(doc, c))
        entry["summary"] = sentence(c.spec.get("description")) or c.summary or f"Stream {cid}"
        desc = sentence(c.spec.get("description"), 300)
        if desc and desc != entry["summary"]:
            entry["desc"] = desc
        if c.send:
            entry["send"] = list[JSON](c.send)
        if c.recv:
            entry["recv"] = list[JSON](c.recv)
        entry["_tag_desc"] = "WebSocket streams: connect, optionally --send messages, print what arrives (one JSON per line)"
        ops.append(entry)
    return ops


def auth_for(root: Node) -> tuple[Node, str]:
    """The best-supported security scheme, and its description (it often states a token prefix)."""
    schemes = d(d(root.get("components")).get("securitySchemes")) or d(root.get("securityDefinitions"))
    ranked: list[tuple[int, Node, str]] = []
    for scheme in map(d, schemes.values()):
        t, loc, name, http = s(scheme.get("type")), s(scheme.get("in")), s(scheme.get("name")), s(scheme.get("scheme")).lower()
        desc = sentence(scheme.get("description"), 200)
        if (t == "http" and http == "bearer") or t in ("oauth2", "openIdConnect"):
            ranked.append((0, {"type": "bearer"}, desc))
        elif t == "apiKey" and loc == "header":
            ranked.append((1 if name.lower() == "authorization" else 2, {"type": "header", "name": name}, desc))
        elif t == "apiKey" and loc == "query":
            ranked.append((3, {"type": "query", "name": name}, desc))
        elif (t == "http" and http == "basic") or t == "basic":
            ranked.append((4, {"type": "basic"}, desc))
    if not ranked:
        return {"type": "none"}, ""
    _, auth, desc = min(ranked, key=lambda x: x[0])
    return auth, desc


def parse_auth(text: str) -> Node:
    kind, _, rest = text.partition(":")
    name, _, template = rest.partition(":")
    if kind not in ("none", "bearer", "header", "query", "basic") or (kind in ("header", "query") and not name):
        msg = f"--auth {text!r}: use none | bearer | basic | header:NAME[:TEMPLATE] | query:NAME"
        raise BuildError(msg)
    auth: Node = {"type": kind}
    if name:
        auth["name"] = name
    if template:
        auth["template"] = template
    return auth


def rest_base(root: Node, src: str) -> str:
    if s(root.get("swagger")).startswith("2"):
        host = s(root.get("host"))
        scheme = s(next(iter(lst(root.get("schemes"))), "https"))
        base = f"{scheme}://{host}{s(root.get('basePath'))}" if host else s(root.get("basePath"))
    else:
        server = d(next(iter(lst(root.get("servers"))), {}))
        base = s(server.get("url"))
        for var, spec in d(server.get("variables")).items():
            base = base.replace("{" + var + "}", str(d(spec).get("default", "")))
    if not base.startswith(("http://", "https://")) and src.startswith(("http://", "https://")):
        base = urllib.parse.urljoin(src, base or "/")
    return base.rstrip("/")


def ws_base(root: Node) -> str:
    server = d(next(iter(d(root.get("servers")).values()), {}))
    if not server:
        return ""
    proto = s(server.get("protocol")) or "wss"
    if "url" in server:
        url = s(server["url"])
        return (url if "://" in url else f"{proto}://{url}").rstrip("/")
    return f"{proto}://{s(server.get('host'))}{s(server.get('pathname'))}".rstrip("/")


def split_spec(spec: str) -> tuple[str, str]:
    """NAME=SPEC -> (NAME, SPEC); a bare spec has no namespace."""
    ns, eq, src = spec.partition("=")
    return (ns, src) if eq and re.fullmatch(r"[a-z][a-z0-9-]*", ns) else ("", spec)


def compile_index(args: argparse.Namespace, warnings: list[str]) -> Node:
    env = (args.env or args.name).upper().replace("-", "_")
    title = args.title or ""
    apis: Node = {}
    groups: Node = {}
    all_ops: list[Node] = []
    for spec in args.specs:
        ns, src = split_spec(spec)
        root = load(src)
        doc = Doc(root)
        title = title or s(d(root.get("info")).get("title")) or args.name
        is_async = "asyncapi" in root
        api_id = (ns or "main") + ("-ws" if is_async else "")
        auth, auth_desc = (parse_auth(args.auth), "") if args.auth else auth_for(root)
        if auth.get("type") == "header" and s(auth.get("name")).lower() == "authorization" and "template" not in auth:
            said = f" The spec says: {auth_desc}" if auth_desc else ""
            warnings.append(f"{src}: tokens go in the Authorization header with no prefix.{said} If the server wants one, pass --auth 'header:Authorization:<prefix> {{token}}'")
        if is_async:
            apis[api_id] = {"base": ws_base(root), "env": env, "base_env": f"{env}_WS_URL", "auth": auth}
            ops = asyncapi_ops(doc, api_id, args.asyncapi_client_view)
        else:
            base = args.base_url or rest_base(root, src)
            if not base.startswith(("http://", "https://")):
                warnings.append(f"{src}: no absolute server URL ({base!r}); pass --base-url, or users must set {env}_BASE_URL")
            apis[api_id] = {"base": base, "env": env, "auth": auth}
            ops = openapi_ops(doc, api_id, warnings)
            name_ops(ops)
        for op in ops:
            if ns:
                op["ns"] = ns
            if tag_desc := s(op.pop("_tag_desc", "")):
                groups.setdefault(s(op["group"]), tag_desc)
        all_ops += ops
    if not all_ops:
        msg = "the specs define no operations"
        raise BuildError(msg)
    counts = Counter((s(op.get("ns")), s(op["group"]), s(op["action"])) for op in all_ops)
    if clashes := [" ".join(k).strip() for k, n in counts.items() if n > 1]:
        msg = f"commands defined by more than one spec: {', '.join(clashes[:5])}; namespace the specs as NAME=SPEC"
        raise BuildError(msg)
    return {"name": args.name, "title": title, "apis": apis, "groups": groups, "ops": list[JSON](all_ops)}


def render(template: Path, values: dict[str, str]) -> str:
    text = template.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    if leftover := re.findall(r"\{\{\w+\}\}", text):
        msg = f"{template}: unfilled placeholders {leftover}"
        raise BuildError(msg)
    return text


def write_project(out: Path, index: Node, args: argparse.Namespace) -> None:
    pkg = args.name.replace("-", "_")
    first_api = d(next(iter(d(index["apis"]).values())))
    values = {
        "name": args.name,
        "pkg": pkg,
        "title": s(index["title"]),
        "title_toml": json.dumps(s(index["title"]), ensure_ascii=False)[1:-1],
        "env": s(first_api.get("env")),
        "count": str(len(lst(index["ops"]))),
        "specs": ", ".join(f"`{x}`" for x in args.specs),
        "date": dt.datetime.now(dt.UTC).date().isoformat(),
    }
    template = SKILL / "assets" / "template"
    src = out / "src" / pkg
    src.mkdir(parents=True, exist_ok=True)
    (out / "tests").mkdir(exist_ok=True)
    for name in ("pyproject.toml", "README.md", ".gitignore", ".pre-commit-config.yaml", "tests/test_cli.py"):
        source = template / (name + ".tmpl" if name.endswith(".py") else name)
        (out / name).write_text(render(source, values), encoding="utf-8")
    shutil.copyfile(SKILL / "assets" / "cli.py.tmpl", src / "cli.py")
    (src / "__init__.py").write_text(f'"""Agent-first CLI for {values["title"]}."""\n', encoding="utf-8")
    (src / "commands.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    manifest = {k: v for k, v in vars(args).items() if k not in ("out", "rebuild")} | {"built": values["date"]}
    (out / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def absolute_spec(spec: str) -> str:
    """Record local spec paths absolutely so --rebuild works from any directory."""
    ns, src = split_spec(spec)
    if not src.startswith(("http://", "https://")):
        src = str(Path(src).expanduser().resolve())
    return f"{ns}={src}" if ns else src


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("specs", nargs="*", help="OpenAPI/Swagger/AsyncAPI file or URL; NAME=SPEC puts its commands under `<cli> NAME`")
    parser.add_argument("--name", help="command name, e.g. gitea-api (check `command -v NAME` first); the package is NAME with _")
    parser.add_argument("--out", type=Path, help="project directory (default: ~/dev/NAME)")
    parser.add_argument("--env", help="env var prefix for TOKEN, BASE_URL, READ_ONLY (default: NAME upper-cased)")
    parser.add_argument("--base-url", help="REST base URL when the spec has none or a relative one")
    parser.add_argument("--auth", help="override the spec's auth: none | bearer | basic | header:NAME[:TEMPLATE] | query:NAME (TEMPLATE uses {token})")
    parser.add_argument("--title", help="display title (default: the first spec's info.title)")
    parser.add_argument("--asyncapi-client-view", action="store_true", help="AsyncAPI 3 docs written from the client's side (default: the server's)")
    parser.add_argument("--rebuild", type=Path, metavar="DIR", help="repeat the build recorded in DIR/.api-cli.json")
    args = parser.parse_args()
    if args.rebuild:
        recorded = json.loads((args.rebuild / MANIFEST).read_text(encoding="utf-8"))
        args = argparse.Namespace(**(vars(args) | {k: v for k, v in recorded.items() if k != "built"} | {"out": args.rebuild}))
    if not args.specs or not args.name:
        parser.error("give at least one spec and --name (or --rebuild DIR)")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", args.name):
        parser.error("--name must be lowercase letters, digits, and hyphens")
    args.specs = [absolute_spec(spec) for spec in args.specs]
    args.out = (args.out or Path.home() / "dev" / args.name).expanduser()
    if args.out.exists() and any(args.out.iterdir()) and not (args.out / MANIFEST).exists():
        parser.error(f"{args.out} exists and was not built by api-cli; choose another --out")
    return args


def main() -> int:
    args = parse_args()
    warnings: list[str] = []
    try:
        index = compile_index(args, warnings)
    except (BuildError, OSError, ValueError, yaml.YAMLError) as e:
        sys.stderr.write(f"build: {e}\n")
        return 1
    write_project(args.out, index, args)
    ops = [d(op) for op in lst(index["ops"])]
    groups = sorted({f"{s(op.get('ns'))} {s(op['group'])}".strip() for op in ops})
    sys.stdout.write(f"{len(ops)} commands in {len(groups)} groups -> {args.out}\ngroups: {' '.join(groups)[:400]}\n")
    for warning in dict.fromkeys(warnings):
        sys.stdout.write(f"warning: {warning}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
