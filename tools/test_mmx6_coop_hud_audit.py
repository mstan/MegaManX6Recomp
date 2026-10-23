"""Source-audit reproduction and strict limits; no native/rendered passes."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_mmx6_coop_hud as hud

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"docs/COOP_HUD_MENU_AUDIT.json"


class SourceAuditTests(unittest.TestCase):
    def report(self):return json.loads(REPORT.read_text(encoding="utf-8"))

    def test_exact_three_frozen_definitions_and_no_inherited_passes(self):
        data=self.report()
        self.assertEqual(data["scope"],["R5","R6","F18"])
        self.assertEqual({r["id"]:r["frozen_row_sha256"] for r in data["comparisons"]},hud.DEFINITIONS)
        self.assertTrue(data["source_only"])
        for row in data["comparisons"]:
            self.assertEqual((row["local"],row["netplay"],row["rendered_status"]),("unverified",)*3)
        self.assertNotIn("x5_sources",data)

    def test_current_fixed_layout_gap_is_not_a_rendered_failure_or_pass(self):
        data=self.report()
        self.assertEqual(data["layout"]["p2_translation"],dict(x=0,y=104))
        self.assertEqual(data["layout"]["native_hp_xy"],[22,80])
        self.assertEqual(data["layout"]["package_option_count"],0)
        self.assertEqual(data["layout"]["hud_layout_control"],"absent")
        self.assertEqual(data["ownership"]["shared_life_digit_icons_suppressed"],[3,4])
        self.assertIn("unverified",data["visibility"]["prediction_status"])

    def test_c_boundary_parser_ignores_comment_and_string_braces(self):
        source='void target(int x);\nstatic void target(int x) { const char *s="}"; /* { */ if(x){f();} }\nvoid next(){}'
        row=hud.function(source,"target")
        self.assertEqual(row["line"],2)
        self.assertTrue(row["source"].endswith('if(x){f();} }'))
        self.assertNotIn("next",row["source"])
        with self.assertRaises(ValueError):hud.function('void a(){ if(1){ }',"a")
        with self.assertRaises(ValueError):hud.function('void a();',"a")

    def test_unbounded_revision_and_path_rejected_without_git(self):
        with patch.object(hud.subprocess,"run") as run:
            for revision,path in (("HEAD","src/x.c"),(hud.BASE,"../secret"),(hud.BASE,"/absolute")):
                with self.assertRaises(ValueError):hud.committed(ROOT,revision,path)
            run.assert_not_called()

    def test_missing_or_wrong_original_rejected_before_source_lookup(self):
        with patch.object(hud,"committed") as lookup:
            for data in (b"",b"PS-X EXE"+bytes(522232)):
                with self.assertRaisesRegex(ValueError,"pinned original"):hud.audit(ROOT,ROOT,data)
            lookup.assert_not_called()

    @unittest.skipUnless(os.environ.get("MMX6_CONTENT_EXE") and os.environ.get("MMX6_X4_REPOSITORY"),
                         "Pinned original EXE and frozen X4 repository not supplied")
    def test_actual_original_and_committed_sources_reproduce_report(self):
        data=hud.audit(ROOT,Path(os.environ["MMX6_X4_REPOSITORY"]),Path(os.environ["MMX6_CONTENT_EXE"]).read_bytes())
        self.assertEqual(data,self.report())
        calls={r["pc"]:r["target"] for span in data["native_spans"] for r in span["direct_calls"]}
        self.assertEqual(calls["800244F8"],"80024F90")
        self.assertEqual(calls["80024520"],"800249D4")
        self.assertEqual(calls["80022AC8"],"800232D4")
        self.assertEqual(calls["80025FC0"],"80022960")
        self.assertEqual(calls["800349FC"],"80025FB0")

    def test_initializer_refuses_to_clobber_existing_receipt(self):
        root=Path(os.environ["TEMP"]).resolve(strict=True)
        self.assertNotEqual(root.drive.upper(),"C:")
        with tempfile.TemporaryDirectory(dir=root) as directory:
            exe=Path(directory)/"original";exe.write_bytes(bytes(522240))
            output=Path(directory)/"audit.json";output.write_text("retained evidence")
            with patch.object(hud,"audit",return_value={}),self.assertRaises(FileExistsError):
                hud.main(["--exe",str(exe),"--x4-repository",str(ROOT),"--output",str(output)])
            self.assertEqual(output.read_text(),"retained evidence")


if __name__=="__main__":unittest.main()
