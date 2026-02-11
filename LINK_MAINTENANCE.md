# Link maintenance (Wayback vs direct)

This revival started from an archival snapshot, so many outbound resource links were imported as Wayback URLs.

## Goals

- Prefer **direct links** when the original resource is reachable today.
- Keep **Wayback links** when the original resource is dead, unstable, or rights-restricted.

## Current state (how to measure)

Generate a link inventory:

```bash
cd lexicity
python3 scripts/link_audit.py
```

This writes:
- `link_audit/link_audit_summary.json`
- `link_audit/link_audit_rows.csv`

## Remaining Wayback links report

Generate a human-readable “what’s left” report:

```bash
cd lexicity
python3 scripts/wayback_remaining_report.py
```

This writes `link_audit/wayback_remaining_report.md` (ignored by git).

## Wayback cleanup workflow

Probe Wayback originals and produce rewrite suggestions:

```bash
cd lexicity
python3 scripts/check_wayback_links.py --timeout 6 --max-workers 32
```

Then apply suggested rewrites:

```bash
cd lexicity
python3 scripts/apply_link_rewrites.py        # dry-run
python3 scripts/apply_link_rewrites.py --apply
```

### “Wayback-only” list for future investigation

After running the command above, **the remaining Wayback-only links** are the rows with `decision=keep_wayback` in:

- `link_audit/wayback_check_results.csv`

We keep this report out of git (it changes over time), but it’s the canonical list to work through.

## Rule-based rewrites (when probing isn’t feasible)

If automated probing can’t reach certain hosts (for example, network blocks), you can apply conservative
rule-based rewrites for trusted hosts:

```bash
cd lexicity
python3 scripts/rule_based_wayback_rewrites.py --apply
```

## HTTP → HTTPS upgrades

Some links may still be `http://`. Upgrade only when HTTPS works:

```bash
cd lexicity
python3 scripts/upgrade_http_to_https.py        # dry-run
python3 scripts/upgrade_http_to_https.py --apply
```

