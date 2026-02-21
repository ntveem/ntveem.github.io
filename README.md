# ntveem.github.io

Personal website source for GitHub Pages, built with Jekyll 4.

## Quick updates

1. Edit page content in:
   - `00-index.md` (home)
   - `01-index_research.md`
   - `02-index_publications.md`
   - `03-index_CV.md`
   - `04-index_contact.md`
2. Commit and push to `master` (or `main`).
3. GitHub Actions deploys automatically to Pages.

## Local preview

Prerequisites:
- Ruby `3.1.x` (see `.ruby-version`)
- Bundler `2.5.x`

Commands:

```bash
export PATH="/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/ruby@3.1/bin:$PATH"
bundle _2.5.11_ install
./scripts/site_local.sh serve
```

Then open: `http://127.0.0.1:4000`

For a one-off local build:

```bash
./scripts/site_local.sh build
```

Both commands auto-clean LaTeX auxiliary files in `cv/generated` and `private/cv`.

## Automation now enabled

- `/.github/workflows/pages.yml`
  - Deploys on push
  - Manual run via Actions tab
  - Weekly scheduled rebuild (Monday 09:00 UTC) to catch breakage early
- `/.github/dependabot.yml`
  - Weekly update PRs for GitHub Actions and Ruby gems
- `/.github/workflows/publications-sync.yml`
  - Daily ADS sync for `/02-index_publications.md`
  - Uses repository secret `ADS_API_TOKEN`

## ADS Publications Sync

Fetch canonical ADS data:

```bash
python scripts/sync_ads_data.py
```

Notes:
- `sync_ads_data.py` now backfills missing abstracts and stores them in `data/ads_publications.json`.
- Use `--refresh-abstracts` to re-fetch all abstracts from ADS.
- Use `--skip-abstracts` if you want metadata-only sync.
- Topic classification uses `data/topics.json` + `data/topic_overrides.json`.
- If `OPENAI_API_KEY` is set, topics are classified and saved per paper.
- Changing the topic list triggers automatic reclassification on the next run.
- Use `--skip-topics` to disable classification and `--refresh-topics` to force a full re-run.

Local preview (does not edit files):

```bash
python scripts/sync_publications.py --preview
```

Local write:

```bash
python scripts/sync_publications.py --write
```

GitHub setup for daily sync:

1. Go to repository **Settings → Secrets and variables → Actions**
2. Add a new repository secret named `ADS_API_TOKEN`
3. Add repository secret `OPENAI_API_KEY` (for topic auto-classification)
4. (Optional) Add repository variable `OPENAI_MODEL` (default in script: `gpt-4.1-mini`)
5. Paste your ADS/OpenAI token values
6. (Optional) Run **Actions → Sync Publications From ADS → Run workflow** once manually

## CV Automation

Canonical CV template (source of truth in this repo):
- `cv/source/myresume_master.tex`

Generated daily from ADS canonical data (`data/ads_publications.json`):
- Public TeX: `cv/generated/Tejaswi_CV_public.tex`
- Private TeX: `private/cv/Tejaswi_CV_private.tex`
- Public PDF (website): `assets/files/Tejaswi_CV.pdf`
- Private PDF (not published on website): `private/cv/Tejaswi_CV_private.pdf`

The public CV removes these sections:
- Current and Pending Support
- Graduate Committees
- Undergraduate Students Supervised
- Postdoctoral Scholars Supervised
- Other Supervision/Mentoring
- University Service

Local regeneration:

```bash
./scripts/sync_ads_pipeline.sh
```

Manual step-by-step (equivalent):

```bash
python scripts/sync_ads_data.py
python scripts/sync_publications.py --write
python scripts/sync_cv.py
```

## GitHub Pages settings

In repository settings, ensure:
- Source: **GitHub Actions**
- Custom domain (if used) is configured in repo settings and `CNAME`
