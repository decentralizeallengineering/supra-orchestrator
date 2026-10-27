"""The `supra` command line. Standard library only.

Files live in $SUPRA_HOME (default: the current directory):
ORDERS.md, STATE.md, STATE-ARCHIVE.md, FACTS.md.
"""
import argparse
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

STATE_MAX = 150
RESULT_RE = re.compile(r"RESULT: (DONE|FAILED|BLOCKED) - \S.*$")
STATES = ("open", "done", "blocked")
ORDERS_HEADER = (
    "| id | date | words (verbatim) | owner | state |\n"
    "|---|---|---|---|---|\n"
)
DATE_FMT = "%Y-%m-%d %H:%M"


def home():
    return Path(os.environ.get("SUPRA_HOME") or ".")


def now():
    """Current time; SUPRA_NOW (YYYY-MM-DD HH:MM) overrides it so tests are stable."""
    fixed = os.environ.get("SUPRA_NOW")
    return datetime.strptime(fixed, DATE_FMT) if fixed else datetime.now().replace(second=0, microsecond=0)


def state_max():
    return int(os.environ.get("SUPRA_STATE_MAX") or STATE_MAX)


# ---------- ledger rows ----------

def esc(text):
    """Make text safe for one table cell: no newlines, escaped backslash and pipe."""
    text = " ".join(text.split())
    return text.replace("\\", "\\\\").replace("|", "\\|")


def split_row(line):
    """Split a table row into unescaped cells."""
    body = line.strip()
    if not (body.startswith("|") and body.endswith("|")):
        return None
    cells, cur, i, body = [], [], 0, body[1:-1]
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            cur.append(body[i + 1])
            i += 2
            continue
        if ch == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def join_row(cells):
    return "| " + " | ".join(esc(c) for c in cells) + " |"


def read_orders(path):
    """Return (lines, rows) where rows maps line index to its five cells."""
    lines = path.read_text().splitlines() if path.exists() else []
    rows = {}
    for n, line in enumerate(lines):
        cells = split_row(line)
        if cells and len(cells) == 5 and re.fullmatch(r"[A-Za-z]*\d+", cells[0]):
            rows[n] = cells
    return lines, rows


def write_lines(path, lines):
    path.write_text("\n".join(lines) + "\n")


