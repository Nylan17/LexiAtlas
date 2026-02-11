#!/usr/bin/env python3
"""
Rule-based rewrites for Wayback URLs when probing is infeasible or unreliable.

This is intentionally conservative and targeted:
- If a Wayback URL wraps an original on a 'trusted stable host', rewrite to the direct original.

Why:
- Some domains (notably archive.org in some environments) may be blocked from automated probing.

Default trusted hosts:
- archive.org (and www.archive.org)

Usage:
  cd lexicity
  python3 scripts/link_audit.py
  python3 scripts/rule_based_wayback_rewrites.py --apply
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlunparse


WAYBACK_RE = re.compile(r"^https?://web\.archive\.org/web/(?:\\d+|\\*)/(https?://.+)$")


def unwrap_wayback(url: str) -> Optional[str]:
    u = url.strip()
    for _ in range(2):
        m = WAYBACK_RE.match(u)
        if not m:
            return None if u == url.strip() else u
        u = m.group(1)
    return u


def force_https(url: str) -> str:
    try:
        p = urlparse(url)
        if p.scheme == "http":
            return urlunparse(p._replace(scheme="https"))
    except Exception:
        pass
    return url


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--rows-csv",
        default=str(root / "link_audit" / "link_audit_rows.csv"),
        help="CSV produced by scripts/link_audit.py",
    )
    ap.add_argument(
        "--out-json",
        default=str(root / "link_audit" / "rule_rewrites.json"),
        help="Where to write rewrite map JSON",
    )
    ap.add_argument(
        "--trusted-host",
        action="append",
        default=["archive.org", "www.archive.org"],
        help="Hostnames eligible for rule-based rewriting (repeatable)",
    )
    ap.add_argument("--apply", action="store_true", help="Apply rewrites to Markdown files")
    args = ap.parse_args()

    rows_csv = Path(args.rows_csv).expanduser().resolve()
    out_json = Path(args.out_json).expanduser().resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)

    trusted = {h.lower() for h in (args.trusted_host or [])}

    rewrites: Dict[str, str] = {}
    with rows_csv.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if row.get("kind") != "wayback":
                continue
            wb = row.get("url") or ""
            orig = row.get("wayback_original") or unwrap_wayback(wb) or ""
            if not orig or "web.archive.org/web/" in orig:
                continue
            host = ""
            try:
                host = urlparse(orig).netloc.lower()
            except Exception:
                host = ""
            if host in trusted:
                rewrites[wb] = force_https(orig)

    out_json.write_text(json.dumps(rewrites, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"trusted_hosts": sorted(trusted), "rewrites": len(rewrites), "out_json": str(out_json)}, indent=2))

    if args.apply and rewrites:
        # Apply by reusing apply_link_rewrites.py logic (simple replace across md files).
        # We implement inline to avoid extra dependencies.
        content_dir = root / "site" / "src" / "content" / "languages"
        files_changed = 0
        batches = 0
        for md in sorted(content_dir.glob("*.md")):
            before = md.read_text(encoding="utf-8")
            after = before
            for old, new in rewrites.items():
                if old in after:
                    after = after.replace(old, new)
                    batches += 1
            if after != before:
                md.write_text(after, encoding="utf-8")
                files_changed += 1
        print(json.dumps({"applied": True, "files_changed": files_changed, "replacement_batches": batches}, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

