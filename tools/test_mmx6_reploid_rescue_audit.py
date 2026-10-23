"""Source/codec tests only; none establishes a native rescue outcome."""
import copy
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import audit_mmx6_reploid_rescue as audit
from inventory_mmx6_coop_content import RawDisc

ROOT = Path(__file__).resolve().parents[1]


class FoundCodecTests(unittest.TestCase):
    def test_word_byte_and_nibble_boundaries_are_lossless_for_all128_ids(self):
        for identifier in range(128):
            cell = audit.found_slot(identifier)
            self.assertEqual(int(cell["byte_address"],16), audit.PLAY+0xD8+identifier//2)
            self.assertEqual(int(cell["word_address"],16)+(cell["shift"]//8), int(cell["byte_address"],16))
            self.assertEqual(int(cell["mask"],16), 15 << cell["shift"])
        self.assertEqual(audit.found_slot(7)["shift"],28)
        self.assertEqual(audit.found_slot(8)["shift"],0)
        self.assertEqual(audit.found_slot(127)["word_address"],"800CCFE4")
        self.assertEqual(audit.found_slot(127,base=audit.PLAY+0x118)["word_address"],"800CD024")
        for bad in (-1,128,256,True,1.0,"1"):
            with self.assertRaises(ValueError):
                audit.found_slot(bad)

    def test_all_physical_nibble_values_are_preserved_without_inventing_status1(self):
        raw=bytes((i%16)|(((i+1)%16)<<4) for i in range(64))
        rows=audit.decode_found(raw)
        self.assertEqual(len(rows),128)
        self.assertEqual([r["value"] for r in rows[::2]],list(i%16 for i in range(64)))
        for row in rows:
            if row["value"] not in (0,2,3,4):
                self.assertEqual(row["meaning"],"unknown_native_value")
        for raw in (bytes(63),bytes(65)):
            with self.assertRaises(ValueError):
                audit.decode_found(raw)

    def test_source_window_call_and_store_widths_are_decoded_from_instructions(self):
        # JAL target8004FF00, SB/H/SW at offsets4/6/8 of native a0.
        words=(0x0C013FC0,0xA0820004,0xA4820006,0xAC820008)
        result=audit.code_window(struct.pack("<4I",*words),0x80010000,"fixture",0x80010000,0x80010010)
        self.assertEqual(result["direct_calls"],[dict(address="80010000",target="8004FF00")])
        self.assertEqual([(s["bytes"],s["offset"],s["base_register"]) for s in result["stores"]],[(1,4,4),(2,6,4),(4,8,4)])
        for lo,hi in ((0x7FFFFFFC,0x80010004),(0x80010001,0x80010008),(0x80010000,0x80010014)):
            with self.assertRaises(ValueError):
                audit.code_window(bytes(16),0x80010000,"invalid",lo,hi)

    def test_native_table_bounds_widths_and_signedness(self):
        self.assertEqual(audit.table(b"\x80\xFF\x01\x02",0x80010000,0x80010000,2,2)["values"],[0xFF80,0x201])
        for address,count,width in ((0x7FFFFFFF,1,1),(0x80010000,3,2),(0x80010000,1,3),(0x80010000,0,4)):
            with self.assertRaises(ValueError):
                audit.table(bytes(4),0x80010000,address,count,width)


class DurableContractTests(unittest.TestCase):
    def setUp(self):
        self.inventory=(ROOT/"docs/COOP_X6_CONTENT.json").read_bytes()
        self.frozen=audit.frozen_inventory(self.inventory)
        self.report=json.loads((ROOT/"docs/COOP_REPLOID_RESCUE_AUDIT.json").read_text(encoding="utf-8"))

    def test_all128_native_definitions_and_seven_case_keys_are_preserved_exactly(self):
        self.assertEqual(len(self.report["reploids"]),128)
        for expected,row in zip(self.frozen["reploids"],self.report["reploids"]):
            self.assertEqual(row["inventory_definition"],expected)
            self.assertEqual(row["id"],expected["id"])
            self.assertEqual(row["inventory_definition_sha256"],audit.sha(audit.canonical(expected)))
            self.assertEqual(row["native_placement"]["subtype"],expected["native_id"])
            self.assertEqual(row["native_placement"]["address"],expected["address"])
            self.assertEqual(len(expected["checks"]),7)
            self.assertEqual(row["runtime_status"],"unverified")
        self.assertEqual(self.report["counts"],dict(reploids=128,reward_kinds=dict(none=88,life_upgrade=8,energy_upgrade=8,part=24),gameplay_passes=0))

    def test_source_drift_including_changed_or_missing_id_is_rejected(self):
        for change in (lambda d:d["reploids"].pop(),
                       lambda d:d["reploids"][0].update(native_id=1),
                       lambda d:d["reploids"][0].update(x=0)):
            changed=copy.deepcopy(self.frozen)
            change(changed)
            with self.assertRaisesRegex(ValueError,"SHA"):
                audit.frozen_inventory(json.dumps(changed).encode())

    def test_native_upgrade_ordinals_are_distinct_once_bits_and_parts_shared(self):
        for kind,start in (("life_upgrade",8),("energy_upgrade",24)):
            rows=[r for r in self.report["reploids"] if r["reward"]["kind"]==kind]
            self.assertEqual([r["reward"]["ordinal"] for r in rows],list(range(1,9)))
            self.assertEqual([int(r["reward"]["once_mask"],16) for r in rows],[1 << (start+i) for i in range(8)])
            self.assertTrue(all(r["reward"]["once_word"]=="800CCF3C" for r in rows))
        parts=[r["reward"] for r in self.report["reploids"] if r["reward"]["kind"]=="part"]
        self.assertEqual({int(r["code"],16) for r in parts},{1 << i for i in range(2,26)})
        self.assertTrue(all(r["beneficiary"]=="shared_parts" and r["once_word"]=="800CCF40" for r in parts))

    def test_relevant_adapter_contract_is_pinned_and_missing_entry_rejected(self):
        source=(ROOT/"src/mods/mmx6_coop_plugin.c").read_text(encoding="utf-8")
        config=(ROOT/"game.toml").read_text(encoding="utf-8")
        self.assertEqual(audit.adapter_contract(source,config),self.report["adapter"])
        for changed in (source.replace("0x8004EECC,pickup_collect","0x8004EECC,unrelated"),
                        source.replace("static int pickup_tick(","static int unrelated(")):
            with self.assertRaises(ValueError):
                audit.adapter_contract(changed,config)
        with self.assertRaises(ValueError):
            audit.adapter_contract(source,config.replace('"0x8004EC30"','"0x80000000"'))
        with self.assertRaises(ValueError):
            audit.source_function("static void incomplete(void) {", "incomplete")

    def test_output_initializer_refuses_existing_audit_without_clobber(self):
        with tempfile.TemporaryDirectory(prefix="x6-reploid-audit-",dir=os.environ["TEMP"]) as directory:
            root=Path(directory)
            for name in ("exe","archive","existing.json"):(root/name).write_bytes(b"preserve")
            argv=["audit", "--exe",str(root/"exe"),"--bin",str(root/"archive"),"--output",str(root/"existing.json")]
            with patch("sys.argv",argv),patch.object(audit,"audit",return_value={}):
                with self.assertRaises(FileExistsError):audit.main()
            self.assertEqual((root/"existing.json").read_bytes(),b"preserve")


@unittest.skipUnless(os.environ.get("MMX6_CONTENT_EXE") and os.environ.get("MMX6_CONTENT_DISC"),
                     "Set explicit original source paths for native table/window reproduction")
class OriginalSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image=Path(os.environ["MMX6_CONTENT_EXE"]).read_bytes()
        disc=RawDisc(Path(os.environ["MMX6_CONTENT_DISC"]))
        try:cls.archive=disc.inventory_files()["ROCK_X6.BIN"]
        finally:disc.stream.close()
        cls.inventory=(ROOT/"docs/COOP_X6_CONTENT.json").read_bytes()
        cls.adapter=(ROOT/"src/mods/mmx6_coop_plugin.c").read_text(encoding="utf-8")
        cls.config=(ROOT/"game.toml").read_text(encoding="utf-8")

    def test_actual_original_tables_windows_and128_placements_reproduce_report(self):
        reproduced=audit.audit(self.image,self.archive,self.inventory,self.adapter,self.config)
        self.assertEqual(reproduced,json.loads((ROOT/"docs/COOP_REPLOID_RESCUE_AUDIT.json").read_text(encoding="utf-8")))
        setter=next(w for w in reproduced["code_windows"] if w["id"]=="found_setter")
        self.assertEqual(setter["stores"][-1]["bytes"],4)  # Native nibble RMW writes its complete word.
        self.assertEqual(reproduced["tables"][0]["values"][:3],[0x8004E800,0x8004EA78,0x8004F880])

    def test_modified_native_input_is_rejected_before_table_interpretation(self):
        for is_exe in (True,False):
            original=self.image if is_exe else self.archive
            changed=bytearray(original);changed[-1]^=1
            with self.assertRaisesRegex(ValueError,"pinned original"):
                audit.audit(bytes(changed) if is_exe else self.image,
                            self.archive if is_exe else bytes(changed), self.inventory,self.adapter,self.config)


if __name__=="__main__":
    unittest.main()
