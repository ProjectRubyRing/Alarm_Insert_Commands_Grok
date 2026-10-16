#!/usr/bin/env bash
# Append one UTF-8 test record to an existing log.
# This script never creates, truncates, rewrites, or deletes the target.
# A write happens only with --confirm-append. Anything else is a dry run.
set -euo pipefail
set -o noclobber

if [ -z "${BASH_VERSION:-}" ]; then
  printf '%s\n' "RESULT=REFUSED"
  printf '%s\n' "bash で実行してください。"
  exit 2
fi

MAX_BYTES=16384
ABSOLUTE_MAX=1048550
SAMPLE_DIR=""

cleanup() {
  case "${SAMPLE_DIR:-}" in
    /tmp/cw-alarm-sample.*) rm -rf -- "$SAMPLE_DIR" ;;
  esac
}
trap cleanup EXIT

emit() {
  printf '%s\n' "$1"
}

refuse() {
  emit "RESULT=REFUSED"
  emit "$1"
  exit 2
}

verify_fail() {
  emit "RESULT=VERIFY_FAILED"
  emit "$1"
  exit 3
}

usage() {
  emit "使い方: safe_append.sh --file 絶対パス (--marker 文字列 --operator 名前 | --text-file 下書き) [--confirm-append]"
  emit "書き込むのは --confirm-append のときだけです。先に --self-test を実行できます。"
}

has_placeholder() {
  case "$1" in
    *ここを*) return 0 ;;
    *) return 1 ;;
  esac
}

