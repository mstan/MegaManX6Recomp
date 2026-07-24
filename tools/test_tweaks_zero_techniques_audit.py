#!/usr/bin/env python3
"""Tests for the Zero-technique rejection boundary."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import tweaks_zero_techniques_audit as audit


class ZeroTechniqueAuditTests(unittest.TestCase):
    def test_exact_remaining_zero_inventory(self) -> None:
        self.assertEqual(len(audit.REJECTED_CONTROLS), 17)
        self.assertEqual(len(set(audit.REJECTED_CONTROLS)), 17)
        self.assertIn("ZeroYammarInput01", audit.REJECTED_CONTROLS)
        self.assertIn("ZeroEnsuizanMode01", audit.REJECTED_CONTROLS)

    def test_radio_helper_is_explicit(self) -> None:
        changes = {}
        audit._radio(changes, "ZeroSentsuizanInput", 2, 3)
        self.assertEqual(changes, {
            "ZeroSentsuizanInput01": "0",
            "ZeroSentsuizanInput02": "1",
            "ZeroSentsuizanInput03": "0",
        })

    def test_decision_names_single_feature_boundary(self) -> None:
        source = Path(
            r"F:\Projects\psxrecomp\_wt-mmx6-mod-packages\mmx6-tweaks"
            r"\_patcher\src_extracted"
            r"\Mega Man X6 Tweaks Patcher (v2.6.1)\_src"
        )
        profile = Path(
            r"F:\Projects\psxrecomp\_wt-mmx6-mod-packages\mmx6-tweaks"
            r"\_patcher\run_extracted\profiles\default.x6tweaksprofile"
        )
        if not source.exists() or not profile.exists():
            self.skipTest("reviewed MMX6 Tweaks extraction is not available")
        report = audit.build_audit(source, profile)
        decision = report["decision"]
        self.assertIn("single Zero-techniques feature", decision["reason"])
        self.assertIn(
            "one coherent Zero-techniques feature",
            decision["product_boundary"],
        )
        self.assertIn("cross-package", decision["required_primitive"])


if __name__ == "__main__":
    unittest.main()
