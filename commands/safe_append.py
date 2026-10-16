#!/usr/bin/env python3
"""Append a CloudWatch alarm test record to an existing log file.

The tool only appends bytes to a regular file that already exists.
It never creates, truncates, rewrites, or deletes the target.
Without --confirm-append it prints the plan and does not write.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import stat
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_REFUSED = 2
EXIT_VERIFY = 3

DEFAULT_MAX_BYTES = 16_384
AGENT_EXAMPLE_MAX_BYTES = 262_144
SERVICE_BATCH_MAX_BYTES = 1_048_576
SERVICE_EVENT_OVERHEAD = 26
ABSOLUTE_MAX_BYTES = SERVICE_BATCH_MAX_BYTES - SERVICE_EVENT_OVERHEAD
HEAD_SAMPLE_BYTES = 65_536
SEARCH_LIMIT_BYTES = 32 * 1024 * 1024
LOCK_WAIT_SECONDS = 10
PLACEHOLDER_MARK = "ここを"

DEVICE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


class Refusal(Exception):
    """The operator asked for something this tool will not do."""


class VerifyFailure(Exception):
    """Bytes may already have been appended, but the proof failed."""


@dataclass(frozen=True)
class Plan:
    path: Path
    payload: bytes
    inode: int
    device: int
    size: int
    head: bytes


@dataclass(frozen=True)
class Receipt:
    result: str
    path: Path
    inode: int
    size_before: int
    size_after: int
    payload_bytes: int
    payload_sha256: str
    head_unchanged: bool
    payload_found: bool


def _emit(text: str) -> None:
    print(text, flush=True)


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _refuse_placeholder(value: str, label: str) -> None:
    if PLACEHOLDER_MARK in value:
        raise Refusal(
            f"{label} に例文の「{PLACEHOLDER_MARK}」が残っています。"
            "実行する前に、現場の値へ書き換えてください。"
        )


def validate_existing_file(path_str: str) -> Path:
    """Return a normal, existing, absolute file path, or refuse."""
    if not isinstance(path_str, str) or path_str.strip() == "":
        raise Refusal("パスが空です。")
    if "\x00" in path_str or "\n" in path_str or "\r" in path_str:
        raise Refusal("パスに改行やヌル文字は使えません。")
    if any(char in path_str for char in "*?[]"):
        raise Refusal("ワイルドカードは使えません。実在する1つのファイルを指定します。")
    if not os.path.isabs(path_str):
        raise Refusal("絶対パスだけを受け付けます。相対パスは、今いるフォルダを間違えると別のファイルに当たります。")

    if os.name == "nt":
        raw = path_str.replace("/", "\\")
        _drive, rest = os.path.splitdrive(raw)
        if ":" in rest:
            raise Refusal("ドライブ文字以外のコロンは使えません。別ストリームや別デバイスの指定を拒否します。")
        absolute = os.path.abspath(raw)
        windows_root = os.path.abspath(os.environ.get("SystemRoot", r"C:\Windows"))
        lowered = absolute.lower()
        root_lower = windows_root.lower()
        if lowered == root_lower or lowered.startswith(root_lower + "\\"):
            raise Refusal("Windows のシステムディレクトリには書きません。")
        final_name = os.path.basename(absolute).split(".")[0].upper()
        if final_name in DEVICE_NAMES:
            raise Refusal("デバイス名には書きません。")
    else:
        absolute = os.path.abspath(path_str)
        if absolute == "/" or absolute in {"/proc", "/sys", "/dev"}:
            raise Refusal("この場所には書きません。")
        for prefix in ("/proc/", "/sys/", "/dev/"):
            if absolute.startswith(prefix):
                raise Refusal("この場所には書きません。ログファイルのパスを指定します。")

    path = Path(absolute)
    try:
        link_stat = os.lstat(path)
    except FileNotFoundError as exc:
        raise Refusal("ファイルがありません。新しいファイルは作りません。") from exc

    if stat.S_ISLNK(link_stat.st_mode):
        raise Refusal("シンボリックリンクです。リンク先の本物のパスを指定します。")
    attributes = getattr(link_stat, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if attributes & reparse:
        raise Refusal("リンクまたはジャンクションです。本物のファイルのパスを指定します。")
    if stat.S_ISDIR(link_stat.st_mode):
        raise Refusal("ディレクトリです。ディレクトリの中をまとめて扱いません。")
    if not stat.S_ISREG(link_stat.st_mode):
        raise Refusal("通常のファイルではありません。パイプやデバイスには書きません。")
    if not os.access(path, os.W_OK):
        raise Refusal("このファイルへ書き込む権限がありません。")
    return path


def _read_head_and_last(path: Path) -> tuple[bytes, int, bytes]:
    with path.open("rb") as handle:
        head = handle.read(HEAD_SAMPLE_BYTES)
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        if size == 0:
            return head, size, b""
        handle.seek(size - 1)
        return head, size, handle.read(1)


def _encoding_guard(head: bytes) -> None:
    if head.startswith(b"\xff\xfe") or head.startswith(b"\xfe\xff"):
        raise Refusal("UTF-16 のファイルです。UTF-8 を混ぜると文字が壊れます。このツールでは追記しません。")


def _lock(fd: int) -> None:
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise Refusal("別の処理がロックを持っています。10秒待っても取れなかったので、何も書きません。")
            time.sleep(0.05)


def _unlock(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("write が 0 を返しました。")
        view = view[written:]


def _contains_from(path: Path, start: int, needle: bytes, limit: int) -> bool:
    if needle == b"":
        return False
    overlap = max(len(needle) - 1, 0)
    carry = b""
    remaining = limit
    with path.open("rb") as handle:
        handle.seek(max(start, 0))
        while remaining > 0:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            data = carry + chunk
            if needle in data:
                return True
            carry = data[-overlap:] if overlap else b""
    return False


def prepare_text(raw: bytes, *, max_bytes: int) -> bytes:
    if b"\x00" in raw:
        raise Refusal("ヌル文字が含まれています。ログの1行として追記しません。")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refusal("UTF-8 として読めません。文字コードを直した下書きを作り直してください。") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.strip("\n") == "":
        raise Refusal("追記する中身が空です。")
    text = text.rstrip("\n") + "\n"
    payload = text.encode("utf-8")
    if len(payload) > max_bytes:
        raise Refusal(
            f"追記データが {len(payload)} バイトあります。この実行の上限は {max_bytes} バイトです。"
            "アラーム試験の1行は短くします。"
            f"エージェント例の 256KB まで使うなら --max-bytes {AGENT_EXAMPLE_MAX_BYTES}、"
            f"サービスのバッチに収まる上限まで使うなら --max-bytes {ABSOLUTE_MAX_BYTES} です。"
        )
    if len(payload) > ABSOLUTE_MAX_BYTES:
        raise Refusal(
            "1回の PutLogEvents に載る実用水準（1,048,576 からイベントオーバーヘッド 26 を引いた値）を超えています。"
        )
    return payload


def marker_line(marker: str, operator: str, *, json_line: bool, json_level: str) -> bytes:
    for label, value in (("検知文字列", marker), ("操作者", operator), ("JSONのlevel", json_level)):
        if value.strip() == "":
            raise Refusal(f"{label} が空です。")
        if "\n" in value or "\r" in value or "\x00" in value:
            raise Refusal(f"{label} に改行やヌル文字は使えません。長文は --text-file を使います。")
    _refuse_placeholder(marker, "検知文字列")
    _refuse_placeholder(operator, "操作者")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    host = socket.gethostname()
    test_id = str(uuid.uuid4())
    if json_line:
        payload = {
            "time": now,
            "level": json_level,
            "cwAlarmTest": True,
            "id": test_id,
            "host": host,
            "operator": operator,
            "message": marker,
        }
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    else:
        line = (
            f"CWALARM-TEST time={now} host={host} operator={operator} "
            f"id={test_id} marker={marker}"
        )
    return (line + "\n").encode("utf-8")


def load_text_file(text_file: Path, target: Path, max_bytes: int) -> bytes:
    source = validate_existing_file(str(text_file))
    source_stat = source.stat()
    target_stat = target.stat()
    if source_stat.st_dev == target_stat.st_dev and source_stat.st_ino == target_stat.st_ino:
        raise Refusal("下書きとログが同じファイルです。ログを自分自身へ足すと、終わりなく膨らみます。")
    with source.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    return prepare_text(raw, max_bytes=max_bytes)


def inspect_plan(path: Path, payload: bytes, *, allow_missing_newline: bool) -> Plan:
    file_stat = path.stat()
    head, size, last = _read_head_and_last(path)
    _encoding_guard(head)
    if size > 0 and last != b"\n" and not allow_missing_newline:
        raise Refusal(
            "末尾が改行（バイト 0a）ではありません。"
            "このまま足すと、書きかけの行と試験行がつながり、エージェントがまとめて送ることがあります。"
            "末尾を人が確認し、それでも足す場合だけ --allow-missing-trailing-newline を付けます。"
        )
    sample_length = min(size, HEAD_SAMPLE_BYTES)
    return Plan(
        path=path,
        payload=payload,
        inode=file_stat.st_ino,
        device=file_stat.st_dev,
        size=size,
        head=head[:sample_length],
    )


def _print_plan(plan: Plan, *, writing: bool) -> None:
    preview = plan.payload.decode("utf-8")
    if len(preview) > 2000:
        preview = preview[:1500] + "\n...（中略）...\n" + preview[-300:]
    _emit(f"path={plan.path}")
    _emit(f"inode={plan.inode}")
    _emit(f"size_before={plan.size}")
    _emit(f"payload_bytes={len(plan.payload)}")
    _emit(f"payload_sha256={_sha256(plan.payload)}")
    _emit("---- payload ----")
    _emit(preview.rstrip("\n"))
    _emit("---- end ----")
    if writing:
        _emit("mode=confirm-append")
    else:
        _emit("RESULT=DRY_RUN")
        _emit("ファイルは変更していません。")


def _open_append(path: Path) -> int:
    """Open an existing file for append. Never create it and never shorten it."""
    if os.name != "nt":
        return os.open(path, os.O_WRONLY | os.O_APPEND)
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    file_append_data = 0x0004
    share_all = 0x0001 | 0x0002 | 0x0004
    open_existing = 3
    normal = 0x80
    handle = create_file(str(path), file_append_data, share_all, None, open_existing, normal, None)
    invalid = wintypes.HANDLE(-1).value
    if handle == invalid:
        error = ctypes.get_last_error()
        raise Refusal(f"追記用に開けませんでした。Windows エラー {error}。新しいファイルは作りません。")
    return msvcrt.open_osfhandle(int(handle), os.O_APPEND | os.O_BINARY)


def _sidecar_lock(path: Path) -> int:
    """Lock a temp file, not the log. The log itself stays append-only."""
    import hashlib

    digest = hashlib.sha256(os.path.abspath(path).encode("utf-8")).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"cw-alarm-append-{digest}.lock"
    flags = os.O_CREAT | os.O_RDWR
    if os.name == "nt":
        flags |= os.O_BINARY
    fd = os.open(lock_path, flags, 0o600)
    try:
        _lock(fd)
    except Exception:
        os.close(fd)
        raise
    return fd


def append_payload(path: Path, payload: bytes, *, allow_missing_newline: bool) -> Receipt:
    plan = inspect_plan(path, payload, allow_missing_newline=allow_missing_newline)
    lock_fd = _sidecar_lock(path)
    try:
        fd = _open_append(path)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise Refusal("開いた先が通常ファイルではありません。何も書きません。")
            if plan.inode != before.st_ino or plan.device != before.st_dev:
                raise Refusal("開いてからファイルの識別子が変わりました。何も書きません。")
            if before.st_size < plan.size:
                raise Refusal("開く前よりファイルが小さくなっています。切り詰めが起きたので何も書きません。")
            _print_plan(plan, writing=True)
            _write_all(fd, payload)
            os.fsync(fd)
            after = os.fstat(fd)
        finally:
            os.close(fd)
    finally:
        _unlock(lock_fd)
        os.close(lock_fd)

    if after.st_ino != before.st_ino or after.st_dev != before.st_dev:
        raise VerifyFailure("inode が変わりました。ファイルが置き換わっています。切り詰め直しはしません。")
    if after.st_size < before.st_size:
        raise VerifyFailure("サイズが減りました。切り詰めが起きました。ツールから戻す操作はしません。")
    if after.st_size < before.st_size + len(payload):
        raise VerifyFailure("増えたバイト数が、書いたバイト数より少ないです。人が tail で確認してください。")

    head_after, size_after, _last = _read_head_and_last(path)
    sample_length = len(plan.head)
    head_unchanged = head_after[:sample_length] == plan.head
    if not head_unchanged:
        raise VerifyFailure("先頭サンプルが変わっています。追記以外の書き換えが起きた可能性があります。")
    found = _contains_from(path, before.st_size, payload, SEARCH_LIMIT_BYTES)
    if not found:
        tail_start = max(size_after - SEARCH_LIMIT_BYTES, 0)
        found = _contains_from(path, tail_start, payload, SEARCH_LIMIT_BYTES)
    if not found:
        raise VerifyFailure(
            "書いたバイト列を、追記位置から 32MB の範囲と末尾 32MB に見つけられませんでした。"
            "inode は同じで、サイズは減っていません。検索キーを人が探してください。"
        )
    receipt = Receipt(
        result="APPENDED",
        path=path,
        inode=after.st_ino,
        size_before=before.st_size,
        size_after=after.st_size,
        payload_bytes=len(payload),
        payload_sha256=_sha256(payload),
        head_unchanged=True,
        payload_found=True,
    )
    _emit("RESULT=APPENDED")
    _emit(f"inode={receipt.inode}")
    _emit(f"size_before={receipt.size_before}")
    _emit(f"size_after={receipt.size_after}")
    _emit(f"size_delta={receipt.size_after - receipt.size_before}")
    _emit(f"payload_bytes={receipt.payload_bytes}")
    _emit(f"head_unchanged={'yes' if receipt.head_unchanged else 'no'}")
    _emit(f"payload_found={'yes' if receipt.payload_found else 'no'}")
    if receipt.size_after > receipt.size_before + receipt.payload_bytes:
        _emit("note=待ち時間のあいだに、ほかのプロセスもこのログへ書いています。試験行はその中にあります。")
    return receipt


def dry_run(path: Path, payload: bytes, *, allow_missing_newline: bool) -> Plan:
    plan = inspect_plan(path, payload, allow_missing_newline=allow_missing_newline)
    _print_plan(plan, writing=False)
    return plan


def build_payload(args: argparse.Namespace, path: Path) -> bytes:
    modes = [args.marker is not None, args.text_file is not None, args.stdin]
    if sum(1 for enabled in modes if enabled) != 1:
        raise Refusal("--marker か --text-file か --stdin を、どれか1つだけ指定します。")
    if args.marker is not None:
        if args.operator is None:
            raise Refusal("--marker を使うときは --operator も指定します。")
        payload = marker_line(
            args.marker,
            args.operator,
            json_line=args.json,
            json_level=args.json_level,
        )
        if len(payload) > args.max_bytes:
            raise Refusal(f"試験行が上限 {args.max_bytes} バイトを超えています。")
        return payload
    if args.text_file is not None:
        _refuse_placeholder(str(args.text_file), "下書きパス")
        return load_text_file(Path(args.text_file), path, args.max_bytes)
    if sys.stdin.isatty():
        raise Refusal("標準入力が端末です。--stdin は、下書きをパイプで渡すときだけ使います。")
    raw = sys.stdin.buffer.read(args.max_bytes + 1)
    if PLACEHOLDER_MARK.encode("utf-8") in raw:
        raise Refusal("標準入力に例文の「ここを」が残っています。")
    return prepare_text(raw, max_bytes=args.max_bytes)


def run_self_test() -> int:
    """Exercise append safety against a temporary log, then delete only that temp directory."""
    with tempfile.TemporaryDirectory(prefix="cw-alarm-self-test-") as directory:
        log_path = Path(directory) / "application.log"
        original = ("existing application line\n" * 40).encode("utf-8")
        log_path.write_bytes(original)
        inode_before = log_path.stat().st_ino
        payload = marker_line("SELFTEST", "self-test", json_line=False, json_level="ERROR")
        dry_run(log_path, payload, allow_missing_newline=False)
        if log_path.read_bytes() != original:
            raise VerifyFailure("ドライランでファイルが変わりました。")
        receipt = append_payload(log_path, payload, allow_missing_newline=False)
        observed = log_path.read_bytes()
        if not observed.startswith(original):
            raise VerifyFailure("セルフテストで既存行が失われました。")
        if observed[len(original) :] != payload:
            raise VerifyFailure("セルフテストの追記バイトが一致しません。")
        if receipt.inode != inode_before:
            raise VerifyFailure("セルフテストで inode が変わりました。")
        missing = log_path.with_name("does-not-exist.log")
        try:
            validate_existing_file(str(missing))
        except Refusal:
            pass
        else:
            raise VerifyFailure("存在しないファイルを拒否しませんでした。")
    _emit("RESULT=SELF_TEST_OK")
    return EXIT_OK


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="safe_append.py",
        description=(
            "既存ログの末尾へ、CloudWatch Alarm 試験用の文字列だけを足します。"
            "ファイルの作成、切り詰め、上書き、削除はしません。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "書き込むのは --confirm-append を付けたときだけです。\n"
            "先に --self-test を実行すると、一時ディレクトリの中だけで動作を確認できます。\n"
            "本番の通知先に試験であることが伝わっているときだけ、本番ログへ実行してください。"
        ),
    )
    parser.add_argument("--file", help="既存ログの絶対パス")
    parser.add_argument("--marker", help="メトリクスフィルタが探す文字列")
    parser.add_argument("--operator", help="だれが試験したか。試験行に残します")
    parser.add_argument("--text-file", help="足したい長文が入った、ログとは別の下書きファイル")
    parser.add_argument("--stdin", action="store_true", help="標準入力の長文を足す")
    parser.add_argument("--json", action="store_true", help="試験行を1行のJSONにする")
    parser.add_argument("--json-level", default="ERROR", help="JSONの level。既定は ERROR")
    parser.add_argument("--confirm-append", action="store_true", help="このフラグがあるときだけ追記する")
    parser.add_argument("--dry-run", action="store_true", help="明示的なドライラン。--confirm-append と同時には使えません")
    parser.add_argument(
        "--allow-missing-trailing-newline",
        action="store_true",
        help="末尾が改行でなくても追記する。未完成の行が一緒に送られることがある",
    )
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--self-test", action="store_true", help="一時ファイルだけで安全確認を実行する")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.self_test:
            if args.confirm_append or args.file or args.marker or args.text_file or args.stdin:
                raise Refusal("--self-test は単独で実行します。本番のパスは受け取りません。")
            return run_self_test()
        if args.max_bytes < 1 or args.max_bytes > ABSOLUTE_MAX_BYTES:
            raise Refusal(f"--max-bytes は 1 から {ABSOLUTE_MAX_BYTES} までです。")
        if args.confirm_append and args.dry_run:
            raise Refusal("--confirm-append と --dry-run は同時に指定できません。")
        if not args.file:
            raise Refusal("--file に既存ログの絶対パスを指定します。")
        _refuse_placeholder(args.file, "ログのパス")
        path = validate_existing_file(args.file)
        payload = build_payload(args, path)
        if args.confirm_append:
            append_payload(path, payload, allow_missing_newline=args.allow_missing_trailing_newline)
        else:
            dry_run(path, payload, allow_missing_newline=args.allow_missing_trailing_newline)
        return EXIT_OK
    except Refusal as exc:
        _emit(f"RESULT=REFUSED")
        _emit(str(exc))
        return EXIT_REFUSED
    except VerifyFailure as exc:
        _emit("RESULT=VERIFY_FAILED")
        _emit(str(exc))
        return EXIT_VERIFY


if __name__ == "__main__":
    sys.exit(main())
