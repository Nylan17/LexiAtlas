#!/usr/bin/env python3
"""
Convert Lexicity ODT content into a JSON structure suitable for a static site.

ODT is a ZIP; main document body is in content.xml.
We parse a conservative subset of OpenDocument text elements:
- text:h (headings)
- text:p (paragraphs)
- text:list / text:list-item (lists)
- text:a (links)

Output structure (high level):
{
  "meta": {...},
  "languages": [
    {"title": "...", "slug": "...", "blocks": [ ... ] }
  ]
}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import xml.etree.ElementTree as ET


NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    # present in many ODTs; safe to include for tag checks
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
}


def _tag(ns: str, local: str) -> str:
    return f"{{{NS[ns]}}}{local}"


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s or "untitled"


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


Token = Dict[str, Any]  # {"t": "text", "v": "..."} | {"t": "a", "v": "...", "href": "..."}


def parse_inline_tokens(node: ET.Element) -> List[Token]:
    """
    Flatten inline content to a token stream, preserving hyperlinks.
    """
    tokens: List[Token] = []

    def emit_text(txt: Optional[str]) -> None:
        if txt:
            v = txt
            if v:
                tokens.append({"t": "text", "v": v})

    def walk(n: ET.Element) -> None:
        emit_text(n.text)

        for child in list(n):
            if child.tag == _tag("text", "a"):
                href = child.attrib.get(_tag("xlink", "href")) or child.attrib.get("href") or ""
                link_text = _collect_all_text(child)
                link_text = _norm_ws(link_text)
                if link_text:
                    tokens.append({"t": "a", "v": link_text, "href": href})
                # Don't walk the link subtree; we already captured its full text.
                emit_text(child.tail)
                continue

            # common inline wrappers: text:span, text:s, text:line-break, etc.
            if child.tag in (
                _tag("text", "span"),
                _tag("text", "s"),
                _tag("text", "soft-page-break"),
                _tag("text", "line-break"),
            ):
                walk(child)
                emit_text(child.tail)
                continue

            # unknown inline-ish tag: fall back to text extraction
            walk(child)
            emit_text(child.tail)

    walk(node)

    # normalize whitespace within text tokens (but keep token boundaries)
    out: List[Token] = []
    for t in tokens:
        if t["t"] == "text":
            v = t.get("v", "")
            v = v.replace("\u00a0", " ")
            out.append({"t": "text", "v": v})
        else:
            out.append(t)
    return _coalesce_text_tokens(out)


def _coalesce_text_tokens(tokens: List[Token]) -> List[Token]:
    out: List[Token] = []
    buf: List[str] = []

    def flush() -> None:
        nonlocal buf
        if buf:
            out.append({"t": "text", "v": "".join(buf)})
            buf = []

    for tok in tokens:
        if tok["t"] == "text":
            buf.append(tok.get("v", ""))
        else:
            flush()
            out.append(tok)
    flush()
    return out


def tokens_to_plain_text(tokens: List[Token]) -> str:
    parts: List[str] = []
    for t in tokens:
        if t["t"] == "text":
            parts.append(t.get("v", ""))
        elif t["t"] == "a":
            parts.append(t.get("v", ""))
    return _norm_ws("".join(parts))


def _collect_all_text(node: ET.Element) -> str:
    # ElementTree's itertext() gives us a decent baseline for most tags
    return "".join(node.itertext())


def _get_outline_level(h: ET.Element) -> int:
    lvl = h.attrib.get(_tag("text", "outline-level")) or h.attrib.get("outline-level")
    try:
        return int(lvl) if lvl else 1
    except ValueError:
        return 1


def iter_blocks(text_root: ET.Element) -> Iterable[Dict[str, Any]]:
    """
    Yield blocks in document order. Each block has:
      - type: "h" | "p" | "list"
      - tokens (for p/h items) or items(list[str/tokens])
    """
    def emit_from_node(node: ET.Element) -> Iterable[Dict[str, Any]]:
        for child in list(node):
            if child.tag == _tag("text", "h"):
                tokens = parse_inline_tokens(child)
                yield {
                    "type": "h",
                    "level": _get_outline_level(child),
                    "tokens": tokens,
                    "text": tokens_to_plain_text(tokens),
                }
                continue

            if child.tag == _tag("text", "p"):
                tokens = parse_inline_tokens(child)
                plain = tokens_to_plain_text(tokens)
                if plain:
                    yield {"type": "p", "tokens": tokens, "text": plain}
                continue

            if child.tag == _tag("text", "list"):
                items: List[Dict[str, Any]] = []
                for li in child.findall("text:list-item", NS):
                    # list item may contain multiple paragraphs; we join them with newlines
                    paras = li.findall("text:p", NS)
                    if paras:
                        toks: List[Token] = []
                        for p in paras:
                            pt = parse_inline_tokens(p)
                            if toks:
                                toks.append({"t": "text", "v": "\n"})
                            toks.extend(pt)
                        items.append({"tokens": toks, "text": tokens_to_plain_text(toks)})
                    else:
                        raw = _norm_ws(_collect_all_text(li))
                        if raw:
                            items.append({"tokens": [{"t": "text", "v": raw}], "text": raw})
                if items:
                    yield {"type": "list", "items": items}
                # do not recurse into list children (avoids duplicating item paragraphs)
                continue

            # Recurse into structural containers so we capture content inside tables/sections.
            # ODTs often store most content inside table cells.
            if child.tag in (
                _tag("text", "section"),
                _tag("text", "soft-page-break"),
                _tag("table", "table"),
                _tag("table", "table-row"),
                _tag("table", "table-cell"),
                _tag("table", "covered-table-cell"),
            ):
                yield from emit_from_node(child)
                continue

            # Default: keep descending; this is conservative and helps with unexpected wrappers.
            yield from emit_from_node(child)

    yield from emit_from_node(text_root)


def group_into_languages(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Heuristic: treat outline-level 1 headings as language boundaries.
    If no level-1 heading exists, return a single "All languages" section.
    """
    has_lvl1 = any(b.get("type") == "h" and b.get("level") == 1 for b in blocks)
    if not has_lvl1:
        return [
            {
                "title": "All languages",
                "slug": "all-languages",
                "blocks": blocks,
            }
        ]

    languages: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for b in blocks:
        if b.get("type") == "h" and b.get("level") == 1:
            title = b.get("text") or "Untitled"
            current = {"title": title, "slug": slugify(title), "blocks": [b]}
            languages.append(current)
            continue

        if current is None:
            # content before first language heading; keep it as "Intro"
            current = {"title": "Intro", "slug": "intro", "blocks": []}
            languages.append(current)
        current["blocks"].append(b)

    # de-dupe slugs
    seen: Dict[str, int] = {}
    for lang in languages:
        s = lang["slug"]
        n = seen.get(s, 0)
        if n:
            lang["slug"] = f"{s}-{n+1}"
        seen[s] = n + 1

    return languages


def convert_odt_to_json(source_odt: Path) -> Dict[str, Any]:
    if not source_odt.exists():
        raise FileNotFoundError(str(source_odt))

    with zipfile.ZipFile(source_odt, "r") as z:
        try:
            content_xml = z.read("content.xml")
        except KeyError as e:
            raise RuntimeError("ODT is missing content.xml") from e

    # Some ODTs are UTF-8; ElementTree handles the XML declaration.
    root = ET.fromstring(content_xml)
    text_root = root.find("office:body/office:text", NS)
    if text_root is None:
        raise RuntimeError("Could not locate office:body/office:text in content.xml")

    blocks = list(iter_blocks(text_root))
    languages = group_into_languages(blocks)

    now = datetime.now(timezone.utc).isoformat()
    return {
        "meta": {
            "generated_at": now,
            "source_file": source_odt.name,
            "block_count": len(blocks),
            "language_count": len(languages),
        },
        "languages": languages,
    }


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Path to Lexicity ODT file")
    ap.add_argument("--out", dest="out_path", required=True, help="Path to write JSON")
    args = ap.parse_args(argv)

    src = Path(args.in_path).expanduser().resolve()
    out = Path(args.out_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    data = convert_odt_to_json(src)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

