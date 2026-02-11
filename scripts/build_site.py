#!/usr/bin/env python3
"""
Build a static Lexicity site into ./dist from the ODT source.

Outputs:
  dist/index.html, dist/styles.css, dist/app.js  (copied from ./site)
  dist/data/lexicity.json                      (generated from ODT)
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from odt_to_lexicity_json import convert_odt_to_json  # type: ignore


def _copy_tree(src_dir: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    for p in src_dir.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(src_dir)
        out = dst_dir / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--odt",
        default=str(Path(__file__).resolve().parents[1] / "Lexicity All Languages.odt"),
        help="Path to ODT source",
    )
    ap.add_argument(
        "--site-dir",
        default=str(Path(__file__).resolve().parents[1] / "site"),
        help="Directory containing static site template files",
    )
    ap.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parents[1] / "dist"),
        help="Output directory (static build)",
    )
    args = ap.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    odt_path = Path(args.odt).expanduser().resolve()
    site_dir = Path(args.site_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()

    if not odt_path.exists():
        raise FileNotFoundError(f"ODT not found: {odt_path}")
    if not site_dir.exists():
        raise FileNotFoundError(f"site dir not found: {site_dir}")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # copy static template
    _copy_tree(site_dir, out_dir)

    # generate data json
    data = convert_odt_to_json(odt_path)
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "lexicity.json").write_text(
        __import__("json").dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # small build marker for debugging deploys
    (out_dir / "data" / "build.txt").write_text(
        f"Built from {odt_path.name}\n", encoding="utf-8"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

