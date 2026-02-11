#!/usr/bin/env python3
"""
Generate a human-readable report of remaining Wayback links.

Writes to `link_audit/wayback_remaining_report.md` (gitignored).
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows-csv", default=str(root / "link_audit" / "link_audit_rows.csv"))
    ap.add_argument("--check-csv", default=str(root / "link_audit" / "wayback_check_results.csv"))
    ap.add_argument("--out", default=str(root / "link_audit" / "wayback_remaining_report.md"))
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--samples", type=int, default=6)
    args = ap.parse_args()

    rows_csv = Path(args.rows_csv).expanduser().resolve()
    check_csv = Path(args.check_csv).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    check = {}
    if check_csv.exists():
        with check_csv.open("r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                check[row["wayback_url"]] = row

    remaining = []
    with rows_csv.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if row.get("kind") != "wayback":
                continue
            wb = row.get("url") or ""
            cr = check.get(wb, {})
            remaining.append(
                {
                    "file": row.get("file", ""),
                    "line": row.get("line", ""),
                    "text": row.get("text", ""),
                    "wayback_url": wb,
                    "original_url": cr.get("original_url") or row.get("wayback_original") or "",
                    "status": cr.get("status", ""),
                    "error": cr.get("error", ""),
                    "decision": cr.get("decision", ""),
                }
            )

    by_domain = Counter()
    by_reason = Counter()
    examples = defaultdict(list)
    for it in remaining:
        orig = it["original_url"]
        wb = it["wayback_url"]
        host = ""
        try:
            host = (urlparse(orig).netloc or urlparse(wb).netloc).lower()
        except Exception:
            host = ""
        by_domain[host] += 1
        status = it.get("status") or "unknown"
        err = it.get("error") or ""
        reason = status if status and status != "error" else (err.split(":", 1)[0] if err else "error")
        by_reason[reason] += 1
        if len(examples[host]) < args.samples:
            examples[host].append(it)

    lines = []
    lines.append("# Remaining Wayback links report")
    lines.append("")
    lines.append(f"- Remaining Wayback links in content: **{len(remaining)}**")
    lines.append("")
    lines.append("## Top domains")
    lines.append("")
    for host, count in by_domain.most_common(args.top):
        lines.append(f"- {count} — `{host}`")
    lines.append("")
    lines.append("## Top failure reasons (from last check)")
    lines.append("")
    for reason, count in by_reason.most_common(args.top):
        lines.append(f"- {count} — `{reason}`")
    lines.append("")
    lines.append("## Samples (by domain)")
    lines.append("")
    for host, _ in by_domain.most_common(min(args.top, 12)):
        lines.append(f"### `{host}`")
        lines.append("")
        for it in examples.get(host, []):
            lines.append(f"- `{it['file']}:{it['line']}` — {it['text']}")
            if it.get("original_url"):
                lines.append(f"  - orig: `{it['original_url']}`")
            lines.append(f"  - wayback: `{it['wayback_url']}`")
            if it.get("status") or it.get("error"):
                lines.append(
                    f"  - last_check: `{it.get('status','')}` `{(it.get('error','') or '')[:120]}`"
                )
        lines.append("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

