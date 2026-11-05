#!/usr/bin/env bash
# Rung acceptance, stage 3. Frozen: see docs/acceptance-3.md.
# Exit 0 only when UC23 to UC29 all pass and every ID in docs/use-cases-3.md is named by a passing test.
set -u
cd "$(dirname "$0")/.."
PY="${RUNG_PY:-.venv/bin/python}"
EVID="evidence"
OUT="$EVID/acceptance-3"
mkdir -p "$EVID" "$OUT"
START="$OUT/.run-start"
touch "$START"
sleep 1

if ! curl -s -m 3 http://127.0.0.1:9222/json/version >/dev/null; then
  echo "FAIL: Hermes Desktop dev build is not exposing CDP on 127.0.0.1:9222"
  exit 2
fi

FIRST=23
LAST=29
TOTAL=$((LAST - FIRST + 1))
pass=0
for n in $(seq "$FIRST" "$LAST"); do
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
echo "ACCEPTANCE-3: ${pass}/${TOTAL}"

# Coverage: every ID in docs/use-cases-3.md named by a test that passed in this run.
"$PY" -m pytest -q -p no:cacheprovider tests --ignore=tests/e2e --junitxml="$OUT/unit.xml" >"$OUT/unit.log" 2>&1
unit_rc=$?
"$PY" - "$EVID" "$OUT" "$FIRST" "$LAST" "$unit_rc" <<'PYEOF'
import os, re, sys, xml.etree.ElementTree as ET
evid, out, first, last, unit_rc = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
problems = []
ids = re.findall(r"^\| ([A-Z]{3}-\d{2}) \|", open("docs/use-cases-3.md").read(), re.M)
if not ids or len(ids) != len(set(ids)):
    problems.append("docs/use-cases-3.md IDs missing or duplicated")
if unit_rc != 0:
    problems.append(f"unit tests failed (log {out}/unit.log)")
files = [f"{evid}/uc{n}.xml" for n in range(first, last + 1)] + [f"{out}/unit.xml"]
passed = set()
for f in files:
    if not os.path.exists(f):
        problems.append(f"missing {f}"); continue
    try:
        root = ET.parse(f).getroot()
    except Exception as e:
        problems.append(f"unreadable {f}: {e}"); continue
    for tc in root.iter("testcase"):
        if any(ch.tag in ("failure", "error", "skipped") for ch in tc):
            continue
        passed.add(tc.get("name", "").lower())
missing = [i for i in ids if not any(i.replace("-", "").lower() in n for n in passed)]
if missing:
    problems.append(f"{len(missing)} of {len(ids)} use cases have no passing test: " + ", ".join(missing))
print(f"use cases covered: {len(ids) - len(missing)}/{len(ids)}")
for p in problems:
    print("COVERAGE-3 FAIL: " + p)
print("COVERAGE-3: " + ("PASS" if not problems else "FAIL"))
sys.exit(1 if problems else 0)
PYEOF
cov=$?

[ "$pass" -eq "$TOTAL" ] && [ "$cov" -eq 0 ]
