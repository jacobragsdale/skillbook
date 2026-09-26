#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Proton Mail Bridge client. Read, organize, and draft -- NEVER send. Stdlib only.

Password: $PMAIL_PASS, else `pass show protonmail/bridge-imap`.
There is no SMTP code path: replies are saved to Drafts and Jacob sends them.
Organizing (archive/move/label/seen) never deletes: Trash and Spam are refused.
Read commands open mailboxes readonly.
"""
import argparse, email, email.message, email.policy, email.utils, html.parser, imaplib, os, re, ssl, subprocess, sys
import datetime
from email.header import decode_header, make_header

USER = os.environ.get("PMAIL_USER", "jacobragsdale@pm.me")
CERT = os.path.expanduser("~/.config/pmail/bridge-cert.pem")


def password():
    pw = os.environ.get("PMAIL_PASS")
    if pw:
        return pw
    return subprocess.run(["pass", "show", "protonmail/bridge-imap"],
                          capture_output=True, text=True, check=True).stdout.splitlines()[0]


class _Text(html.parser.HTMLParser):
    """Visible text from an HTML body. Enough to read mail, not a renderer."""
    SKIP = {"script", "style", "head", "title"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in ("p", "br", "div", "tr", "li", "h1", "h2", "h3"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1

    def handle_data(self, d):
        if not self.skip and d.strip():
            self.out.append(d.strip() + " ")


def untag(h):
    p = _Text()
    p.feed(h)
    return re.sub(r"\n{3,}", "\n\n", "".join(p.out)).strip()


def hdr(raw):
    return str(make_header(decode_header(raw or "")))


def imap(folder=None, readonly=True):
    # ponytail: pins the bridge's self-signed cert; re-copy it if bridge reinstalls.
    ctx = ssl.create_default_context(cafile=CERT)
    ctx.check_hostname = False
    m = imaplib.IMAP4("127.0.0.1", 1143)
    m.starttls(ctx)
    m.login(USER, password())
    if folder:
        ok, err = m.select(f'"{folder}"', readonly=readonly)
        if ok != "OK":
            sys.exit(f"cannot open {folder!r}: {err[0].decode()}")
    return m


def cmd_folders(_):
    for line in imap().list()[1]:
        print(line.decode())


def show(m, uids, n=None):
    """Print one header line per uid. ONE bulk FETCH, not one per message."""
    uids = uids[-n:] if n else uids
    if not uids:
        return print("(no matches)")
    # ponytail: one round trip for the whole set; chunk it if a set ever exceeds ~5k uids.
    # UID is requested explicitly: without it the uid rides in a trailing
    # response element and part[0] carries only the sequence number.
    resp = m.uid("fetch", b",".join(uids),
                 "(UID BODY.PEEK[HEADER.FIELDS (DATE FROM SUBJECT)])")[1]
    rows = {}
    for part in resp:
        if not isinstance(part, tuple):
            continue
        uid = re.search(rb"UID (\d+)", part[0])
        msg = email.message_from_bytes(part[1])
        if not uid:
            continue
        rows[int(uid.group(1))] = msg
    # Sort by Date, not uid: uid order only approximates arrival, and in
    # "All Mail" it is visibly out of order. ponytail: the -n cut above is
    # still by uid; Proton's bridge advertises no SORT to do better cheaply.
    def when(item):
        try:
            d = email.utils.parsedate_to_datetime(item[1]["Date"])
            return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)
        except (TypeError, ValueError):
            return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)

    for uid, msg in sorted(rows.items(), key=when):
        print(f'{uid:>7}  {hdr(msg["Date"])[:31]:31}  '
              f'{hdr(msg["From"])[:34]:34}  {hdr(msg["Subject"])}')
    return len(rows)


def cmd_ls(a):
    folder = a[0] if a else "INBOX"
    n = int(a[1]) if len(a) > 1 else 20
    m = imap(folder)
    show(m, m.uid("search", None, "ALL")[1][0].split(), n)


def cmd_search(a):
    if not a:
        sys.exit('usage: pmail search <folder> <imap-keys...>   e.g. search "All Mail" FROM github SINCE 01-Sep-2026')
    n = 25
    a = list(a)
    if "-n" in a:
        i = a.index("-n")
        n = int(a[i + 1])
        del a[i:i + 2]
    m = imap(a[0])
    # imaplib joins argv with spaces, so a multi-word value must arrive pre-quoted.
    keys = [f'"{k}"' if " " in k and not k.startswith('"') else k for k in a[1:]]
    ok, data = m.uid("search", None, *keys)
    if ok != "OK":
        sys.exit(f"search rejected: {data[0].decode()}")
    uids = data[0].split()
    found = show(m, uids, n) or 0
    if len(uids) > found:
        print(f"\n({len(uids)} matches, newest {found} shown -- use -n to widen)")


def cmd_read(a):
    m = imap(a[0])
    uid = a[1] if len(a) > 1 else (m.uid("search", None, "ALL")[1][0].split() or [b""])[-1].decode()
    if not uid:
        return print(f"{a[0]}: empty")
    # BODY.PEEK, not BODY: reading must not set \Seen.
    raw = m.uid("fetch", uid, "(BODY.PEEK[])")[1][0][1]
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    print(f"uid: {uid}")
    for k in ("Date", "From", "To", "Cc", "Subject"):
        if msg[k]:
            print(f"{k}: {hdr(msg[k])}")
    names = [p.get_filename() for p in msg.iter_attachments() if p.get_filename()]
    if names:
        print(f"Attachments: {', '.join(names)}")
    body = msg.get_body(("plain", "html"))
    if not body:
        return print("\n(no text body)")
    text = body.get_content()
    print("\n" + (untag(text) if body.get_content_subtype() == "html" else text))


# Moving here is deleting on a timer (Proton empties both after 30 days).
NO_MOVE_TO = {"Trash", "Spam"}


def _target(a, usage):
    """Open <folder> read-write and echo the <uid,...> rows about to change.
    UIDs are per-folder: the echo is how a wrong-folder uid gets noticed."""
    if len(a) < 2:
        sys.exit(usage)
    m = imap(a[0], readonly=False)
    uids = a[1].encode()
    if not show(m, uids.split(b",")):
        sys.exit(f"no such uid in {a[0]!r}: {a[1]}")
    return m, uids


def _ok(resp, what):
    ok, data = resp
    if ok != "OK":
        sys.exit(f"{what} rejected: {data[0].decode() if data and data[0] else ok}")


def cmd_move(a):
    usage = "usage: pmail move <folder> <uid[,uid...]> <dest>"
    if len(a) < 3:
        sys.exit(usage)
    if a[2] in NO_MOVE_TO:
        sys.exit(f"refusing to move to {a[2]}: pmail never deletes mail")
    m, uids = _target(a, usage)
    _ok(m.uid("MOVE", uids, f'"{a[2]}"'), "move")
    print(f"-> moved to {a[2]}")


def cmd_label(a):
    usage = "usage: pmail label <folder> <uid[,uid...]> <label>"
    if len(a) < 3:
        sys.exit(usage)
    # Proton exposes labels as folders under Labels/; a COPY there applies the label.
    label = a[2] if a[2].startswith("Labels/") else f"Labels/{a[2]}"
    m, uids = _target(a, usage)
    _ok(m.uid("COPY", uids, f'"{label}"'), "label")
    print(f"-> labeled {label}")


def cmd_seen(a, on=True):
    m, uids = _target(a, f"usage: pmail {'seen' if on else 'unseen'} <folder> <uid[,uid...]>")
    _ok(m.uid("STORE", uids, "+FLAGS" if on else "-FLAGS", r"(\Seen)"), "flag")
    print(f"-> marked {'read' if on else 'unread'}")


def build_draft(to, subject, body, cc=None, orig=None):
    """A plain-text draft; with `orig`, a threaded reply to it."""
    msg = email.message.EmailMessage()
    msg["From"] = USER
    if orig is not None:
        to = to or orig["Reply-To"] or orig["From"]
        subj = str(orig["Subject"] or "")
        subject = subject or (subj if re.match(r"(?i)re:", subj) else f"Re: {subj}")
        if orig["Message-ID"]:
            msg["In-Reply-To"] = orig["Message-ID"]
            msg["References"] = f'{orig["References"] or ""} {orig["Message-ID"]}'.strip()
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject or ""
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=USER.split("@")[1])
    msg.set_content(body)
    return msg


def cmd_draft(a):
    p = argparse.ArgumentParser(prog="pmail draft",
                                description="Save a draft to Drafts; body on stdin. Never sends.")
    p.add_argument("--to")
    p.add_argument("--cc")
    p.add_argument("--subject")
    p.add_argument("--reply", nargs=2, metavar=("FOLDER", "UID"), help="thread as a reply to this message")
    o = p.parse_args(a)
    orig = None
    if o.reply:
        part = imap(o.reply[0]).uid("fetch", o.reply[1], "(BODY.PEEK[HEADER])")[1][0]
        if not isinstance(part, tuple):
            sys.exit(f"no such uid in {o.reply[0]!r}: {o.reply[1]}")
        orig = email.message_from_bytes(part[1], policy=email.policy.default)
    if not (o.to or orig):
        p.error("--to or --reply is required")
    msg = build_draft(o.to, o.subject, sys.stdin.read(), o.cc, orig)
    _ok(imap().append('"Drafts"', r"(\Draft \Seen)", None, msg.as_bytes(policy=email.policy.SMTP)),
        "draft")
    print(f'saved to Drafts: "{msg["Subject"]}" to {msg["To"]} -- Jacob sends it from Proton')


def demo():
    assert hdr("=?utf-8?B?SGVsbG8gd29ybGQ=?=") == "Hello world"
    orig = email.message_from_bytes(
        b"From: Ann <ann@x.com>\r\nSubject: Lunch\r\nMessage-ID: <1@x.com>\r\n\r\n",
        policy=email.policy.default)
    d = build_draft(None, None, "sure\n", orig=orig)
    assert (d["To"], d["Subject"]) == ("Ann <ann@x.com>", "Re: Lunch")
    assert d["In-Reply-To"] == d["References"] == "<1@x.com>"
    assert build_draft(None, None, "x", orig=email.message_from_bytes(
        b"From: a@b.c\r\nSubject: RE: Lunch\r\n\r\n", policy=email.policy.default))["Subject"] == "RE: Lunch"
    assert "Trash" in NO_MOVE_TO
    assert hdr(None) == ""
    # the read path: exercises email.policy.default, which is not imported by `import email`
    msg = email.message_from_bytes(
        b"Subject: hi\r\nFrom: a@b.c\r\nContent-Type: text/plain\r\n\r\nbody\r\n",
        policy=email.policy.default)
    assert msg.get_body(("plain",)).get_content().strip() == "body"
    assert untag("<style>x{}</style><p>Hello <b>you</b></p>") == "Hello you"
    print("ok")


if __name__ == "__main__":
    cmds = {"folders": cmd_folders, "ls": cmd_ls, "search": cmd_search,
            "read": cmd_read, "archive": lambda a: cmd_move(a[:2] + ["Archive"]),
            "move": cmd_move, "label": cmd_label, "seen": cmd_seen,
            "unseen": lambda a: cmd_seen(a, on=False), "draft": cmd_draft,
            "demo": lambda _: demo()}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit("usage: pmail folders | ls [folder] [n] | search <folder> <imap-query...> | "
                 "read <folder> [uid]\n"
                 "       pmail archive|seen|unseen <folder> <uid,...> | move <folder> <uid,...> <dest> | "
                 "label <folder> <uid,...> <label>\n"
                 "       pmail draft (--to ADDR | --reply FOLDER UID) [--cc ADDR] [--subject S] < body"
                 "        (never sends)")
    cmds[sys.argv[1]](sys.argv[2:])
