#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

find cv/generated private/cv -type f \
  \( -name "*.aux" -o -name "*.fdb_latexmk" -o -name "*.fls" -o -name "*.log" -o -name "*.out" -o -name "*.synctex.gz" -o -name "*.toc" \) \
  -delete 2>/dev/null || true
