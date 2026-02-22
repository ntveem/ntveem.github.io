#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPILE_PDF=1
if [[ "${1:-}" == "--no-pdf" ]]; then
  COMPILE_PDF=0
fi

python3 scripts/sync_ads_data.py
python3 scripts/sync_publications.py --write
python3 scripts/sync_cv.py
python3 scripts/sync_group.py

if [[ "$COMPILE_PDF" -eq 1 ]]; then
  if ! command -v latexmk >/dev/null 2>&1; then
    echo "latexmk not found. Install MacTeX/TeX Live or run with --no-pdf." >&2
    exit 3
  fi

  latexmk -pdf -interaction=nonstopmode -halt-on-error \
    -output-directory=cv/generated cv/generated/Tejaswi_CV_public.tex
  latexmk -pdf -interaction=nonstopmode -halt-on-error \
    -output-directory=private/cv private/cv/Tejaswi_CV_private.tex

  cp -f cv/generated/Tejaswi_CV_public.pdf assets/files/Tejaswi_CV.pdf
fi

./scripts/clean_latex_artifacts.sh

echo "ADS sync pipeline complete."
