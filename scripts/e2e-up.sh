#!/usr/bin/env bash
# Start the isolated end-to-end environment: a throwaway Hermes home with Rung linked in, a
# deterministic stub chat model, and the Hermes Desktop dev build on CDP 127.0.0.1:9222.
# Nothing here reads or writes the Rung data of a real profile.
#
#   scripts/e2e-up.sh          start (idempotent)
#   scripts/e2e-up.sh down     stop the dev build and the stub model
set -u
R="$(cd "$(dirname "$0")/.." && pwd)"
E2E="${RUNG_E2E_DIR:-$R/.e2e}"
HOME_DIR="$E2E/home"
UDATA="$E2E/userdata"
LOGS="$E2E/logs"
HA="${HERMES_AGENT_SRC:-$HOME/.hermes/hermes-agent}"
STUB_PORT="${RUNG_STUB_PORT:-18765}"
mkdir -p "$HOME_DIR/plugins" "$UDATA" "$LOGS"

stop() {
  for f in "$E2E"/*.pid; do
    [ -e "$f" ] || continue
    pid=$(cat "$f")
    pkill -TERM -P "$pid" 2>/dev/null
    kill -TERM "$pid" 2>/dev/null
    rm -f "$f"
  done
  # Everything that runs with this isolated home or user-data dir in its environment: vite,
  # Electron, the gateway and dashboard the Desktop spawned, Rung runner processes.
  victims=""
  for p in $(ps -axo pid=); do
    if ps eww -o command= -p "$p" 2>/dev/null | grep -qF -e "HERMES_HOME=$HOME_DIR" -e "HERMES_DESKTOP_USER_DATA_DIR=$UDATA" -e "--user-data-dir=$UDATA"; then
      victims="$victims $p"
    fi
  done
  for p in $(lsof -ti tcp:5174 2>/dev/null) $(lsof -ti tcp:9222 2>/dev/null) $(lsof -ti tcp:"$STUB_PORT" 2>/dev/null); do
    victims="$victims $p"
  done
  [ -n "$victims" ] && kill -TERM $victims 2>/dev/null
  for _ in $(seq 1 20); do
    alive=""
    for p in $victims; do kill -0 "$p" 2>/dev/null && alive="$alive $p"; done
    [ -z "$alive" ] && break
    sleep 0.5
  done
  [ -n "${alive:-}" ] && kill -KILL $alive 2>/dev/null
  return 0
}

if [ "${1:-}" = "down" ]; then
  stop
  echo "e2e environment stopped"
  exit 0
fi

# 1. Isolated Hermes home: Rung linked (the Desktop re-syncs desktop/plugin.js on every save).
ln -sfn "$R" "$HOME_DIR/plugins/rung"
[ -e "$HOME_DIR/hermes-agent" ] || ln -sfn "$HA" "$HOME_DIR/hermes-agent"
cat > "$HOME_DIR/config.yaml" <<YAML
model:
  default: rung-stub
  provider: custom
  base_url: http://127.0.0.1:$STUB_PORT/v1
  api_key: stub
  context_length: 200000
plugins:
  enabled:
    - rung
agent:
  max_turns: 6
compression:
  enabled: false
YAML

# 2. Stub chat model.
if ! curl -s -m 2 "http://127.0.0.1:$STUB_PORT/v1/models" >/dev/null; then
  nohup "$R/.venv/bin/python" "$R/tests/e2e/stub_model.py" --port "$STUB_PORT" >"$LOGS/stub-model.log" 2>&1 &
  echo $! > "$E2E/stub.pid"
fi

# 3. Desktop dev build against the isolated home.
if ! curl -s -m 2 http://127.0.0.1:9222/json/version >/dev/null; then
  (
    cd "$HA/apps/desktop" || exit 1
    export HERMES_HOME="$HOME_DIR" HERMES_DESKTOP_USER_DATA_DIR="$UDATA" PATH="$HA/venv/bin:$R/.venv/bin:$PATH"
    exec npm run dev >"$LOGS/desktop.log" 2>&1
  ) &
  echo $! > "$E2E/desktop.pid"
fi

for _ in $(seq 1 120); do
  curl -s -m 2 http://127.0.0.1:9222/json/version >/dev/null && break
  sleep 2
done
curl -s -m 2 http://127.0.0.1:9222/json/version >/dev/null || { echo "Desktop dev build did not open CDP; see $LOGS/desktop.log"; exit 1; }
echo "e2e environment up: HERMES_HOME=$HOME_DIR, CDP 127.0.0.1:9222, stub model :$STUB_PORT"
