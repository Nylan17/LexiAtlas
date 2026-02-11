# LexiAtlas

LexiAtlas is a community-maintained directory of learning resources for ancient and historical languages, inspired by the original Lexicity.

For the remaining operational steps to go live (domain, DNS, Cloudflare Pages, GitHub push), see `LAUNCH_CHECKLIST.md`.

## Local setup

Prereqs:
- Python 3
- Node 18+ (or 20+)

Install JS deps:

```bash
cd lexicity/site
npm install
```

## Import content (ODT bootstrap → Markdown)

The ODT file is treated as an initial bootstrap artifact (scraped/archival reconstruction). Import it into canonical Markdown pages:

```bash
cd lexicity
python3 scripts/import_odt_to_markdown.py
```

This writes Markdown files to `lexicity/site/src/content/languages/`.

## Link cleanup (Wayback → direct where possible)

After importing, you can audit and (optionally) rewrite Wayback links to direct URLs where the original resources still exist.

```bash
cd lexicity
python3 scripts/link_audit.py
python3 scripts/check_wayback_links.py
```

This writes reports to `lexicity/link_audit/` (ignored by git). If the suggestions look good:

```bash
cd lexicity
python3 scripts/apply_link_rewrites.py --apply
```

See `LINK_MAINTENANCE.md` for the ongoing workflow, including the “Wayback-only” list location.

## Build + search index

```bash
cd lexicity/site
npm run build:pages
```

Output: `lexicity/site/dist/` (static site) including `dist/pagefind/` (search index).

## Preview locally (important)

Do not open the built HTML via `file://...` (root-absolute links like `/language/.../` won’t resolve correctly).

Instead:

```bash
cd lexicity/site
npm run build:pages
npm run preview
```

## Cloudflare Pages deploy (monorepo)

Create a Cloudflare Pages project pointed at your GitHub repo and set:

- **Build command**: `cd lexicity/site && npm ci && npm run build:pages`
- **Build output directory**: `lexicity/site/dist`

Optional environment variables:
- `SITE_URL`: your production URL (used for metadata; can be left unset initially)
- `PUBLIC_ISSUES_NEW_URL`: `https://github.com/Nylan17/LexiAtlas/issues/new` (for “Suggest link update”)
- `PUBLIC_ISSUES_URL`: `https://github.com/Nylan17/LexiAtlas/issues` (issue list)

## Licensing

- Code and site implementation: see `LICENSE` (MIT).
- Third‑party resources linked from the directory remain governed by their own rights/terms. See `CONTENT_NOTICE.md`.

## Attribution / takedown

See the site pages:
- `/credits/`
- `/usage/`

