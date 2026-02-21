#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Prefer project Ruby toolchain if available.
if [ -d "/opt/homebrew/opt/ruby@3.1/bin" ]; then
  export PATH="/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/ruby@3.1/bin:$PATH"
fi

MODE="${1:-serve}"
shift || true

clean() {
  "$ROOT_DIR/scripts/clean_latex_artifacts.sh"
}

clean
trap clean EXIT

case "$MODE" in
  serve)
    bundle _2.5.11_ exec jekyll serve "$@"
    ;;
  build)
    bundle _2.5.11_ exec jekyll build "$@"
    ;;
  *)
    echo "Usage: scripts/site_local.sh [serve|build] [jekyll args...]"
    exit 2
    ;;
esac
