#!/usr/bin/env python3
"""
Flag potentially-original/editorial phrasing in imported Markdown content.

This is a heuristic to help a human paraphrase pass.
Outputs a markdown report at `link_audit/paraphrase_candidates.md` (gitignored).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple


PATTERNS = [
    r"\bclick on\b",
    r"\bmake sure to\b",
    r"\bthere'?s always\b",
    r"\bas always\b",
    r"\balways the first\b",
    r"\bthe site will take\b",
    r"\bget used to\b",
    r"\bremember\b",
    r"\bwhat'?s better than\b",
    r"\bthe hard way\b",
    r"\bhumorous\b",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--content-dir",
        default=str(root / "site" / "src" / "content" / "languages"),
    )
    ap.add_argument(
        "--out",
        default=str(root / "link_audit" / "paraphrase_candidates.md"),
    )
    ap.add_argument("--context", type=int, default=0, help="Extra lines of context to include")
    args = ap.parse_args()

    content_dir = Path(args.content_dir).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    rx = re.compile("|".join(f"(?:{p})" for p in PATTERNS), re.IGNORECASE)
    hits: List[Tuple[str, int, str]] = []

    for md in sorted(content_dir.glob("*.md")):
        lines = md.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, start=1):
            if rx.search(line):
                hits.append((md.name, i, line.strip()))

    report: List[str] = []
    report.append("# Paraphrase candidates")
    report.append("")
    report.append(
        "Heuristic list of lines that may be too editorial/original and worth rewriting into neutral phrasing."
    )
    report.append("")
    report.append(f"Total hits: **{len(hits)}**")
    report.append("")
    for fname, line_no, line in hits:
        report.append(f"- `{fname}:{line_no}` — {line}")
    report.append("")

    out.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

