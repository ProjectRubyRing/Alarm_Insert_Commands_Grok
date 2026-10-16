import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "commands" / "safe_append.py"


class SafeAppendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="cw-alarm-test-")
        self.root = Path(self.temp.name)
        self.log = self.root / "application.log"
        self.original = ("existing line {0}\n".format("A" * 40) * 30).encode("utf-8")
        self.log.write_bytes(self.original)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_tool(self, args: list[str], stdin: bytes | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TOOL), *args],
            input=stdin.decode("utf-8") if stdin is not None else None,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )

    def test_self_test_uses_only_a_temp_file(self) -> None:
        result = self.run_tool(["--self-test"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESULT=SELF_TEST_OK", result.stdout)
        self.assertEqual(self.log.read_bytes(), self.original)

    def test_dry_run_does_not_change_bytes_or_inode(self) -> None:
        inode = self.log.stat().st_ino
        result = self.run_tool(
            ["--file", str(self.log), "--marker", "ERROR", "--operator", "tester"]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESULT=DRY_RUN", result.stdout)
        self.assertEqual(self.log.read_bytes(), self.original)
        self.assertEqual(self.log.stat().st_ino, inode)

    def test_confirm_appends_and_keeps_prefix_and_inode(self) -> None:
        inode = self.log.stat().st_ino
        result = self.run_tool(
            [
                "--file",
                str(self.log),
                "--marker",
                "ERROR",
                "--operator",
                "tester",
                "--confirm-append",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        observed = self.log.read_bytes()
        self.assertTrue(observed.startswith(self.original))
        self.assertGreater(len(observed), len(self.original))
        self.assertTrue(observed.endswith(b"\n"))
        self.assertIn(b"marker=ERROR", observed)
        self.assertEqual(self.log.stat().st_ino, inode)
        self.assertIn("head_unchanged=yes", result.stdout)
        self.assertIn("payload_found=yes", result.stdout)

    def test_missing_file_is_not_created(self) -> None:
        missing = self.root / "missing.log"
        result = self.run_tool(
            ["--file", str(missing), "--marker", "ERROR", "--operator", "tester", "--confirm-append"]
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(missing.exists())

    def test_relative_path_directory_placeholder_and_newline_are_refused(self) -> None:
        relative = self.run_tool(
            ["--file", "application.log", "--marker", "ERROR", "--operator", "tester", "--confirm-append"]
        )
        self.assertEqual(relative.returncode, 2, relative.stdout)
        directory = self.run_tool(
            ["--file", str(self.root), "--marker", "ERROR", "--operator", "tester"]
        )
        self.assertEqual(directory.returncode, 2, directory.stdout)
        placeholder = self.run_tool(
            [
                "--file",
                str(self.log),
                "--marker",
                "ここをメトリクスフィルタが探す文字列に書き換える",
                "--operator",
                "tester",
                "--confirm-append",
            ]
        )
        self.assertEqual(placeholder.returncode, 2, placeholder.stdout)
        self.assertEqual(self.log.read_bytes(), self.original)
        bare = self.root / "bare.log"
        bare.write_bytes(b"no-newline")
        refused = self.run_tool(
            ["--file", str(bare), "--marker", "ERROR", "--operator", "tester", "--confirm-append"]
        )
        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertEqual(bare.read_bytes(), b"no-newline")

    def test_utf16_nul_oversize_and_self_copy_are_refused(self) -> None:
        utf16 = self.root / "utf16.log"
        utf16.write_bytes(b"\xff\xfe" + "A\n".encode("utf-16le"))
        result = self.run_tool(
            ["--file", str(utf16), "--marker", "ERROR", "--operator", "tester", "--confirm-append"]
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertTrue(utf16.read_bytes().startswith(b"\xff\xfe"))
        draft = self.root / "draft.txt"
        draft.write_bytes("bad\x00text\n".encode("utf-8"))
        nul = self.run_tool(
            ["--file", str(self.log), "--text-file", str(draft), "--confirm-append"]
        )
        self.assertEqual(nul.returncode, 2, nul.stdout)
        huge = self.root / "huge.txt"
        huge.write_bytes(b"A" * 20000 + b"\n")
        over = self.run_tool(
            ["--file", str(self.log), "--text-file", str(huge), "--confirm-append", "--max-bytes", "100"]
        )
        self.assertEqual(over.returncode, 2, over.stdout)
        same = self.run_tool(
            ["--file", str(self.log), "--text-file", str(self.log), "--confirm-append", "--max-bytes", "1048550"]
        )
        self.assertEqual(same.returncode, 2, same.stdout)
        self.assertEqual(self.log.read_bytes(), self.original)

    def test_long_text_file_appends_without_growing_forever(self) -> None:
        draft = self.root / "draft.txt"
        body = b"ERROR CWALARM-TEST\nstack line\nthird line\r\n"
        draft.write_bytes(body)
        result = self.run_tool(
            ["--file", str(self.log), "--text-file", str(draft), "--confirm-append"]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        observed = self.log.read_bytes()
        self.assertTrue(observed.startswith(self.original))
        self.assertIn(b"ERROR CWALARM-TEST\nstack line\nthird line\n", observed)
        self.assertEqual(draft.read_bytes(), body)

    def test_json_is_one_line_and_escapes_quotes(self) -> None:
        result = self.run_tool(
            [
                "--file",
                str(self.log),
                "--marker",
                'disk "full"',
                "--operator",
                "tester",
                "--json",
                "--confirm-append",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        added = self.log.read_bytes()[len(self.original) :]
        self.assertEqual(added.count(b"\n"), 1)
        self.assertIn(b'\\"full\\"', added)
        self.assertIn(b'"cwAlarmTest":true', added)

    def test_conflicting_flags_do_not_write(self) -> None:
        result = self.run_tool(
            [
                "--file",
                str(self.log),
                "--marker",
                "ERROR",
                "--operator",
                "tester",
                "--confirm-append",
                "--dry-run",
            ]
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertEqual(self.log.read_bytes(), self.original)

    def test_concurrent_appends_keep_the_original_prefix(self) -> None:
        errors: list[str] = []

        def worker(index: int) -> None:
            result = self.run_tool(
                [
                    "--file",
                    str(self.log),
                    "--marker",
                    f"ERROR-{index}",
                    "--operator",
                    "tester",
                    "--confirm-append",
                ]
            )
            if result.returncode != 0:
                errors.append(result.stdout + result.stderr)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        observed = self.log.read_bytes()
        self.assertTrue(observed.startswith(self.original))
        for index in range(6):
            self.assertIn(f"marker=ERROR-{index}".encode("utf-8"), observed)

    def test_symlink_is_refused_when_the_platform_allows_one(self) -> None:
        link = self.root / "link.log"
        try:
            os.symlink(self.log, link)
        except OSError as exc:
            self.skipTest(f"symlink is not available: {exc}")
        result = self.run_tool(
            ["--file", str(link), "--marker", "ERROR", "--operator", "tester", "--confirm-append"]
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.log.read_bytes(), self.original)

    def test_open_flags_do_not_include_truncate_or_create(self) -> None:
        source = TOOL.read_text(encoding="utf-8")
        self.assertNotIn("os.O_TRUNC", source)
        self.assertNotIn("TRUNCATE_EXISTING", source)
        self.assertNotIn("CREATE_ALWAYS", source)
        self.assertNotIn("os.remove", source)
        self.assertNotIn("unlink", source)
        self.assertIn("open_existing = 3", source)
        self.assertEqual(source.count("os.O_CREAT"), 1)
        self.assertIn("cw-alarm-append-", source)


if __name__ == "__main__":
    unittest.main()
