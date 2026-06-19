"""
digest.py — Rōnin monthly catalog digest.

Once a month, compare the catalog (the SEED array in index.html) and your reading
progress (the synced Gist) against last month's snapshot, and post a Slack summary:
new suggestions, changed release dates, newly-released volumes, and how far you
read this month. The snapshot is stored as a second file in the same private Gist
as your data, so no repo file churn.

Generic plumbing (GitHub file/gist reads, Slack posting + blocks) lives in
automation-core; everything domain-specific (parsing SEED, diffing, wording)
lives here.

Run:
    # live (in GitHub Actions): reads repo + gist, posts to Slack, saves snapshot
    python digest.py

    # local dry-run: read fixtures, print blocks, touch nothing remote
    python digest.py --dry-run --html index.html --state sample-data.json \
                     --snapshot prev-snapshot.json

Env (live mode):
    GITHUB_TOKEN       PAT with `gist` scope (default Actions token can't read a private gist)
    RONIN_GIST_ID      id of the gist that holds ronin-data.json
    SLACK_WEBHOOK_URL  incoming webhook
    RONIN_REPO         owner/name (default ashomah/ronin-manga-reading-log)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from typing import Any, Optional

DATA_FILE = "ronin-data.json"
SNAPSHOT_FILE = "ronin-digest-snapshot.json"
DEFAULT_REPO = "ashomah/ronin-manga-reading-log"
INDEX_PATH = "index.html"


# ── Catalog parsing (SEED array in index.html) ───────────────────────────
def _extract_seed_literal(html: str) -> str:
    """Return the exact text of the SEED = [ ... ] array literal.

    Scans bracket depth while respecting JS string literals (', ", `) and
    escapes, so brackets inside strings/blurbs don't fool us.
    """
    m = re.search(r"\bSEED\s*=\s*\[", html)
    if not m:
        raise ValueError("SEED array not found in index.html")
    i = m.end() - 1  # index of the opening '['
    depth = 0
    quote: Optional[str] = None
    escaped = False
    start = i
    while i < len(html):
        c = html[i]
        if quote:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == quote:
                quote = None
        else:
            if c in "\"'`":
                quote = c
            elif c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
                if depth == 0:
                    return html[start:i + 1]
        i += 1
    raise ValueError("Unterminated SEED array literal")


def _entry_vols(region: str) -> Optional[int]:
    """Volumes of the recommended edition (else the first), as the 'available'
    count for a series. Returns None if no edition vols are present."""
    editions = re.findall(r"\{[^{}]*\}", region)
    first: Optional[int] = None
    for ed in editions:
        mv = re.search(r"\bvols:\s*(\d+)", ed)
        if not mv:
            continue
        v = int(mv.group(1))
        if first is None:
            first = v
        if re.search(r"\brecommended:\s*true", ed):
            return v
    return first


def parse_catalog(html: str) -> dict[str, dict[str, Any]]:
    """Parse SEED into {id: {t, section, nextDate, vols}}.

    Relies on the catalog's disciplined format (double-quoted strings with no
    nested double quotes, as enforced by CLAUDE.md).
    """
    seed = _extract_seed_literal(html)
    # Each entry starts with id:"..",section:"shelf|wishlist".
    starts = [m.start() for m in
              re.finditer(r'\{\s*id:"[^"]+",\s*section:"(?:shelf|wishlist)"', seed)]
    out: dict[str, dict[str, Any]] = {}
    for idx, s in enumerate(starts):
        region = seed[s: starts[idx + 1] if idx + 1 < len(starts) else len(seed)]
        mid = re.search(r'id:"([^"]+)"', region)
        msec = re.search(r'section:"(shelf|wishlist)"', region)
        if not mid or not msec:
            continue
        mt = re.search(r'\bt:"([^"]*)"', region)
        mnd = re.search(r'\bnextDate:"([^"]*)"', region)
        out[mid.group(1)] = {
            "t": mt.group(1) if mt else mid.group(1),
            "section": msec.group(1),
            "nextDate": mnd.group(1) if mnd else "",
            "vols": _entry_vols(region),
        }
    return out


# ── Progress (the synced Gist data) ──────────────────────────────────────
def read_progress(state: dict[str, Any]) -> dict[str, Any]:
    """Aggregate owned/read totals from the user-data object.

    Keys starting with '__' are metadata (schema, timestamps, seed flags).
    """
    by_id: dict[str, dict[str, int]] = {}
    total_read = total_owned = 0
    for k, v in state.items():
        if k.startswith("__") or not isinstance(v, dict):
            continue
        owned = int(v.get("owned") or 0)
        read = min(int(v.get("read") or 0), owned)  # read is clamped <= owned
        by_id[k] = {"owned": owned, "read": read}
        total_owned += owned
        total_read += read
    return {"read": total_read, "owned": total_owned, "byId": by_id}


def make_snapshot(catalog: dict, progress: dict, today: _dt.date) -> dict:
    return {"at": today.isoformat(), "catalog": catalog, "progress": progress}


# ── Diff ─────────────────────────────────────────────────────────────────
def diff(prev: Optional[dict], catalog: dict, progress: dict) -> dict:
    """Compute month-over-month changes. prev=None means first run (baseline)."""
    if not prev:
        return {"baseline": True}

    prev_cat: dict = prev.get("catalog", {})
    prev_prog: dict = prev.get("progress", {})
    prev_by = prev_prog.get("byId", {})

    new_suggestions, new_shelf, date_changes, new_volumes = [], [], [], []
    for cid, c in catalog.items():
        if cid not in prev_cat:
            (new_suggestions if c["section"] == "wishlist" else new_shelf).append(c["t"])
            continue
        p = prev_cat[cid]
        if c["nextDate"] and c["nextDate"] != p.get("nextDate", ""):
            date_changes.append((c["t"], p.get("nextDate", ""), c["nextDate"]))
        cv, pv = c.get("vols"), p.get("vols")
        if isinstance(cv, int) and isinstance(pv, int) and cv > pv:
            new_volumes.append((c["t"], pv, cv))

    read_progressed = []
    for cid, cur in progress["byId"].items():
        before = prev_by.get(cid, {}).get("read", 0)
        if cur["read"] > before:
            title = catalog.get(cid, {}).get("t", cid)
            read_progressed.append((title, before, cur["read"]))
    read_progressed.sort(key=lambda x: x[2] - x[1], reverse=True)

    return {
        "baseline": False,
        "since": prev.get("at", ""),
        "new_suggestions": new_suggestions,
        "new_shelf": new_shelf,
        "date_changes": date_changes,
        "new_volumes": new_volumes,
        "read_delta": progress["read"] - prev_prog.get("read", 0),
        "owned_delta": progress["owned"] - prev_prog.get("owned", 0),
        "read_total": progress["read"],
        "owned_total": progress["owned"],
        "read_progressed": read_progressed,
    }


# ── Slack message ────────────────────────────────────────────────────────
def build_blocks(changes: dict, today: _dt.date) -> list[dict]:
    from automation_core import slack

    blocks = [slack.header("📚 Rōnin — monthly catalog digest")]

    if changes.get("baseline"):
        blocks += [
            slack.section("First run — captured a baseline of your catalog and "
                          "progress. Next month you'll get the changes since today."),
            slack.context(today.isoformat()),
        ]
        return blocks

    since = changes.get("since") or "last month"
    blocks.append(slack.context(f"Changes since {since} → {today.isoformat()}"))

    def lines(items: list[str]) -> str:
        return "\n".join(items)

    if changes["new_suggestions"]:
        blocks.append(slack.section(
            "*✨ New suggestions*\n" + lines(f"• {t}" for t in changes["new_suggestions"])))
    if changes["new_shelf"]:
        blocks.append(slack.section(
            "*➕ Added to your shelf*\n" + lines(f"• {t}" for t in changes["new_shelf"])))
    if changes["new_volumes"]:
        blocks.append(slack.section(
            "*📦 New volumes released*\n"
            + lines(f"• {t}: {pv} → *{cv}* vols" for t, pv, cv in changes["new_volumes"])))
    if changes["date_changes"]:
        blocks.append(slack.section(
            "*🗓️ Release-date updates*\n"
            + lines(f"• *{t}* — {nd}" for t, _, nd in changes["date_changes"])))

    rd, od = changes["read_delta"], changes["owned_delta"]
    progressed = changes["read_progressed"]
    prog_lines = [
        f"*This month:* +{rd} volume(s) read" + (f", +{od} acquired" if od else ""),
        f"*Totals:* {changes['read_total']} read / {changes['owned_total']} owned",
    ]
    blocks.append(slack.divider())
    blocks.append(slack.fields(prog_lines))
    if progressed:
        blocks.append(slack.section(
            "*Series you advanced*\n"
            + lines(f"• {t}: {b} → *{a}*" for t, b, a in progressed[:8])))

    nothing = not any(changes[k] for k in
                      ("new_suggestions", "new_shelf", "new_volumes",
                       "date_changes", "read_progressed")) and rd == 0 and od == 0
    if nothing:
        blocks.append(slack.context("No catalog changes or reading progress this month."))
    return blocks


# ── Entry point ──────────────────────────────────────────────────────────
def _load(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def main() -> int:
    ap = argparse.ArgumentParser(description="Rōnin monthly catalog digest.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Read local fixtures, print blocks, touch nothing remote.")
    ap.add_argument("--html", help="Local index.html (dry-run).")
    ap.add_argument("--state", help="Local ronin-data.json (dry-run).")
    ap.add_argument("--snapshot", help="Local previous snapshot json (dry-run; optional).")
    ap.add_argument("--no-slack", action="store_true", help="Compute + save, don't post.")
    ap.add_argument("--no-save", action="store_true", help="Don't write the new snapshot.")
    args = ap.parse_args()

    today = _dt.date.today()

    if args.dry_run:
        if not args.html or not args.state:
            print("dry-run needs --html and --state", file=sys.stderr)
            return 2
        html = _load(args.html)
        state = json.loads(_load(args.state))
        prev = json.loads(_load(args.snapshot)) if args.snapshot else None
        catalog = parse_catalog(html)
        progress = read_progress(state)
        blocks = build_blocks(diff(prev, catalog, progress), today)
        print(json.dumps({"blocks": blocks}, indent=2, ensure_ascii=False))
        print(f"\n[dry-run] {len(catalog)} series parsed; "
              f"{progress['read']} read / {progress['owned']} owned", file=sys.stderr)
        return 0

    # In CI the workflow maps RONIN_GIST_TOKEN -> GITHUB_TOKEN; locally (sourcing
    # .env) only RONIN_GIST_TOKEN exists, so fall back to it.
    os.environ.setdefault("GITHUB_TOKEN", os.environ.get("RONIN_GIST_TOKEN", ""))

    from automation_core import github, slack

    repo = os.environ.get("RONIN_REPO", DEFAULT_REPO)
    gist_id = os.environ.get("RONIN_GIST_ID")
    if not gist_id:
        print("RONIN_GIST_ID not set.", file=sys.stderr)
        return 2

    html, _ = github.get_file(repo, INDEX_PATH)
    state = json.loads(github.get_gist(gist_id, filename=DATA_FILE))
    try:
        prev = json.loads(github.get_gist(gist_id, filename=SNAPSHOT_FILE))
    except github.GitHubError:
        prev = None  # first run

    catalog = parse_catalog(html)
    progress = read_progress(state)
    blocks = build_blocks(diff(prev, catalog, progress), today)

    if not args.no_slack:
        slack.post_blocks(blocks)
        print("Posted digest to Slack.")

    if not args.no_save:
        snap = make_snapshot(catalog, progress, today)
        github.update_gist(gist_id, SNAPSHOT_FILE,
                           json.dumps(snap, indent=2, ensure_ascii=False),
                           description="Rōnin — monthly digest snapshot")
        print("Saved snapshot to gist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
