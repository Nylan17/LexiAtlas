#!/usr/bin/env python3
"""
Option A (incremental): convert per-section resource blobs in Markdown into a
more consistent, structured list format without changing the underlying links.

Heuristic:
- Within each section (## ...), treat standalone Markdown links as resource titles.
- Attach following paragraphs (until next link or heading) as Notes.
- Detect Format/Access tags from URL extension + note keywords.

Defaults to dry-run; pass --apply to write changes.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


LINK_LINE_RE = re.compile(r"^\s*\[([^\]]+)\]\((https?://[^)]+)\)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+")
FRONTMATTER_DELIM = "---"


FORMAT_BY_EXT = {
    ".pdf": "PDF",
    ".doc": "DOC",
    ".docx": "DOCX",
    ".txt": "TXT",
    ".djvu": "DJVU",
    ".ps": "PS",
    ".zip": "ZIP",
}


def detect_format(url: str, notes: str) -> Optional[str]:
    path = urlparse(url).path.lower()
    for ext, fmt in FORMAT_BY_EXT.items():
        if path.endswith(ext):
            return fmt
    n = (notes or "").lower()
    if "pdf" in n:
        return "PDF"
    if "word document" in n or "docx" in n:
        return "DOC"
    if "text file" in n:
        return "TXT"
    if "youtube" in url.lower() or "video" in n:
        return "Video"
    return None


def detect_access(notes: str) -> List[str]:
    n = (notes or "").lower()
    tags: List[str] = []
    if "register" in n or "registration" in n or "log in" in n:
        tags.append("Registration")
    if "subscription" in n or "institutional" in n or "pay" in n or "paywall" in n:
        tags.append("Subscription")
    if "java" in n:
        tags.append("Java")
    if "font" in n:
        tags.append("Font")
    if "chrome" in n or "translation" in n:
        # not truly access; keep out
        pass
    return tags


@dataclass
class Resource:
    title: str
    url: str
    notes: str = ""
    fmt: str = ""
    access: List[str] = None  # type: ignore[assignment]


def split_frontmatter(lines: List[str]) -> Tuple[List[str], List[str]]:
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        return [], lines
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIM:
            return lines[: i + 1], lines[i + 1 :]
    return [], lines


def normalize_whitespace(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s


def format_section(lines: List[str]) -> List[str]:
    """
    Given the body lines of a single section (excluding the heading),
    return formatted lines.
    """
    out: List[str] = []

    # If the section is explicitly empty, keep as-is.
    joined = "\n".join(lines).strip()
    if joined in ("(nothing available)", "(nothing available)."):
        return lines

    resources: List[Resource] = []
    buffer_other: List[str] = []

    def flush_other() -> None:
        nonlocal buffer_other
        if buffer_other:
            out.extend(buffer_other)
            buffer_other = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if HEADING_RE.match(line):
            # shouldn't happen inside section but treat as passthrough
            flush_other()
            out.append(line)
            i += 1
            continue

        m = LINK_LINE_RE.match(line)
        if m:
            flush_other()
            title, url = m.group(1).strip(), m.group(2).strip()
            # collect notes until next link or heading
            note_lines: List[str] = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if HEADING_RE.match(nxt) or LINK_LINE_RE.match(nxt):
                    break
                # skip blank lines around notes
                if nxt.strip():
                    note_lines.append(nxt.strip())
                j += 1
            notes = normalize_whitespace(" ".join(note_lines))
            fmt = detect_format(url, notes) or ""
            access = detect_access(notes)
            resources.append(Resource(title=title, url=url, notes=notes, fmt=fmt, access=access))
            i = j
            continue

        # Keep non-resource text verbatim (rare, but e.g. intro paragraph)
        buffer_other.append(line)
        i += 1

    # If we found resources, rewrite into a consistent list format.
    if resources:
        # Keep any preamble we flushed into out, then add a blank line if needed.
        if out and out[-1].strip():
            out.append("")
        for r in resources:
            out.append(f"- [{r.title}]({r.url})")
            if r.fmt:
                out.append(f"  - Format: {r.fmt}")
            if r.access:
                out.append(f"  - Access: {', '.join(r.access)}")
            if r.notes:
                out.append(f"  - Notes: {r.notes}")
            out.append("")
        # drop trailing blank line
        while out and out[-1] == "":
            out.pop()
        return out

    # Otherwise return original lines
    return lines


def format_file(path: Path) -> Tuple[str, bool]:
    lines = path.read_text(encoding="utf-8").splitlines()
    fm, body = split_frontmatter(lines)

    out: List[str] = []
    if fm:
        out.extend(fm)
        # keep single blank line after frontmatter
        if body and body[0].strip() != "":
            out.append("")

    # Walk body: headings are kept; section bodies formatted
    i = 0
    while i < len(body):
        line = body[i]
        hm = HEADING_RE.match(line)
        if hm and hm.group(1) == "##":
            out.append(line)
            out.append("")
            # collect until next ## heading
            j = i + 1
            section_lines: List[str] = []
            while j < len(body):
                if HEADING_RE.match(body[j]) and body[j].startswith("## "):
                    break
                section_lines.append(body[j])
                j += 1
            # trim leading/trailing blank lines in section
            while section_lines and not section_lines[0].strip():
                section_lines.pop(0)
            while section_lines and not section_lines[-1].strip():
                section_lines.pop()
            out.extend(format_section(section_lines))
            out.append("")
            i = j
            continue

        out.append(line)
        i += 1

    # tidy trailing whitespace/blank lines
    while out and not out[-1].strip():
        out.pop()
    out.append("")

    new_text = "\n".join(out)
    changed = new_text != path.read_text(encoding="utf-8")
    return new_text, changed


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--content-dir",
        default=str(root / "site" / "src" / "content" / "languages"),
    )
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of files processed (0=all)")
    args = ap.parse_args()

    content_dir = Path(args.content_dir).expanduser().resolve()
    files = sorted(content_dir.glob("*.md"))
    if args.limit and args.limit > 0:
        files = files[: args.limit]

    changed_files = 0
    for md in files:
        new_text, changed = format_file(md)
        if changed:
            changed_files += 1
            if args.apply:
                md.write_text(new_text, encoding="utf-8")

    mode = "APPLIED" if args.apply else "DRY_RUN"
    print(f"{mode}: {changed_files}/{len(files)} file(s) would change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