def cmd_order_new(args):
    words = args.words
    if not words or not words.strip():
        print("supra: the person's verbatim words are required", file=sys.stderr)
        return 2
    path = home() / "ORDERS.md"
    lines, rows = read_orders(path)
    if not lines:
        lines = ["# Orders ledger", "", *ORDERS_HEADER.splitlines()]
    top = max((int(re.sub(r"\D", "", r[0])) for r in rows.values()), default=0)
    oid = f"O{top + 1}"
    quoted = '"' + " ".join(words.split()) + '"'
    lines.append(join_row([oid, now().strftime(DATE_FMT), quoted, args.owner, "open"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    write_lines(path, lines)
    print(oid)
    return 0


def cmd_order_state(args):
    path = home() / "ORDERS.md"
    lines, rows = read_orders(path)
    hit = [n for n, c in rows.items() if c[0] == args.id]
    if not hit:
        print(f"supra: no order {args.id}", file=sys.stderr)
        return 2
    evidence = (args.evidence or "").strip()
    if args.state in ("done", "blocked") and not evidence:
        print(f"supra: state {args.state} needs --evidence", file=sys.stderr)
        return 2
    cells = rows[hit[0]]
    cells[4] = f"{args.state}: {evidence}" if evidence else args.state
    lines[hit[0]] = join_row(cells)
    write_lines(path, lines)
    print(f"{args.id} {cells[4]}")
    return 0


# ---------- state, facts ----------

def cmd_state_add(args):
    line = " ".join(args.line.split())
    if not RESULT_RE.search(line):
        print("supra: line must end with 'RESULT: DONE|FAILED|BLOCKED - <evidence>'", file=sys.stderr)
        return 2
    path = home() / "STATE.md"
    lines = path.read_text().splitlines() if path.exists() else ["# State", ""]
    lines.append(f"- {now().strftime(DATE_FMT)} {line}")
    moved = []
    limit = state_max()
    while len(lines) > limit:
        idx = next((n for n, text in enumerate(lines) if text.startswith("- ")), None)
        if idx is None:
            break
        moved.append(lines.pop(idx))
    if moved:
        with open(home() / "STATE-ARCHIVE.md", "a") as fh:
            fh.write("\n".join(moved) + "\n")
    write_lines(path, lines)
    print(f"STATE.md {len(lines)} lines, {len(moved)} archived")
    return 0


def cmd_facts_add(args):
    text = " ".join(args.text.split())
    if not text:
        print("supra: empty fact", file=sys.stderr)
        return 2
    path = home() / "FACTS.md"
    new = not path.exists()
    with open(path, "a") as fh:  # append only; there is deliberately no edit or delete
        if new:
            fh.write("# Facts (append-only)\n\n")
        fh.write(f"- {now().strftime(DATE_FMT)} {text}\n")
    return 0


# ---------- audit ----------

def audit(path, hours, at):
    """Return finding strings for stale open orders and done rows with no evidence."""
    _, rows = read_orders(path)
    found = []
    for cells in rows.values():
        oid, date, _, _, state = cells
        kind, _, evidence = state.partition(":")
        kind = kind.strip().lower()
        if kind == "open":
            try:
                age = (at - datetime.strptime(date, DATE_FMT)).total_seconds() / 3600
            except ValueError:
                found.append(f"{oid}: unreadable date {date!r}")
                continue
            if age > hours:
                found.append(f"{oid}: open for {age:.1f} h (limit {hours:g} h)")
        elif kind == "done" and not evidence.strip():
            found.append(f"{oid}: DONE without evidence")
    return found


def cmd_audit(args):
    found = audit(home() / "ORDERS.md", args.hours, now())
    for item in found:
        print(item)
    if not found:
        print("audit clean")
    return 1 if found else 0


def cmd_init(args):
    target = Path(args.dir)
    target.mkdir(parents=True, exist_ok=True)
    src = Path(__file__).parent / "templates"
    for tpl in sorted(src.iterdir()):
        dest = target / tpl.name
        if dest.exists():
            print(f"kept   {dest}")
        else:
            shutil.copyfile(tpl, dest)
            print(f"wrote  {dest}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="supra", description="Orders, state and facts for a fleet of Claude Code sessions.")
    sub = p.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="copy the templates into a directory (never overwrites)")
    init.add_argument("dir", nargs="?", default=".")
    init.set_defaults(fn=cmd_init)

    order = sub.add_parser("order", help="orders ledger").add_subparsers(dest="sub", required=True)
    new = order.add_parser("new", help="record the person's verbatim words as a new row")
    new.add_argument("words", help="the exact words, quoted")
    new.add_argument("--owner", default="unassigned", help="session that carries the order out")
    new.set_defaults(fn=cmd_order_new)
    st = order.add_parser("state", help="set an order to open, done or blocked")
    st.add_argument("id")
    st.add_argument("state", choices=STATES)
    st.add_argument("--evidence", help="required for done and blocked")
    st.set_defaults(fn=cmd_order_state)

    state = sub.add_parser("state", help="STATE.md").add_subparsers(dest="sub", required=True)
    sa = state.add_parser("add", help="append a line ending in 'RESULT: DONE|FAILED|BLOCKED - <evidence>'")
    sa.add_argument("line")
    sa.set_defaults(fn=cmd_state_add)

    facts = sub.add_parser("facts", help="FACTS.md").add_subparsers(dest="sub", required=True)
    fa = facts.add_parser("add", help="append a dated fact")
    fa.add_argument("text")
    fa.set_defaults(fn=cmd_facts_add)

    au = sub.add_parser("audit", help="list stale open orders and DONE rows without evidence")
    au.add_argument("--hours", type=float, default=24.0, help="open longer than this is stale (default 24)")
    au.set_defaults(fn=cmd_audit)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
