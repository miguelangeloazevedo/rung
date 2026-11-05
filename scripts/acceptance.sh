#!/usr/bin/env bash
# Rung v1 acceptance. Frozen: see docs/acceptance.md. Exit 0 only when UC01 to UC12 all pass.
set -u
cd "$(dirname "$0")/.."
PY="${RUNG_PY:-.venv/bin/python}"
EVID="evidence"
mkdir -p "$EVID"
START="$EVID/.run-start"
touch "$START"
sleep 1

if ! curl -s -m 3 http://127.0.0.1:9222/json/version >/dev/null; then
  echo "FAIL: Hermes Desktop dev build is not exposing CDP on 127.0.0.1:9222"
  exit 2
fi

pass=0
for n in 01 02 03 04 05 06 07 08 09 10 11 12; do
  files=(tests/e2e/test_uc${n}_*.py)
  if [ ! -e "${files[0]}" ]; then
    echo "UC${n} FAIL: no tests/e2e/test_uc${n}_*.py"
    continue
  fi
  xml="$EVID/uc${n}.xml"
  rm -f "$xml"
  "$PY" -m pytest -q -p no:cacheprovider "${files[@]}" --junitxml="$xml" >"$EVID/uc${n}.log" 2>&1
  rc=$?
  verdict=$("$PY" - "$xml" "$rc" <<'PYEOF'
import sys, xml.etree.ElementTree as ET
path, rc = sys.argv[1], int(sys.argv[2])
try:
    root = ET.parse(path).getroot()
except Exception as e:
    print(f"no junit report ({e})"); sys.exit()
suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
t = sum(int(s.get("tests", 0)) for s in suites)
f = sum(int(s.get("failures", 0)) for s in suites)
e = sum(int(s.get("errors", 0)) for s in suites)
k = sum(int(s.get("skipped", 0)) for s in suites)
if rc == 0 and t > 0 and f == 0 and e == 0 and k == 0:
    print(f"ok {t}")
else:
    print(f"tests={t} failures={f} errors={e} skipped={k} exit={rc}")
PYEOF
)
  shot="$EVID/uc${n}.png"
  if [[ "$verdict" != ok* ]]; then
    echo "UC${n} FAIL: $verdict (log $EVID/uc${n}.log)"
  elif [ ! -s "$shot" ] || [ ! "$shot" -nt "$START" ]; then
    echo "UC${n} FAIL: no fresh screenshot $shot"
  else
    echo "UC${n} PASS (${verdict#ok } tests)"
    pass=$((pass + 1))
  fi
done

echo "ACCEPTANCE: ${pass}/12"
[ "$pass" -eq 12 ]
