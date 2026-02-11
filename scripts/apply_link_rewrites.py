#!/usr/bin/env python3
"""
Apply link rewrites to Markdown content, based on a suggestions JSON map:
  { "<old_url>": "<new_url>", ... }

Defaults to dry-run; pass --apply to modify files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple


def _apply_to_text(text: str, rewrites: Dict[str, str]) -> Tuple[str, int]:
    n = 0
    out = text
    for old, new in rewrites.items():
        if old == new:
            continue
        if old in out:
            out = out.replace(old, new)
            n += 1
    return out, n


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--content-dir",
        default=str(root / "site" / "src" / "content" / "languages"),
        help="Directory containing markdown files",
    )
    ap.add_argument(
        "--rewrites",
        default=str(root / "link_audit" / "wayback_rewrite_suggestions.json"),
        help="JSON map of old_url -> new_url",
    )
    ap.add_argument("--apply", action="store_true", help="Actually write changes to disk")
    args = ap.parse_args()

    content_dir = Path(args.content_dir).expanduser().resolve()
    rewrites_path = Path(args.rewrites).expanduser().resolve()
    rewrites = json.loads(rewrites_path.read_text(encoding="utf-8"))
    if not isinstance(rewrites, dict):
        raise RuntimeError("Rewrites file must be a JSON object mapping old_url to new_url.")

    files_changed = 0
    total_replacements = 0

    for md in sorted(content_dir.glob("*.md")):
        before = md.read_text(encoding="utf-8")
        after, n = _apply_to_text(before, rewrites)
        if n:
            files_changed += 1
            total_replacements += n
            if args.apply:
                md.write_text(after, encoding="utf-8")

    mode = "APPLIED" if args.apply else "DRY_RUN"
    print(
        json.dumps(
            {
                "mode": mode,
                "files_changed": files_changed,
                "replacement_batches": total_replacements,
                "content_dir": str(content_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

