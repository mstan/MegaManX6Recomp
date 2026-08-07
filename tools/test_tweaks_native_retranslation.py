#!/usr/bin/env python3
"""Focused tests for the native Retranslation conversion boundary."""

from __future__ import annotations

import hashlib
import sys
import tomllib
import unittest
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_native_psxmod as native


class RetranslationExtraMugshotTests(unittest.TestCase):
    def test_exact_permission_gated_site_ledger(self) -> None:
        characters = native.RETRANSLATION_EXTRA_MUGSHOT_RECORDS.values()
        self.assertEqual(len(native.RETRANSLATION_EXTRA_MUGSHOT_RECORDS), 18)
        self.assertEqual(sum(item == "hunter" for item in characters), 2)
        self.assertEqual(sum(item == "dr_light" for item in characters), 16)

    def test_forced_portrait_is_restored_to_none(self) -> None:
        source = native.Subasset(
            0x15,
            b"translated" + native.EXTRA_MUGSHOT_FORCED_COMMAND + b"dialogue",
        )
        restored, evidence = native.restore_retranslation_extra_mugshot_none(
            203, 0, source
        )
        self.assertEqual(
            restored.payload,
            b"translated" + native.EXTRA_MUGSHOT_NONE_COMMAND + b"dialogue",
        )
        self.assertEqual(evidence["character"], "hunter")
        self.assertEqual(evidence["relative_offset"], len(b"translated"))

    def test_missing_reviewed_site_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            AssertionError, "contains 0 forced extra-mugshot commands"
        ):
            native.restore_retranslation_extra_mugshot_none(
                203, 0, native.Subasset(0x15, b"translated dialogue")
            )

    def test_unreviewed_forced_site_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            AssertionError, "contains 1 forced extra-mugshot commands"
        ):
            native.restore_retranslation_extra_mugshot_none(
                220,
                0,
                native.Subasset(
                    0x15, native.EXTRA_MUGSHOT_FORCED_COMMAND
                ),
            )

    def test_preloaded_retranslation_uses_no_portrait_payloads(self) -> None:
        package = (
            ROOT
            / "mods"
            / "preloaded"
            / "packages"
            / "mmx6.tweaks.native"
            / "1.10.5"
        )
        manifest = tomllib.loads(
            (package / "manifest.toml").read_text(encoding="utf-8")
        )
        overlay_by_file = {
            item["file"]: item
            for item in manifest["overlay"]
            if item["feature"] == "retranslation"
        }

        for record_id in native.RETRANSLATION_EXTRA_MUGSHOT_RECORDS:
            matches = tuple(
                (package / "assets" / "retranslation").glob(
                    f"*-record-{record_id}-*.bin"
                )
            )
            payloads = tuple(
                path
                for path in matches
                if path.name.endswith("-subasset-00.bin")
                or path.name.endswith("-relocated.bin")
            )
            self.assertEqual(
                len(payloads), 1, f"record {record_id} payload"
            )
            path = payloads[0]
            payload = path.read_bytes()
            self.assertNotIn(
                native.EXTRA_MUGSHOT_FORCED_COMMAND, payload, path.name
            )
            self.assertIn(native.EXTRA_MUGSHOT_NONE_COMMAND, payload, path.name)

            relative_path = path.relative_to(package).as_posix()
            self.assertIn(relative_path, overlay_by_file)
            self.assertEqual(
                hashlib.sha256(payload).hexdigest(),
                overlay_by_file[relative_path]["sha256"],
                path.name,
            )


if __name__ == "__main__":
    unittest.main()
