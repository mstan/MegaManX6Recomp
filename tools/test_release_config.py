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
        self.assertEqual(self.check(checker.RELEASE_CONFIG.read_text(encoding="utf-8"))[0], 0)

    def test_missing_overlay_hooks_are_rejected(self):
        text = re.sub(r"^mod_function_entry_funcs = .*\n", "",
                      checker.RELEASE_CONFIG.read_text(encoding="utf-8"), flags=re.MULTILINE)
        status, output = self.check(text)
        self.assertEqual(status, 1)
        self.assertIn("recompiler.mod_function_entry_funcs", output)

    def test_changed_overlay_hook_is_rejected(self):
        text = checker.RELEASE_CONFIG.read_text(encoding="utf-8").replace("0x800270D0", "0x800270D4")
        status, output = self.check(text)
        self.assertEqual(status, 1)
        self.assertIn("recompiler.mod_function_entry_funcs", output)



class PlaytestDefaultsTests(unittest.TestCase):
    def test_current_version_and_adaptive_fresh_default(self):
        import tomllib
        root=Path(__file__).resolve().parents[1]
        self.assertEqual((root/'packaging/release/VERSION').read_text(encoding="utf-8").strip(),'v1.3.6-alpha')
        catalog=tomllib.loads((root/'mods/preloaded/packages/mmx6.enhancement.widescreen/1.0.0/manifest.toml').read_text(encoding="utf-8"))
        self.assertTrue(next(x for x in catalog['feature']if x['id']=='widescreen')['default_enabled'])
        self.assertEqual(next(x for x in catalog['option']if x['id']=='aspect')['default'],'adaptive')

    def test_normal_release_has_no_lab_catalog_or_loading_packages(self):
        import tomllib
        root=Path(__file__).resolve().parents[1]
        config=tomllib.loads((root/'packaging/release.toml').read_text(encoding="utf-8"))
        self.assertIn('-DMMX6_ENABLE_LOOPBACK_HOST_LAB=OFF',config['build']['cmake_args'])
        self.assertIn('-DMMX6_ENABLE_PORTABLE_CPU_HOST_LAB=OFF',config['build']['cmake_args'])
        self.assertIn('-DBUILD_TESTING=ON',config['build']['cmake_args'])
        self.assertNotIn('lab_', (root/'mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml').read_text(encoding="utf-8"))
        cmake=(root/'CMakeLists.txt').read_text(encoding="utf-8")
        allow=cmake[cmake.index('set(MMX6_BUILTIN_MOD_ALLOWLIST'):cmake.index('set(MMX6_BUILTIN_MOD_ALLOWLIST')+500]if 'set(MMX6_BUILTIN_MOD_ALLOWLIST'in cmake else cmake
        self.assertNotIn('psx.enhancement.cd-speed',allow)
        self.assertNotIn('psx.enhancement.fast-loading',allow)


if __name__ == "__main__":
    unittest.main()