require_safe_path() {
  local file="$1"
  local label="$2"
  [ -n "$file" ] || refuse "${label} が空です。"
  case "$file" in
    *$'\n'*|*$'\r'*) refuse "${label} に改行は使えません。" ;;
    *'*'*|*'?'*|*'['*) refuse "${label} にワイルドカードは使えません。" ;;
    /*) ;;
    *) refuse "${label} は絶対パスだけを受け付けます。" ;;
  esac
  case "$file" in
    /|/proc|/proc/*|/sys|/sys/*|/dev|/dev/*)
      refuse "${label} がシステム領域です。ログファイルを指定します。"
      ;;
  esac
  if [ -L "$file" ]; then
    refuse "${label} はシンボリックリンクです。本物のパスを指定します。"
  fi
  if [ ! -e "$file" ]; then
    refuse "${label} のファイルがありません。新しいファイルは作りません。"
  fi
  if [ -d "$file" ]; then
    refuse "${label} はディレクトリです。"
  fi
  if [ ! -f "$file" ]; then
    refuse "${label} は通常のファイルではありません。"
  fi
}

check_bom_and_newline() {
  local file="$1"
  local size bom last
  size="$(stat -c '%s' "$file")"
  if [ "$size" -ge 2 ]; then
    bom="$(dd if="$file" bs=2 count=1 status=none | od -An -tx1 | tr -d '[:space:]')"
    case "$bom" in
      fffe|feff) refuse "UTF-16 のファイルです。UTF-8 を混ぜません。" ;;
    esac
  fi
  if [ "$size" -gt 0 ]; then
    last="$(tail -c 1 "$file" | od -An -tx1 | tr -d '[:space:]')"
    if [ "$last" != "0a" ]; then
      refuse "末尾が改行（0a）ではありません。未完成の行と試験行がつながることがあります。"
    fi
  fi
}

prepare_payload() {
  local raw="$1"
  raw="${raw//$'\r'/}"
  raw="${raw%$'\n'}"
  if [ -z "$raw" ]; then
    refuse "追記する中身が空です。"
  fi
  printf '%s\n' "$raw"
}

payload_from_marker() {
  local marker="$1"
  local operator="$2"
  local now host test_id
  case "$marker" in
    *$'\n'*|*$'\r'*) refuse "検知文字列に改行は使えません。長文は --text-file です。" ;;
  esac
  case "$operator" in
    *$'\n'*|*$'\r'*) refuse "操作者に改行は使えません。" ;;
  esac
  [ -n "$marker" ] || refuse "検知文字列が空です。"
  [ -n "$operator" ] || refuse "操作者が空です。"
  if has_placeholder "$marker"; then
    refuse "検知文字列に例文の「ここを」が残っています。"
  fi
  if has_placeholder "$operator"; then
    refuse "操作者に例文の「ここを」が残っています。"
  fi
  now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  host="$(hostname 2>/dev/null || printf '%s' "unknown-host")"
  test_id="$(od -An -N16 -tx1 /dev/urandom | tr -d '[:space:]')"
  printf '%s\n' "CWALARM-TEST time=${now} host=${host} operator=${operator} id=${test_id} marker=${marker}"
}

show_plan() {
  local file="$1"
  local payload="$2"
  local writing="$3"
  emit "path=${file}"
  emit "inode=$(stat -c '%i' "$file")"
  emit "size_before=$(stat -c '%s' "$file")"
  emit "payload_bytes=$(printf '%s' "$payload" | wc -c | tr -d '[:space:]')"
  emit "---- payload ----"
  printf '%s' "$payload"
  emit "---- end ----"
  if [ "$writing" = "yes" ]; then
    emit "mode=confirm-append"
  else
    emit "RESULT=DRY_RUN"
    emit "ファイルは変更していません。"
  fi
}

append_payload() {
  local file="$1"
  local payload="$2"
  case "$payload" in
    *$'\n') ;;
    *) refuse "試験行の末尾に改行がありません。エージェントは改行までを1件として読みます。" ;;
  esac
  local before_inode before_size after_inode after_size payload_bytes sample
  local payload_file added_file before_head after_head
  SAMPLE_DIR="$(mktemp -d /tmp/cw-alarm-sample.XXXXXXXX)"
  payload_file="${SAMPLE_DIR}/payload"
  added_file="${SAMPLE_DIR}/added"
  before_head="${SAMPLE_DIR}/head-before"
  after_head="${SAMPLE_DIR}/head-after"
  printf '%s' "$payload" > "$payload_file"
  payload_bytes="$(stat -c '%s' "$payload_file")"
  if [ "$payload_bytes" -gt "$MAX_BYTES" ]; then
    refuse "追記データが ${payload_bytes} バイトあります。上限は ${MAX_BYTES} バイトです。"
  fi
  before_inode="$(stat -c '%i' "$file")"
  before_size="$(stat -c '%s' "$file")"
  sample="$before_size"
  if [ "$sample" -gt 65536 ]; then
    sample=65536
  fi
  if [ "$sample" -gt 0 ]; then
    dd if="$file" of="$before_head" bs="$sample" count=1 status=none
  else
    : > "$before_head"
  fi
  show_plan "$file" "$payload" "yes"
  printf '%s' "$payload" >> "$file"
  after_inode="$(stat -c '%i' "$file")"
  after_size="$(stat -c '%s' "$file")"
  if [ "$after_inode" != "$before_inode" ]; then
    verify_fail "inode が変わりました。ファイルが置き換わっています。切り詰め直しはしません。"
  fi
  if [ "$after_size" -lt "$before_size" ]; then
    verify_fail "サイズが減りました。切り詰めが起きました。ツールから戻す操作はしません。"
  fi
  if [ "$after_size" -lt $((before_size + payload_bytes)) ]; then
    verify_fail "増えたバイト数が、書いたバイト数より少ないです。"
  fi
  if [ "$sample" -gt 0 ]; then
    dd if="$file" of="$after_head" bs="$sample" count=1 status=none
    if ! cmp -s "$before_head" "$after_head"; then
      verify_fail "先頭サンプルが変わっています。追記以外の書き換えが起きた可能性があります。"
    fi
  fi
  if [ $((after_size - before_size)) -eq "$payload_bytes" ]; then
    dd if="$file" of="$added_file" bs=1 skip="$before_size" count="$payload_bytes" status=none
    if ! cmp -s "$payload_file" "$added_file"; then
      verify_fail "末尾に書いたバイト列が一致しません。"
    fi
  elif ! grep -F -a -q -f "$payload_file" "$file"; then
    verify_fail "書いたバイト列をファイル内に見つけられませんでした。inode は同じです。"
  fi
  emit "RESULT=APPENDED"
  emit "inode=${after_inode}"
  emit "size_before=${before_size}"
  emit "size_after=${after_size}"
  emit "size_delta=$((after_size - before_size))"
  emit "payload_bytes=${payload_bytes}"
  emit "head_unchanged=yes"
  emit "payload_found=yes"
}

run_self_test() {
  local dir log_file original_file
  dir="$(mktemp -d /tmp/cw-alarm-self-test.XXXXXXXX)"
  log_file="${dir}/application.log"
  original_file="${dir}/original"
  printf '%s\n' "existing application line" "existing application line" > "$log_file"
  cp -p "$log_file" "$original_file"
  MAX_BYTES=16384
  local payload
  payload="$(payload_from_marker "SELFTEST" "self-test")"$'\n'
  show_plan "$log_file" "$payload" "no"
  if ! cmp -s "$log_file" "$original_file"; then
    verify_fail "ドライランでファイルが変わりました。"
  fi
  cat -- "$original_file" > "${dir}/expected"
  printf '%s' "$payload" >> "${dir}/expected"
  append_payload "$log_file" "$payload"
  if ! cmp -s "$log_file" "${dir}/expected"; then
    verify_fail "セルフテストの追記結果が、既存行に試験行を足した内容と一致しません。"
  fi
  case "$dir" in
    /tmp/cw-alarm-self-test.*) rm -rf -- "$dir" ;;
    *) verify_fail "一時ディレクトリのパスが想定外なので削除しません。" ;;
  esac
  emit "RESULT=SELF_TEST_OK"
}

FILE_PATH=""
MARKER=""
OPERATOR_NAME=""
TEXT_FILE=""
CONFIRM="no"
SELF_TEST="no"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --file)
      FILE_PATH="${2:-}"
      shift 2
      ;;
    --marker)
      MARKER="${2:-}"
      shift 2
      ;;
    --operator)
      OPERATOR_NAME="${2:-}"
      shift 2
      ;;
    --text-file)
      TEXT_FILE="${2:-}"
      shift 2
      ;;
    --confirm-append)
      CONFIRM="yes"
      shift
      ;;
    --dry-run)
      CONFIRM="no"
      shift
      ;;
    --self-test)
      SELF_TEST="yes"
      shift
      ;;
    --max-bytes)
      MAX_BYTES="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      refuse "未知の引数です: $1"
      ;;
  esac
done

if [ "$SELF_TEST" = "yes" ]; then
  if [ -n "$FILE_PATH" ] || [ -n "$MARKER" ] || [ -n "$TEXT_FILE" ]; then
    refuse "--self-test は単独で実行します。"
  fi
  run_self_test
  exit 0
fi

case "$MAX_BYTES" in
  ''|*[!0-9]*) refuse "--max-bytes は正の整数です。" ;;
esac
if [ "$MAX_BYTES" -lt 1 ] || [ "$MAX_BYTES" -gt "$ABSOLUTE_MAX" ]; then
  refuse "--max-bytes が範囲外です。"
fi

[ -n "$FILE_PATH" ] || refuse "--file を指定します。"
if has_placeholder "$FILE_PATH"; then
  refuse "ログのパスに例文の「ここを」が残っています。"
fi
require_safe_path "$FILE_PATH" "ログ"
[ -w "$FILE_PATH" ] || refuse "このファイルへ書き込む権限がありません。"
check_bom_and_newline "$FILE_PATH"

modes=0
[ -n "$MARKER" ] && modes=$((modes + 1))
[ -n "$TEXT_FILE" ] && modes=$((modes + 1))
[ "$modes" -eq 1 ] || refuse "--marker か --text-file を、どちらか1つ指定します。"

if [ -n "$MARKER" ]; then
  PAYLOAD="$(payload_from_marker "$MARKER" "$OPERATOR_NAME")"$'\n'
else
  if has_placeholder "$TEXT_FILE"; then
    refuse "下書きパスに例文の「ここを」が残っています。"
  fi
  require_safe_path "$TEXT_FILE" "下書き"
  log_id="$(stat -c '%d:%i' "$FILE_PATH")"
  text_id="$(stat -c '%d:%i' "$TEXT_FILE")"
  if [ "$log_id" = "$text_id" ]; then
    refuse "下書きとログが同じファイルです。ログを自分自身へ足すと、終わりなく膨らみます。"
  fi
  text_size="$(stat -c '%s' "$TEXT_FILE")"
  if [ "$text_size" -gt "$MAX_BYTES" ]; then
    refuse "下書きが大きすぎます。上限は ${MAX_BYTES} バイトです。"
  fi
  stripped_size="$(tr -d '\000' < "$TEXT_FILE" | wc -c | tr -d '[:space:]')"
  if [ "$text_size" -ne "$stripped_size" ]; then
    refuse "下書きにヌル文字があります。"
  fi
  PAYLOAD="$(prepare_payload "$(cat -- "$TEXT_FILE")")"$'\n'
fi

if [ "$CONFIRM" = "yes" ]; then
  append_payload "$FILE_PATH" "$PAYLOAD"
else
  show_plan "$FILE_PATH" "$PAYLOAD" "no"
fi
