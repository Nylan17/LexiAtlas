#!/usr/bin/env python3
"""
Extract and classify outbound links from the Markdown language content.

Outputs a JSON and CSV report under ./link_audit/ (ignored by git).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import unquote, urlparse


MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


WAYBACK_RE = re.compile(
    r"^https?://web\.archive\.org/web/(?P<ts>\d+|\*)/(?P<orig>https?://.+)$"
)


def _unwrap_wayback(url: str) -> Optional[str]:
    """
    If URL is a Wayback wrapper, return the original URL.
    Handles nested wayback by unwrapping repeatedly.
    """
    u = url.strip()
    for _ in range(3):
        m = WAYBACK_RE.match(u)
        if not m:
            return None if u == url.strip() else u
        u = m.group("orig")
    return u


def _is_http_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


@dataclass
class LinkRow:
    file: str
    line: int
    text: str
    url: str
    kind: str  # direct | wayback | other
    wayback_original: str = ""


def iter_markdown_links(md_path: Path) -> Iterable[LinkRow]:
    for i, line in enumerate(md_path.read_text(encoding="utf-8").splitlines(), start=1):
        for m in MD_LINK_RE.finditer(line):
            text = m.group(1).strip()
            url = m.group(2).strip()
            if not _is_http_url(url):
                continue
            orig = _unwrap_wayback(url)
            if orig:
                kind = "wayback"
                wayback_original = orig
            elif "web.archive.org/web/" in url:
                kind = "wayback"
                wayback_original = ""
            else:
                kind = "direct"
                wayback_original = ""
            yield LinkRow(
                file=str(md_path),
                line=i,
                text=text,
                url=url,
                kind=kind,
                wayback_original=wayback_original,
            )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--content-dir",
        default=str(root / "site" / "src" / "content" / "languages"),
        help="Directory of markdown language files",
    )
    ap.add_argument(
        "--out-dir",
        default=str(root / "link_audit"),
        help="Output directory for reports",
    )
    ap.add_argument(
        "--format",
        choices=["both", "csv", "json"],
        default="both",
        help="Which outputs to write (default: both)",
    )
    ap.add_argument(
        "--progress",
        action="store_true",
        help="Print progress as files are scanned",
    )
    args = ap.parse_args()

    content_dir = Path(args.content_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[LinkRow] = []
    mds = sorted(content_dir.glob("*.md"))
    for idx, md in enumerate(mds, start=1):
        if args.progress:
            print(f"[link_audit] scanning {idx}/{len(mds)}: {md.name}")
        rows.extend(iter_markdown_links(md))

    # summary
    total = len(rows)
    wayback = sum(1 for r in rows if r.kind == "wayback")
    direct = sum(1 for r in rows if r.kind == "direct")
    http = sum(1 for r in rows if r.url.startswith("http://"))

    summary = {
        "total_links": total,
        "direct_links": direct,
        "wayback_links": wayback,
        "http_links": http,
        "content_dir": str(content_dir),
    }

    if args.format in ("both", "json"):
        (out_dir / "link_audit_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        (out_dir / "link_audit_rows.json").write_text(
            json.dumps([asdict(r) for r in rows], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.format in ("both", "csv"):
        with (out_dir / "link_audit_rows.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["file", "line", "text", "url", "kind", "wayback_original"],
            )
            w.writeheader()
            for r in rows:
                w.writerow(asdict(r))

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

