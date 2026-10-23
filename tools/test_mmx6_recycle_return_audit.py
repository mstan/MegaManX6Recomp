"""Source and pure-policy tests; none is a native route qualification."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_mmx6_recycle_return as audit


class PolicyTests(unittest.TestCase):
    def test_positive_exit_namespaces_are_variant_specific(self):
        first=audit.exit_policy(1,0)
        second=audit.exit_policy(0x41,1,1)
        other=audit.exit_policy(127,2,1)
        self.assertEqual((first["major"],first["checkpoint"],first["native_play5f_or"]),(19,2,16))
        self.assertEqual(second["next_namespace"],dict(major=20,stage=11,section=0,checkpoint=4))
        self.assertEqual(other["next_namespace"],dict(major=12,stage=15,section=0,checkpoint=0))
        for value in (first,second,other):
            self.assertEqual((value["stage"],value["section"]),(20,1))
            self.assertNotEqual(value["next_namespace"]["stage"],4)

    def test_negative_and_zero_are_not_campaign_returns(self):
        for transition in (128,129,255):
            for variant in (0,1,2,255):
                row=audit.exit_policy(transition,variant,1)
                self.assertEqual((row["major"],row["stage"],row["section"],row["checkpoint"]),(9,20,1,1))
                self.assertIsNone(row["next_namespace"])
        self.assertIsNone(audit.exit_policy(0,0)["major"])
        for args in ((True,0),(-1,0),(256,0),(1,-1),(1,256),(1,0,False)):
            with self.assertRaises(ValueError):audit.exit_policy(*args)

    def test_initial_scan_strict_edges_and_native_wrap(self):
        self.assertFalse(audit.initial_scan_window(100,224,52,200))
        self.assertTrue(audit.initial_scan_window(100,224,53,200))
        self.assertFalse(audit.initial_scan_window(100,224,468,200))
        self.assertTrue(audit.initial_scan_window(100,224,467,200))
        self.assertFalse(audit.initial_scan_window(100,224,100,176))
        self.assertFalse(audit.initial_scan_window(100,224,100,512))
        self.assertTrue(audit.initial_scan_window(100,224,100,511))
        # Signed16 overflow does not become an invented wrapping safe region.
        self.assertFalse(audit.initial_scan_window(32767,224,32766,200))
        for args in ((True,0,0,0),(0,0,32768,0),(0,0,0,-32769)):
            with self.assertRaises(ValueError):audit.initial_scan_window(*args)


@unittest.skipUnless(os.getenv("MMX6_CONTENT_EXE") and os.getenv("MMX6_CONTENT_DISC"),
                     "Pinned local original EXE/raw disc not configured")
class OriginalSourceTests(unittest.TestCase):
    def inputs(self):
        return Path(os.environ["MMX6_CONTENT_EXE"]),Path(os.environ["MMX6_CONTENT_DISC"])

    def test_exact_source_reproduction_and_bounded_reads(self):
        original=audit.content.RawDisc
        reads=[]
        class Recorded(original):
            def extent(self,lba,size):
                reads.append((lba,size))
                return super().extent(lba,size)
        with patch.object(audit.content,"RawDisc",Recorded):result=audit.audit(*self.inputs())
        self.assertEqual(reads,[(211185,1665024),(211998,4096),(211998+13092,655360)])
        committed=Path(__file__).resolve().parents[1]/"docs/COOP_RECYCLE_RETURN_AUDIT.json"
        self.assertEqual(result,json.loads(committed.read_text(encoding="utf-8")))
        self.assertEqual((result["placement_census"]["primary_count"],result["placement_census"]["secondary_count"]),(31,27))
        self.assertEqual(result["placement_census"]["authored_category0_type1C"],[])
        self.assertEqual([row["index"] for row in result["resource"]["assets"]],[8,9])
        self.assertEqual(result["entrance_interaction"]["rectangle"],[0,224,240,416])
        self.assertIsNone(result["accepted_input_route"])
        self.assertEqual((result["local_coop"],result["netplay"]),("unverified","unverified"))

    def test_source_selector_drift_refuses(self):
        exe_path,disc_path=self.inputs()
        exe=audit.checkpoint.original_executable(exe_path)
        original_word=exe.word
        exe.word=lambda address:0x800F238C if address==0x80076384 else original_word(address)
        with patch.object(audit.checkpoint,"original_executable",return_value=exe):
            with self.assertRaisesRegex(ValueError,"selectors differ"):
                audit.load_original(exe_path,disc_path)

    def test_cli_refuses_clobber_and_check_preserves_bytes(self):
        exe_path,disc_path=self.inputs()
        parent=os.environ.get("TMP") or os.environ.get("TEMP")
        self.assertTrue(parent and Path(parent).drive.upper() in ("F:","G:"))
        with tempfile.TemporaryDirectory(dir=parent) as folder:
            target=Path(folder)/"audit.json"
            target.write_bytes(b"preserve prior evidence\n")
            args=["audit_mmx6_recycle_return.py","--original",str(exe_path),"--disc",str(disc_path),"--out",str(target)]
            with patch("sys.argv",args):
                with self.assertRaises(FileExistsError):audit.main()
            self.assertEqual(target.read_bytes(),b"preserve prior evidence\n")
            with patch("sys.argv",args+["--check"]):
                with self.assertRaises(SystemExit):audit.main()
            self.assertEqual(target.read_bytes(),b"preserve prior evidence\n")


if __name__=="__main__":unittest.main()
