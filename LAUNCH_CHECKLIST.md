# Launch / Deploy checklist (Lexicity revival)

This doc tracks the remaining operational work to get the site live on a new domain using Cloudflare Pages.

## Build + content workflow (quick reference)

- **Canonical content**: Markdown files in `lexicity/site/src/content/languages/`
- **Bootstrap import** (ODT → Markdown):

```bash
cd lexicity
python3 scripts/import_odt_to_markdown.py
```

- **Build + search index** (Astro + Pagefind):

```bash
cd lexicity/site
npm ci
npm run build:pages
```

- **Preview locally** (serve over HTTP; don’t use `file://`):

```bash
cd lexicity/site
npm run preview
```

## Remaining TODOs before public launch

### Repo / GitHub

- [ ] Create a dedicated GitHub repository (recommended) or decide monorepo strategy
- [ ] Add the remote and push
  - Example:

```bash
cd /Users/tannerlund/src
git remote add origin <your-github-repo-ssh-or-https>
git add lexicity
git commit -m "Initial Lexicity revival site"
git push -u origin master
```

- [ ] Enable branch protections (optional but recommended)
  - Require PRs for main branch
  - Require status checks (build) once CI exists

### Cloudflare Pages

- [ ] Create a Cloudflare Pages project connected to the GitHub repo
- [ ] Configure build settings
  - **Build command**: `cd lexicity/site && npm ci && npm run build:pages`
  - **Output directory**: `lexicity/site/dist`
  - **Node version**: set to 18 or 20 (either via Cloudflare setting or env var)
- [ ] Add environment variables (optional)
  - `SITE_URL`: `https://<your-domain>` (used by `astro.config.mjs` if you want absolute URLs)
- [ ] Confirm first deploy succeeds and `/search/` works (Pagefind assets present at `/pagefind/…`)

### Domain + DNS

- [ ] Pick and **buy a new domain** for the revival (or use a subdomain of an existing domain)
  - Recommendation: use a dedicated domain (clear separation from personal site)
- [ ] Decide whether Cloudflare will be the DNS provider
  - Easiest path: move/keep DNS in Cloudflare so Pages domain setup is automatic
- [ ] Attach domain in Cloudflare Pages → follow the DNS prompts
  - You’ll typically add `CNAME` records (subdomain) or follow Cloudflare’s apex-domain instructions
- [ ] Verify HTTPS is issued (Cloudflare handles this)

### Attribution / policy (must-do content edits)

- [ ] Fill in `site/src/pages/credits.astro` with verified original creator attribution (if/when known)
- [ ] Add a real contact path in `site/src/pages/usage.astro`
  - Email address and/or GitHub issues link
- [ ] (Optional) Add a short “What changed since the archive snapshot?” section

### QA (fast but important)

- [ ] Spot-check several language pages for formatting, links, and heading structure
- [ ] Confirm search returns results and excerpts look sane
- [ ] Mobile layout: browse list usable at <900px width
- [ ] Basic SEO: titles/descriptions look good in browser tabs and link previews (optional for V1)

## Post-launch TODOs (nice-to-have)

- [ ] Add analytics (Cloudflare Web Analytics or similar)
- [ ] Add sitemap + robots.txt
- [ ] Add a contribution guide (PR template, style guidelines for entries)
- [ ] Consider a browser-based editor (Decap CMS) if you want non-technical editing

