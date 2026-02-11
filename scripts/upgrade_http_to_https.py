#!/usr/bin/env python3
"""
Safely upgrade http:// links in Markdown content to https:// when HTTPS works.

Rules:
- Only replaces `http://...` with `https://...` if probing the https URL returns 200..399.
- Uses a small cache in ./link_audit/http_probe_cache.json to avoid repeated work.
- Defaults to dry-run; pass --apply to write changes.
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple


MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _probe(url: str, *, timeout_s: float) -> Tuple[Optional[int], str]:
    headers = {"User-Agent": "lexicity-http2https/1.0 (+https://example.invalid)"}
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=headers, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            return int(code), resp.geturl()
    except urllib.error.HTTPError as he:
        # If HEAD returns an HTTP error, keep the status code.
        # For 405-ish cases, try a tiny GET; otherwise accept the failure.
        if he.code not in (405, 403) and he.code < 500:
            return int(he.code), ""
        # Some sites reject HEAD; try a tiny GET.
        req2 = urllib.request.Request(
            url, headers={**headers, "Range": "bytes=0-256"}, method="GET"
        )
        try:
            with urllib.request.urlopen(req2, timeout=timeout_s, context=ctx) as resp2:
                code2 = getattr(resp2, "status", None) or resp2.getcode()
                try:
                    resp2.read(256)
                except Exception:
                    pass
                return int(code2), resp2.geturl()
        except urllib.error.HTTPError as he2:
            return int(he2.code), ""
    except Exception:
        return None, ""


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--content-dir",
        default=str(root / "site" / "src" / "content" / "languages"),
        help="Directory containing markdown files",
    )
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--max-workers", type=int, default=24)
    ap.add_argument("--sleep", type=float, default=0.0)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    content_dir = Path(args.content_dir).expanduser().resolve()
    out_dir = root / "link_audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_path = out_dir / "http_probe_cache.json"
    cache: Dict[str, Dict[str, str]] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            if not isinstance(cache, dict):
                cache = {}
        except Exception:
            cache = {}

    # Collect unique http:// link targets (avoid matching embedded http:// inside wayback URLs)
    files = sorted(content_dir.glob("*.md"))
    http_urls: List[str] = []
    for md in files:
        for line in md.read_text(encoding="utf-8").splitlines():
            for m in MD_LINK_RE.finditer(line):
                url = m.group(2).strip()
                if url.startswith("http://") and "web.archive.org/web/" not in url:
                    http_urls.append(url)
    http_urls = sorted(set(http_urls))

    to_probe = [u for u in http_urls if u not in cache]

    def run_one(u: str) -> Tuple[str, Optional[int], str]:
        https_u = "https://" + u[len("http://") :]
        code, final = _probe(https_u, timeout_s=args.timeout)
        if args.sleep:
            time.sleep(args.sleep)
        return u, code, final or ""

    if to_probe:
        with ThreadPoolExecutor(max_workers=max(1, int(args.max_workers))) as ex:
            futs = [ex.submit(run_one, u) for u in to_probe]
            for fut in as_completed(futs):
                try:
                    u, code, final = fut.result()
                except Exception:
                    # treat as not-upgradable
                    continue
                cache[u] = {
                    "https_status": str(code) if code is not None else "error",
                    "https_final": final,
                }
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Build rewrite map for safe upgrades
    rewrites: Dict[str, str] = {}
    for u, info in cache.items():
        st = info.get("https_status", "error")
        try:
            code = int(st)
        except Exception:
            code = None
        if code is not None and 200 <= code < 400:
            rewrites[u] = "https://" + u[len("http://") :]

    # Apply per-file
    files_changed = 0
    replacements = 0
    for md in files:
        before = md.read_text(encoding="utf-8")
        after = before
        for old, new in rewrites.items():
            if old in after:
                after = after.replace(old, new)
                replacements += 1
        if after != before:
            files_changed += 1
            if args.apply:
                md.write_text(after, encoding="utf-8")

    mode = "APPLIED" if args.apply else "DRY_RUN"
    print(
        json.dumps(
            {
                "mode": mode,
                "http_urls_found": len(http_urls),
                "safe_upgrades": len(rewrites),
                "files_changed": files_changed,
                "replacement_batches": replacements,
                "cache_path": str(cache_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

