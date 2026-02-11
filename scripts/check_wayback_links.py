#!/usr/bin/env python3
"""
Probe Wayback-wrapped links and decide whether they can be replaced by a clean direct URL.

Strategy:
- For each Wayback link, extract original URL.
- Probe original (prefer https variant when original is http).
- If reachable (HTTP 200..399), suggest replacing the Wayback URL with the final direct URL.
- Otherwise, keep the Wayback URL.

Outputs:
- ./link_audit/wayback_check_results.csv
- ./link_audit/wayback_rewrite_suggestions.json
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import ssl
import urllib.error
import urllib.request


def _extract_wayback_original(url: str) -> Optional[str]:
    # mirrored from link_audit.py behavior
    if "web.archive.org/web/" not in url:
        return None
    try:
        parts = url.split("/web/", 1)[1]
        # parts: "<ts>/<orig...>"
        if "/" not in parts:
            return None
        orig = parts.split("/", 1)[1]
        if orig.startswith("http://") or orig.startswith("https://"):
            return orig
        return None
    except Exception:
        return None


def _prefer_https(url: str) -> str:
    try:
        p = urlparse(url)
        if p.scheme == "http":
            return urlunparse(p._replace(scheme="https"))
        return url
    except Exception:
        return url


def _probe(url: str, *, timeout_s: float) -> Tuple[Optional[int], str, str]:
    """
    Returns (status_code, final_url, error).
    """
    headers = {
        "User-Agent": "lexicity-link-check/1.0 (+https://example.invalid)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        ctx = ssl.create_default_context()

        # Try HEAD first.
        req = urllib.request.Request(url, headers=headers, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
                code = getattr(resp, "status", None) or resp.getcode()
                final_url = resp.geturl()
                if code in (405, 403) or code >= 500:
                    raise urllib.error.HTTPError(final_url, code, "HEAD not allowed or server error", resp.headers, None)
                return int(code), str(final_url), ""
        except urllib.error.HTTPError as he:
            # Fallback to GET; many sites dislike HEAD.
            req2 = urllib.request.Request(
                url,
                headers={**headers, "Range": "bytes=0-512"},
                method="GET",
            )
            with urllib.request.urlopen(req2, timeout=timeout_s, context=ctx) as resp2:
                code2 = getattr(resp2, "status", None) or resp2.getcode()
                final_url2 = resp2.geturl()
                # Read small chunk to ensure connection is usable
                try:
                    resp2.read(512)
                except Exception:
                    pass
                return int(code2), str(final_url2), ""
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, ValueError, OSError, ConnectionError) as e:
        return None, "", f"{type(e).__name__}: {e}"


@dataclass
class Result:
    wayback_url: str
    original_url: str
    probed_url: str
    status: str
    final_url: str
    decision: str  # keep_wayback | replace_with_final | replace_with_original
    error: str = ""


def _cache_key(probed_url: str) -> str:
    return probed_url


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-csv", default=str(root / "link_audit" / "link_audit_rows.csv"))
    ap.add_argument("--out-dir", default=str(root / "link_audit"))
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--sleep", type=float, default=0.0, help="Optional delay per probe (seconds)")
    ap.add_argument("--max-workers", type=int, default=24, help="Concurrent probes")
    ap.add_argument(
        "--retry-errors",
        action="store_true",
        help="Re-probe URLs whose cached status is 'error'",
    )
    ap.add_argument("--max", type=int, default=0, help="Max Wayback links to check (0=all)")
    args = ap.parse_args()

    in_csv = Path(args.in_csv).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, str]] = []
    with in_csv.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)

    wayback_rows = [r for r in rows if r.get("kind") == "wayback"]
    if args.max and args.max > 0:
        wayback_rows = wayback_rows[: args.max]

    # Load/maintain a cache so we probe each original URL at most once.
    cache_path = out_dir / "wayback_probe_cache.json"
    cache: Dict[str, Dict[str, str]] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            if not isinstance(cache, dict):
                cache = {}
        except Exception:
            cache = {}

    # Map each wayback URL to original URL and probe candidates.
    wb_to_orig: Dict[str, str] = {}
    wb_to_probes: Dict[str, List[str]] = {}
    pre_results: List[Result] = []

    for row in wayback_rows:
        wb = row["url"]
        orig = row.get("wayback_original") or _extract_wayback_original(wb) or ""
        if not orig:
            pre_results.append(
                Result(
                    wayback_url=wb,
                    original_url="",
                    probed_url="",
                    status="unknown",
                    final_url="",
                    decision="keep_wayback",
                    error="Could not extract original URL",
                )
            )
            continue
        if "web.archive.org/web/" in orig:
            pre_results.append(
                Result(
                    wayback_url=wb,
                    original_url=orig,
                    probed_url="",
                    status="nested_wayback",
                    final_url="",
                    decision="keep_wayback",
                    error="Original URL is itself a Wayback URL",
                )
            )
            continue
        wb_to_orig[wb] = orig
        probes: List[str] = []
        # Try https first when original is http, but fall back to http if https fails.
        if orig.startswith("http://"):
            probes.append(_prefer_https(orig))
            probes.append(orig)
        else:
            probes.append(orig)
        wb_to_probes[wb] = probes

    # Determine which probe URLs need work.
    unique_probe_urls = sorted({u for probes in wb_to_probes.values() for u in probes})
    to_probe = []
    for u in unique_probe_urls:
        ck = _cache_key(u)
        if ck not in cache:
            to_probe.append(u)
        elif args.retry_errors and cache.get(ck, {}).get("status") == "error":
            to_probe.append(u)

    def run_one(u: str) -> Tuple[str, Optional[int], str, str]:
        try:
            code, final, err = _probe(u, timeout_s=args.timeout)
            if args.sleep:
                time.sleep(args.sleep)
            return u, code, final, err
        except Exception as e:
            return u, None, "", f"{type(e).__name__}: {e}"

    if to_probe:
        with ThreadPoolExecutor(max_workers=max(1, int(args.max_workers))) as ex:
            futs = [ex.submit(run_one, u) for u in to_probe]
            for fut in as_completed(futs):
                u, code, final, err = fut.result()
                cache[_cache_key(u)] = {
                    "status": str(code) if code is not None else "error",
                    "final_url": final or "",
                    "error": err or "",
                }

        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Build per-wayback-url results using cached probe data.
    results: List[Result] = []
    results.extend(pre_results)

    for wb, orig in wb_to_orig.items():
        probes = wb_to_probes.get(wb) or [orig]

        chosen_probe = probes[0]
        chosen_status = "error"
        chosen_final = ""
        chosen_error = ""

        # pick the first probe that returns 200..399
        for pu in probes:
            c = cache.get(_cache_key(pu), {})
            st = c.get("status", "error")
            fu = c.get("final_url", "")
            er = c.get("error", "")
            try:
                code_int = int(st)
            except Exception:
                code_int = None
            if code_int is not None and 200 <= code_int < 400:
                chosen_probe, chosen_status, chosen_final, chosen_error = pu, st, fu, ""
                break
            # keep best-effort info from first probe for reporting
            if pu == probes[0]:
                chosen_probe, chosen_status, chosen_final, chosen_error = pu, st, fu, er

        try:
            code_int = int(chosen_status)
        except Exception:
            code_int = None

        if code_int is not None and 200 <= code_int < 400:
            decision = "replace_with_final" if chosen_final and chosen_final != wb else "replace_with_original"
            results.append(
                Result(
                    wayback_url=wb,
                    original_url=orig,
                    probed_url=chosen_probe,
                    status=chosen_status,
                    final_url=chosen_final or orig,
                    decision=decision,
                    error="",
                )
            )
        else:
            results.append(
                Result(
                    wayback_url=wb,
                    original_url=orig,
                    probed_url=chosen_probe,
                    status=chosen_status,
                    final_url=chosen_final,
                    decision="keep_wayback",
                    error=chosen_error,
                )
            )

    # Write outputs
    out_csv = out_dir / "wayback_check_results.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "wayback_url",
                "original_url",
                "probed_url",
                "status",
                "final_url",
                "decision",
                "error",
            ],
        )
        w.writeheader()
        for r in results:
            w.writerow(asdict(r))

    suggestions: Dict[str, str] = {}
    for r in results:
        if r.decision in ("replace_with_final", "replace_with_original") and r.final_url:
            suggestions[r.wayback_url] = r.final_url

    (out_dir / "wayback_rewrite_suggestions.json").write_text(
        json.dumps(suggestions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "checked_wayback_links": len(results),
                "suggested_rewrites": len(suggestions),
                "unique_probes": len(unique_probe_urls),
                "probes_performed_now": len(to_probe),
                "out_csv": str(out_csv),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

