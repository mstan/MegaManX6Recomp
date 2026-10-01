"""Packaged overlays must keep the development renderer's entry hooks."""

import contextlib
import io
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import check_release_config as checker


class ReleaseConfigTests(unittest.TestCase):
    def check(self, release_text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "game.toml"
            path.write_text(release_text, encoding="utf-8")
            output = io.StringIO()
            with patch.object(checker, "RELEASE_CONFIG", path), \
                    contextlib.redirect_stdout(output), \
                    contextlib.redirect_stderr(output):
                status = checker.main()
            return status, output.getvalue()

    def test_packaged_configuration_matches(self):
        self.assertEqual(self.check(checker.RELEASE_CONFIG.read_text())[0], 0)

    def test_missing_overlay_hooks_are_rejected(self):
        text = re.sub(r"^mod_function_entry_funcs = .*\n", "",
                      checker.RELEASE_CONFIG.read_text(), flags=re.MULTILINE)
        status, output = self.check(text)
        self.assertEqual(status, 1)
        self.assertIn("recompiler.mod_function_entry_funcs", output)

    def test_changed_overlay_hook_is_rejected(self):
        text = checker.RELEASE_CONFIG.read_text().replace("0x800270D0", "0x800270D4")
        status, output = self.check(text)
        self.assertEqual(status, 1)
        self.assertIn("recompiler.mod_function_entry_funcs", output)


if __name__ == "__main__":
    unittest.main()
