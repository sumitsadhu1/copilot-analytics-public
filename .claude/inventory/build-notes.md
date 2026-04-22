# Build & Preview Notes

## Build Step

**There is no build step.** The site is hand-authored static HTML. No Jekyll `_config.yml`, no `package.json` with build scripts, no Gemfile, no Makefile.

GitHub Pages serves the repo root directly from the `main` branch.

## How to Preview Locally

Start a local HTTP server from the repo root:

```bash
cd /Users/sumitsadhu/Projects/copilot-analytics-public
python3 -m http.server 8000
```

Then open `http://localhost:8000/` in a browser.

**Note:** The search index (`assets/search-index.json`) requires the file to be served over HTTP — opening `index.html` directly via `file://` will cause CORS errors for the XHR search-index load.

## CSS

All pages under `1-strategy/`, `2-setup/`, `3-operate/`, `4-reference/` use the shared stylesheet at `assets/docs-style.css` (linked via `<link rel="stylesheet" href="../assets/docs-style.css">`).

The landing page (`index.html`) has its own inline `<style>` block — no external stylesheet.

Artifact pages (`artifacts/*.html`) and docs pages (`docs/**/*.html`) have their own inline styles — they don't share `docs-style.css`.

## JavaScript

- **Landing page filter/search JS** is inline in `index.html` at the bottom of `<body>`.
  - `filterCards(role, btn)` — role filter
  - `applyFilters()` — applies role + search term filtering
  - `deepSearch(term)` — searches `assets/search-index.json`
  - `switchLayer(layer, btn)` — layer tab navigation
  - `toggleDecision()` — collapse/expand the "What do you need?" table
  - Topic pill click handler — sets search term and triggers deep search
- No external JS files.
- No framework dependencies.

## Landing Page Navigation Components

1. **Role filter bar** — "I am a:" with 6 buttons (Show All, IT Admin, Business Leader, Analyst, Governance/Security, Finance/Licensing). Filters cards by `data-roles` attribute.
2. **Topic pill navigator** — 16 topic chips (Dashboard, Partitions, Assisted Hours, Power BI, Agents, VFAM, Org Data, Sentiment, Delegation, Billing, ROI, Multi-Agency, Privacy, Templates, Meetings & Focus, Licensing). Triggers deep search against `search-index.json`.
3. **"What do you need?" decision table** — collapsible table mapping 14 tasks to guide links.
4. **Layer tab navigation** — 4 tabs (Strategy, Setup, Operate, Reference) switching between card panels.
5. **Card grid** — 15 cards (3 Strategy + 4 Setup + 4 Operate + 4 Reference) + 1 Tool card in a separate section. Each card has badge, title, description, meta (version + Layer), role tags, and CTA link.
6. **Deep search results** — dropdown showing matching sections from `search-index.json` when a topic pill is active.

## PDF Regeneration

```bash
cd /Users/sumitsadhu/Projects/copilot-analytics-public
./scripts/generate_all_pdfs.sh
```

## Search Index Regeneration

```bash
cd /Users/sumitsadhu/Projects/copilot-analytics-public
python3 scripts/build_search_index.py
```
