#!/usr/bin/env bash
# Validate the plugin as it would be installed: a copy without the dev venv, e2e homes or caches.
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${TMPDIR:-/tmp}/rung-validate"
rm -rf "$OUT" && mkdir -p "$OUT"
rsync -a --exclude .git --exclude .venv --exclude .e2e --exclude __pycache__ --exclude .pytest_cache \
  "$R/" "$OUT/rung/"
HERMES="${HERMES:-$HOME/.hermes/hermes-agent/venv/bin/hermes}"
env -u PYTHONPATH "$HERMES" plugins validate "$OUT/rung"
