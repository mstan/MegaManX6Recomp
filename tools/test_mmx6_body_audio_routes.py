"""Original-source caller/record corruption checks; no game runner."""
import copy
import json
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import audit_mmx6_body_audio_routes as subject


class BodyRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        exe, disc = os.environ.get('MMX6_AUDIO_EXE'), os.environ.get('MMX6_AUDIO_DISC')
        if not exe or not disc: raise unittest.SkipTest('Original MMX6 EXE/disc required')
        cls.sources = subject.original.original_sources(Path(exe), Path(disc))
        subject.prove_routes(*cls.sources)

    def test_original_routes_match_committed_receipt(self):
        receipt = json.loads((Path(__file__).resolve().parents[1]/'docs/COOP_BODY_AUDIO_ROUTES.json').read_bytes())
        self.assertEqual(subject.prove_routes(*self.sources), receipt)
        self.assertEqual([r['tones'][0]['tone'] for r in receipt['body_records']], [1,3,4,5,6,7,8,9])
        self.assertEqual(sum(r['phase']==2 for r in receipt['stop_callers']), 2)

    def test_every_stop_call_delay_argument_and_actor_binding_is_checked(self):
        exe, zero, banks = self.sources
        for site, record, entry, phase in subject.STOPS:
            for pc in (site, site+4, entry+20 if entry==0x8003F58C else entry+8):
                data = bytearray(exe.data)
                at = exe.offset(pc,4)
                struct.pack_into('<I', data, at, exe.word(pc)^4)
                with self.subTest(site=hex(site), pc=hex(pc)), self.assertRaises(ValueError):
                    subject.prove_routes(subject.original.content.Executable(bytes(data)), zero, banks)

    def test_wrong_record_tone_cannot_inherit_a_private_route(self):
        exe, zero, banks = self.sources
        rows = subject.original.resolve_records(banks)
        for record in range(1,9):
            changed = copy.deepcopy(rows)
            next(r for r in changed if (r['group'],r['record'])==(1,record))['tones'][0]['tone'] ^= 1
            with patch.object(subject.original,'resolve_records',return_value=changed), self.assertRaises(ValueError):
                subject.prove_routes(exe, zero, banks)

    def test_original_overlay_sound_actor_is_required(self):
        exe, zero, banks = self.sources
        for site in (0x801EA038,0x801EA168):
            changed=bytearray(zero);struct.pack_into('<I',changed,site+4-subject.original.ZERO_BASE,0x00003021)
            with self.assertRaises(ValueError): subject.prove_routes(exe, bytes(changed), banks)


if __name__ == '__main__':
    unittest.main()
