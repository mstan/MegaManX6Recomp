"""Bounded CURRENT source reproduction and negative mutation guards only."""
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import audit_mmx6_current_data as current


class GuardTests(unittest.TestCase):
    def test_pinned_full_originals_rejected_before_parsing(self):
        with patch.object(current.content, 'Executable') as parsed:
            with self.assertRaisesRegex(ValueError, 'pinned complete original'):
                current.audit(b'not an executable', b'not an archive')
            parsed.assert_not_called()

    def test_span_is_aligned_bounded_and_hash_checked(self):
        data = bytes(range(16)); expected = hashlib.sha256(data[4:12]).hexdigest()
        result = current.checked_span(data, 0x80000000, 'fixture', 0x80000004, 0x8000000C, expected)
        self.assertEqual(result['bytes'], 8)
        self.assertNotIn('code_hex', result)
        for start, end in ((0x7FFFFFFC,0x80000004),(0x80000001,0x80000008),
                           (0x80000008,0x80000008),(0x8000000C,0x80000014)):
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, 'bounded image'):
                current.checked_span(data, 0x80000000, 'fixture', start, end, expected)
        changed = bytearray(data); changed[8] ^= 1
        with self.assertRaisesRegex(ValueError, 'source span changed'):
            current.checked_span(changed, 0x80000000, 'fixture', 0x80000004, 0x8000000C, expected)

    def test_direct_scan_keeps_j_and_jal_and_ignores_partial_tail(self):
        target = current.PACK; encoded = (target >> 2)&0x3FFFFFF
        payload = struct.pack('<5I', 0, (3<<26)|encoded, (2<<26)|encoded,
                              (3<<26)|(encoded+1), 0x0080F809)+b'\x50\x6f'
        self.assertEqual(current.direct_calls(payload, 0x80010000, target),
                         [(0x80010004,'JAL'), (0x80010008,'J')])
        # J-format targets inherit the high region from PC+4.
        self.assertEqual(current.direct_calls(payload, 0x90010000, target), [])
        for base, target_ in ((1,target),(0x80000000,target+1),(True,target)):
            with self.assertRaisesRegex(ValueError, 'aligned 32-bit'):
                current.direct_calls(payload, base, target_)

    def test_missing_duplicate_extra_and_wrong_pack_callers_are_rejected(self):
        good = list(current.EXPECTED_CALLERS)
        current.check_callers(list(reversed(good)))
        for changed in (good[:1], good+[good[0]], good+[('exe',0x80010000,'JAL')],
                        [('bin18',0x800ED15C,'J')]+good[1:]):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'direct caller set changed'):
                current.check_callers(changed)

    def test_output_creation_is_exclusive_and_check_never_mutates(self):
        report = dict(source_only=True, status='source_mapped_runtime_unverified')
        rendered = json.dumps(report, indent=2)+'\n'
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as directory:
            root = Path(directory); output = root/'source.json'
            argv = ['--original-exe',str(root/'original'), '--disc',str(root/'disc')]
            with patch.object(current, 'load_sources', return_value=(b'',b'')), patch.object(current,'audit',return_value=report):
                self.assertEqual(current.main(argv+['--out',str(output)]), 0)
                self.assertEqual(output.read_bytes(), rendered.encode())
                with self.assertRaises(FileExistsError):
                    current.main(argv+['--out',str(output)])
                self.assertEqual(current.main(argv+['--check',str(output)]), 0)
                output.write_text('retained mismatch', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'source audit differs'):
                    current.main(argv+['--check',str(output)])
                self.assertEqual(output.read_text(), 'retained mismatch')


@unittest.skipUnless(os.environ.get('MMX6_CONTENT_EXE') and os.environ.get('MMX6_CONTENT_DISC'),
                     'Pinned original EXE and raw disc not supplied')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.executable, cls.archive = current.load_sources(os.environ['MMX6_CONTENT_EXE'], os.environ['MMX6_CONTENT_DISC'])

    def test_actual_original_report_chain_and_exact_caller_set(self):
        result = current.audit(self.executable, self.archive)
        self.assertTrue(result['source_only'])
        self.assertEqual(result['status'], 'source_mapped_runtime_unverified')
        self.assertEqual(result['scan_scope']['bin_members'], 59)
        self.assertEqual([(r['region'],r['address']) for r in result['direct_pack_callers']],
                         [('bin18','800ED15C'), ('bin20','800EACB0')])
        self.assertEqual(result['pack_contract']['header_value'], 1)
        self.assertEqual(result['intro_route']['positive_exit_value'], 0x40)
        self.assertEqual(result['intro_route']['destination'], dict(major=0x0C,stage=15,section=0,checkpoint=0))
        self.assertEqual(result['report_route']['entries'][0], '800EAC28')
        self.assertEqual(len(result['source_spans']), len(current.SPANS))
        self.assertNotIn('passed', json.dumps(result))
        self.assertTrue(any('No runtime' in limit for limit in result['limits']))
        self.assertEqual(current.audit(self.executable, self.archive), result)

    def test_original_mutations_rejected_at_full_identity_boundary(self):
        altered = bytearray(self.executable); altered[2048] ^= 1
        with self.assertRaisesRegex(ValueError, 'pinned complete original'):
            current.audit(altered, self.archive)
        altered = bytearray(self.archive); altered[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'pinned original ROCK_X6'):
            current.audit(self.executable, altered)

    def test_key_source_span_mutations_rejected_independently(self):
        exe = current.content.Executable(self.executable)
        members = current.content.archive_members(self.archive)
        for region, name, start, end, expected in current.SPANS:
            if region == 'exe':
                payload, base = bytearray(self.executable[2048:2048+exe.size]), exe.base
            else:
                member = members[int(region[3:])]; begin = member['sector']*2048
                payload, base = bytearray(self.archive[begin:begin+member['size']]), current.content.OVERLAY_BASE
            payload[start-base] ^= 1
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'source span changed'):
                current.checked_span(payload, base, name, start, end, expected)


if __name__ == '__main__':
    unittest.main()
