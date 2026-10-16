#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOL="${ROOT}/commands/safe_append.sh"
fail() { printf '%s\n' "FAIL: $1"; exit 1; }

bash "$TOOL" --self-test | grep -q "RESULT=SELF_TEST_OK" || fail "self-test"

DIR="$(mktemp -d /tmp/cw-alarm-sh-test.XXXXXXXX)"
trap 'case "$DIR" in /tmp/cw-alarm-sh-test.*) rm -rf -- "$DIR" ;; esac' EXIT
LOG="${DIR}/application.log"
printf '%s\n' "keep this line" > "$LOG"
BEFORE="$(cat -- "$LOG")"

set +e
bash "$TOOL" --file "${LOG}" --marker "ERROR" --operator "tester" > "${DIR}/dry.out"
DRY=$?
set -e
[ "$DRY" -eq 0 ] || fail "dry-run exit ${DRY}"
grep -q "RESULT=DRY_RUN" "${DIR}/dry.out" || fail "dry-run result"
[ "$(cat -- "$LOG")" = "$BEFORE" ] || fail "dry-run changed the file"

bash "$TOOL" --file "$LOG" --marker "ERROR" --operator "tester" --confirm-append > "${DIR}/ok.out"
grep -q "RESULT=APPENDED" "${DIR}/ok.out" || fail "append result"
grep -q "keep this line" "$LOG" || fail "prefix lost"
tail -n 1 "$LOG" | grep -q "marker=ERROR" || fail "marker missing"
[ "$(tail -c 1 "$LOG" | od -An -tx1 | tr -d '[:space:]')" = "0a" ] || fail "no trailing newline"

set +e
bash "$TOOL" --file "${DIR}/missing.log" --marker "ERROR" --operator "tester" --confirm-append > "${DIR}/miss.out"
MISS=$?
set -e
[ "$MISS" -eq 2 ] || fail "missing exit ${MISS}"
[ ! -e "${DIR}/missing.log" ] || fail "missing file was created"

printf '%s\n' "draft line one" "draft line two" > "${DIR}/draft.txt"
bash "$TOOL" --file "$LOG" --text-file "${DIR}/draft.txt" --confirm-append > "${DIR}/long.out"
grep -q "draft line two" "$LOG" || fail "long text missing"
grep -q "keep this line" "$LOG" || fail "prefix lost after long text"

set +e
bash "$TOOL" --file "$LOG" --text-file "$LOG" --confirm-append > "${DIR}/self.out"
SELF=$?
set -e
[ "$SELF" -eq 2 ] || fail "self-append exit ${SELF}"
grep -q "同じファイル" "${DIR}/self.out" || fail "self-append message"

printf '%s' "no newline" > "${DIR}/bare.log"
set +e
bash "$TOOL" --file "${DIR}/bare.log" --marker "ERROR" --operator "tester" --confirm-append > "${DIR}/bare.out"
BARE=$?
set -e
[ "$BARE" -eq 2 ] || fail "bare exit ${BARE}"
[ "$(cat -- "${DIR}/bare.log")" = "no newline" ] || fail "bare file changed"

ln -s "$LOG" "${DIR}/link.log" || true
if [ -L "${DIR}/link.log" ]; then
  set +e
  bash "$TOOL" --file "${DIR}/link.log" --marker "ERROR" --operator "tester" --confirm-append > "${DIR}/link.out"
  LINK=$?
  set -e
  [ "$LINK" -eq 2 ] || fail "symlink exit ${LINK}"
fi

printf '%s\n' "PASS"
