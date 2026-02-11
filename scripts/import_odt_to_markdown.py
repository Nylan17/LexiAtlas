#!/usr/bin/env python3
"""
One-time (or occasional) importer: ODT -> JSON -> Markdown content files for the Astro site.

Writes one Markdown file per language into `site/src/content/languages/`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from odt_to_lexicity_json import convert_odt_to_json  # type: ignore


def _yaml_str(s: str) -> str:
    # Safe enough for our strings; quotes and preserves unicode.
    return json.dumps(s, ensure_ascii=False)


def _tokens_to_md(tokens: List[Dict[str, Any]]) -> str:
    out: List[str] = []
    for t in tokens or []:
        tt = t.get("t")
        if tt == "text":
            out.append(t.get("v", ""))
        elif tt == "a":
            text = (t.get("v") or "").strip()
            href = (t.get("href") or "").strip()
            if text and href:
                out.append(f"[{text}]({href})")
            elif text:
                out.append(text)
        else:
            # unknown token: best-effort text
            v = t.get("v")
            if isinstance(v, str):
                out.append(v)
    s = "".join(out)
    s = s.replace("\u00a0", " ")
    # normalize whitespace but keep single newlines if present
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def _write_language_md(lang: Dict[str, Any], out_dir: Path, *, overwrite: bool) -> Path:
    title = (lang.get("title") or "Untitled").strip()
    slug = (lang.get("slug") or "untitled").strip()
    blocks = lang.get("blocks") or []

    # Skip the full-document backup/TOC page; it's not useful in the revived UI.
    if slug == "lexicityall-languages" or title.lower().startswith("lexicity/"):
        raise RuntimeError("SkipLexicityAllLanguages")

    md_lines: List[str] = []
    md_lines.append("---")
    md_lines.append(f"title: {_yaml_str(title)}")
    # NOTE: We intentionally do NOT write a `slug` field here.
    # Astro derives entry slugs/ids from the file path; writing `slug` can
    # create confusing collisions and warnings during content syncing.
    md_lines.append('source: "Imported from archival snapshot (ODT bootstrap)"')
    md_lines.append('attribution: "Original Lexicity creator (unknown/verify)"')
    md_lines.append("---")
    md_lines.append("")

    for b in blocks:
        btype = b.get("type")
        if btype == "h":
            level = int(b.get("level") or 1)
            text = (b.get("text") or "").strip()
            if not text:
                continue
            if level == 1:
                # file boundary heading; skip inside body
                continue
            hashes = "#" * max(2, min(level, 6))
            md_lines.append(f"{hashes} {text}")
            md_lines.append("")
            continue

        if btype == "p":
            tokens = b.get("tokens") or []
            s = _tokens_to_md(tokens)
            # Drop common table column headers emitted as standalone paragraphs.
            if s in ("Resource", "Description"):
                continue
            if s:
                md_lines.append(s)
                md_lines.append("")
            continue

        if btype == "list":
            items = b.get("items") or []
            for it in items:
                toks = it.get("tokens") or []
                s = _tokens_to_md(toks) or (it.get("text") or "")
                s = re.sub(r"\s*\n\s*", " ", str(s)).strip()
                if s:
                    md_lines.append(f"- {s}")
            if items:
                md_lines.append("")
            continue

    # trim trailing blank lines
    while md_lines and md_lines[-1] == "":
        md_lines.pop()
    md_lines.append("")

    out_path = out_dir / f"{slug}.md"
    if out_path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {out_path}")
    out_path.write_text("\n".join(md_lines), encoding="utf-8")
    return out_path


def main(argv: List[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--odt",
        default=str(root / "Lexicity All Languages.odt"),
        help="Path to ODT bootstrap source",
    )
    ap.add_argument(
        "--out-dir",
        default=str(root / "site" / "src" / "content" / "languages"),
        help="Output directory for language markdown files",
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing markdown files",
    )
    args = ap.parse_args(argv)

    odt_path = Path(args.odt).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    data = convert_odt_to_json(odt_path)
    languages = data.get("languages") or []
    if not isinstance(languages, list) or not languages:
        raise RuntimeError("No languages found in ODT import.")

    written: List[Path] = []
    for lang in languages:
        if not isinstance(lang, dict):
            continue
        try:
            written.append(_write_language_md(lang, out_dir, overwrite=args.overwrite))
        except RuntimeError as e:
            if str(e) == "SkipLexicityAllLanguages":
                continue
            raise

    # remove placeholder .gitkeep if present
    keep = out_dir / ".gitkeep"
    if keep.exists():
        keep.unlink()

    print(f"Wrote {len(written)} language file(s) to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

