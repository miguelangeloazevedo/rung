#!/usr/bin/env bash
# Smoke: a clean install of the committed plugin through `hermes plugins install`, then validate,
# list and drive the CLI. Uses a throwaway HERMES_HOME; never touches a real profile.
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"
HERMES="${HERMES_BIN:-$HOME/.hermes/hermes-agent/venv/bin/hermes}"
T="$(mktemp -d "${TMPDIR:-/tmp}/rung-clean-XXXX")"
export HERMES_HOME="$T/home"
unset PYTHONPATH
mkdir -p "$HERMES_HOME"
SHA="$(git -C "$R" rev-parse HEAD)"
[ -z "$(git -C "$R" status --porcelain)" ] || echo "note: uncommitted changes are not part of the install (installing $SHA)"
cd "$T"
"$HERMES" plugins install "file://$R" --ref "$SHA" --enable --yes-deps
"$HERMES" plugins validate "$HERMES_HOME/plugins/rung"
"$HERMES" plugins list | grep -E '^\S*\s*rung\s|│ rung ' | grep -q enabled
"$HERMES" rung --help >/dev/null
"$HERMES" rung projects
echo "SMOKE INSTALL PASS ($SHA, home $HERMES_HOME)"
