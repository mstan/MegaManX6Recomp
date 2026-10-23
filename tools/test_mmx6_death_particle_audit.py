"""Original-source accounting/identity tests; never native death qualification."""
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import audit_mmx6_death_particles as death

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"docs/COOP_DEATH_PARTICLE_AUDIT.json"


class DeathSourceTests(unittest.TestCase):
    def report(self):return json.loads(REPORT.read_text())

    def test_exact_frozen_scope_and_no_inherited_runtime_passes(self):
        data=self.report()
        self.assertEqual(data["scope"],["R3","F4"])
        self.assertEqual({r["id"]:r["frozen_row_sha256"] for r in data["comparisons"]},death.DEFINITIONS)
        self.assertTrue(data["source_only"])
        self.assertTrue(all(r["local"]==r["netplay"]=="unverified" for r in data["comparisons"]))
        self.assertEqual(data["emission"]["runtime_status"],"unverified")

    def test_native_attempt_schedule_and_radial_angles_are_complete(self):
        data=self.report();schedule=data["emission"]
        self.assertEqual((schedule["random_attempts"],schedule["radial_attempts"],schedule["invocations"]),(44,32,40))
        self.assertEqual([(r["invocation"],r["radial_groups"]) for r in schedule["events"] if r["radial_groups"]],
                         [(0,[0]),(19,[1]),(38,[2,3])])
        self.assertEqual(sorted(sum(data["radial_angles"],[])),list(range(32)))
        self.assertIn("not_wall_clock_frames",schedule["unit"])
        self.assertIn("allocated slots may persist",data["retirement"]["radial"])

    def test_palette_and_excess_burst_findings_keep_correct_limits(self):
        data=self.report();findings={r["id"]:r["classification"] for r in data["findings"]}
        self.assertEqual(findings["native76"],"source_proven_native_behavior")
        self.assertEqual(findings["atlas-color"],"unverified_resource_gap")
        self.assertEqual(findings["repeat-burst"],"unverified_runtime_obligation")
        self.assertEqual(data["native_resource"]["compression_pointer"],"+38=0")
        self.assertIn("VRAM x32,y480",data["native_resource"]["clut"])
        self.assertEqual(data["pool"]["count"]*data["pool"]["stride"],0x2400)

    def test_native_call_decoder_uses_pc_region_and_rejects_unaligned_input(self):
        data=struct.pack("<II",0x0C012345,0)
        self.assertEqual(death.direct_calls(data,0x80010000),[dict(pc="80010000",target="80048D14")])
        for data,base in ((b"a",0x80010000),(bytes(4),0x80010001)):
            with self.assertRaises(ValueError):death.direct_calls(data,base)

    def test_wrong_original_identity_rejected_before_git_or_interpretation(self):
        with patch.object(death,"committed") as source:
            with self.assertRaisesRegex(ValueError,"pinned complete"):death.audit(ROOT,b"",b"")
            source.assert_not_called()

    @unittest.skipUnless(os.environ.get("MMX6_CONTENT_EXE") and os.environ.get("MMX6_CONTENT_DISC"),
                         "Pinned original EXE/raw disc not supplied")
    def test_actual_original_members_code_tables_and_audit_reproduce(self):
        exe_bytes=Path(os.environ["MMX6_CONTENT_EXE"]).read_bytes()
        raw=death.content.RawDisc(Path(os.environ["MMX6_CONTENT_DISC"]))
        try:archive=raw.extent(211185,1665024)
        finally:raw.stream.close()
        data=death.audit(ROOT,exe_bytes,archive);self.assertEqual(data,self.report())
        exe=death.content.Executable(exe_bytes)
        self.assertEqual(exe.word(0x80073ABC+8),0x8003CC78)
        self.assertEqual(exe.word(0x80047E7C),0x24027802) # Native fixed CLUT.
        calls={r["pc"]:r["target"] for span in data["native_spans"] for r in span["direct_calls"]}
        self.assertEqual(calls["8003DB04"],"8002C530")
        self.assertEqual(calls["8003DB84"],"8002C530")
        self.assertEqual(calls["80020C98"],"800206C0")
        self.assertEqual(calls["80047FF0"],"8002C9B0")
        self.assertNotIn("8002C9B0",[r["target"] for r in death.direct_calls(
            exe_bytes[exe.offset(0x80048000,0x30):exe.offset(0x80048000,0x30)+0x30],0x80048000)])
        broken=bytearray(exe_bytes);broken[exe.offset(0x8003DA8C,4)]^=1
        with self.assertRaises(ValueError):death.audit(ROOT,bytes(broken),archive)
        with self.assertRaisesRegex(ValueError,"counter contract"):
            death.emission_schedule(death.content.Executable(bytes(broken)))
        corrupted=bytearray(archive);corrupted[4096]^=1
        with self.assertRaises(ValueError):death.audit(ROOT,exe_bytes,bytes(corrupted))

    def test_output_refuses_existing_evidence(self):
        root=Path(os.environ["TEMP"]).resolve(strict=True);self.assertNotEqual(root.drive.upper(),"C:")
        with tempfile.TemporaryDirectory(dir=root) as directory:
            exe=Path(directory)/"original";exe.write_bytes(bytes(522240))
            report=Path(directory)/"audit";report.write_text("retained failed attempt")
            reader=SimpleNamespace(extent=Mock(return_value=b""),stream=SimpleNamespace(close=Mock()))
            with patch.object(death.content,"RawDisc",return_value=reader),patch.object(death,"audit",return_value={}),\
                    self.assertRaises(FileExistsError):
                death.main(["--exe",str(exe),"--disc","unused","--output",str(report)])
            self.assertEqual(report.read_text(),"retained failed attempt")
            reader.stream.close.assert_called_once()


if __name__=="__main__":unittest.main()
