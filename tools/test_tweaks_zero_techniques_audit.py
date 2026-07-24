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


if __name__ == "__main__":
    unittest.main()
