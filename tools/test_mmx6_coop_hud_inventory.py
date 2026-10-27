"""Focused ammo ownership, source-ROI and failed-trace admission negatives."""
import copy
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

import mmx6_coop_hud_inventory as ammo
import qualify_mmx6_coop_hud_inventory as runner


def row(energies=(0x1800, 0x1000)):
    result = dict(observation=dict(players=[]))
    for seat, energy in enumerate(energies):
        body = bytearray(0x158)
        body[0x93] = 1 if seat == 0 else 8
        values = [0]+[0x2000]*8; values[body[0x93]] = energy
        struct.pack_into('<9h', body, 0xA8, *values)
        struct.pack_into('<H', body, 0x14A, 0x2000)
        result[('p1_body_hex', 'p2_body_hex')[seat]] = body.hex()
        result['observation']['players'].append(dict(character=seat, hp=32, weapon=body[0x93], ammo=values))
    return result


class AmmoTests(unittest.TestCase):
    def test_fixture_idle_keeps_nonmaximum_hp_and_refuses_dead_or_scripted_actors(self):
        def idle(tick):
            value = row()
            value['observation'].update(tick=tick,native_mode=10,native_phase=0,pause_owner=0,
                scene_owner=0,failed=0,mailbox=0,ready=1,enrolled=1,lifecycle=[0,0])
            for seat, player in enumerate(value['observation']['players']):
                player.update(active=1,state=1,action=2,hp=30+seat*2,x_raw=144+seat*24,y_raw=1115)
            return value
        ctx = dict(set_input=Mock())
        case = SimpleNamespace(sample=Mock(side_effect=[idle(10),idle(12)]),
            adapter=SimpleNamespace(transport_window=Mock()),evidence={})
        accepted = ammo.settle_fixture_idle(ctx,case,1)
        self.assertEqual([p['hp'] for p in accepted['observation']['players']],[30,32])
        self.assertEqual([call.args for call in ctx['set_input'].call_args_list],[(0,0),(1,0)])
        for mutation in ('dead','scripted'):
            altered = idle(10)
            if mutation == 'dead':
                altered['observation']['players'][1]['hp'] = 0
            else:
                body = bytearray.fromhex(altered['p2_body_hex']);body[0xE0]=1
                altered['p2_body_hex'] = body.hex()
            case = SimpleNamespace(sample=Mock(return_value=altered),
                adapter=SimpleNamespace(transport_window=Mock()),evidence={})
            with self.subTest(mutation=mutation), patch.object(ammo.time,'monotonic',side_effect=[0,0,2]):
                with self.assertRaises(ammo.debug.DebugError):
                    ammo.settle_fixture_idle(ctx,case,1)

    @unittest.skipUnless(os.environ.get('MMX6_CONTENT_EXE') and os.environ.get('MMX6_CONTENT_DISC'),
                         'Pinned original EXE and disc not supplied')
    def test_zero_option_activation_is_bound_to_original_code(self):
        source = ammo.load_source(os.environ['MMX6_CONTENT_EXE'],os.environ['MMX6_CONTENT_DISC'])
        self.assertEqual(source['zero_yammar']['selected_weapon'],3)
        zero = bytearray(ammo.hud.resources.zero_contact.load_zero_overlay(os.environ['MMX6_CONTENT_DISC']))
        zero[0x254] ^= 1
        with patch.object(ammo.hud.resources.zero_contact,'load_zero_overlay',return_value=bytes(zero)):
            with self.assertRaisesRegex(ammo.debug.DebugError,'Yammar activation changed'):
                ammo.load_source(os.environ['MMX6_CONTENT_EXE'],os.environ['MMX6_CONTENT_DISC'])

    def test_energy_observation_rejects_mismatched_or_invalid_actor_body(self):
        sample = row()
        self.assertEqual([v['energy'] for v in ammo.selected_resources(sample)], [0x1800, 0x1000])
        for mutation in ('mismatch', 'negative', 'capacity', 'truncated'):
            altered = copy.deepcopy(sample)
            body = bytearray.fromhex(altered['p1_body_hex'])
            if mutation == 'mismatch':
                altered['observation']['players'][0]['weapon'] = 2
            elif mutation == 'negative':
                struct.pack_into('<h', body, 0xAA, -1)
                altered['observation']['players'][0]['ammo'][1] = -1
            elif mutation == 'capacity':
                struct.pack_into('<H', body, 0x14A, 0)
            else:
                body.pop()
            altered['p1_body_hex'] = body.hex()
            with self.subTest(mutation=mutation), self.assertRaises(ammo.debug.DebugError):
                ammo.selected_resources(altered)

    def test_private_ownership_requires_actual_spend_and_unchanged_other_actor(self):
        before, spent = row(), row((0x1700, 0x1000))
        self.assertTrue(all(ammo.ownership_checks(before, spent, 0).values()))
        self.assertFalse(all(ammo.ownership_checks(before, before, 0).values()))
        self.assertFalse(all(ammo.ownership_checks(before, row((0x1700, 0xF00)), 0).values()))
        self.assertFalse(all(ammo.ownership_checks(before, row((0x1900, 0x1000)), 0).values()))

    def test_source_derived_regions_follow_both_layouts_at_all_three_aspects(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as directory:
            for layout in ('stacked', 'side_by_side'):
                for width, height in ammo.ASPECTS:
                    path = Path(directory)/f'{layout}-{width}x{height}.png'
                    Image.new('RGB', (width, height)).save(path)
                    measured = ammo.ammo_regions(path, row(), layout)
                    self.assertEqual(measured['image_size'], [width, height])
                    self.assertEqual(measured['regions'][0]['native_anchor'], [31, 80])
                    self.assertEqual(measured['regions'][1]['native_anchor'],
                                     [31, 184] if layout == 'stacked' else [87, 80])
                    self.assertTrue(all(len(bytes.fromhex(r['normalized_rgb_hex'])) == 990 for r in measured['regions']))
                    altered = Image.open(path).convert('RGB')
                    x0, y0, x1, y1 = measured['regions'][0]['drawable_roi']
                    ImageDraw.Draw(altered).rectangle((x0, y0, x1-1, y1-1), fill='red')
                    altered.save(path)
                    comparison = ammo.compare_regions(measured, ammo.ammo_regions(path, row((0x1700, 0x1000)), layout))
                    self.assertEqual([r['changed_of_330_pixels'] for r in comparison], [330, 0])
                    self.assertTrue(all('no color/fill' in r['admission'] for r in comparison))

    @unittest.skipUnless(os.environ.get('MMX6_CONTENT_EXE'), 'Pinned original not supplied')
    def test_pinned_original_ammo_function_and_instruction_provenance(self):
        source = ammo.load_source(os.environ['MMX6_CONTENT_EXE'])
        self.assertEqual(source['ammo_hud']['sha256'], ammo.AMMO_SHA)
        self.assertEqual(source['ammo_hud']['source_instructions']['0x80024ba4'], '0x2404001f')
        self.assertEqual(source['ammo_hud']['source_instructions']['0x80024bdc'], '0x24060050')


def recording(candidate, *, failure=runner.TAINT_FAILURE, status_failure=None, mode='offline'):
    codec = runner.owner.codec
    directory = candidate/'saves/game/input-recordings/session-test'; directory.mkdir(parents=True)
    settings = dict(declared_scope_available=1, input=dict(ports=[dict(seat=seat, device_kind=1,
        configured_mode=2, connected=1, type=0) for seat in (0, 1)]))
    bundles = {'settings.json': codec.canonical(settings), 'content.json': b'{}\n',
               'simulation-contract.json': codec.canonical(dict(interpreted_overlays_sealed=1, oracle=0))}
    identity = dict(image_sha256='1'*64, manifest_sha256='2'*64, execution_id='synthetic-fixture',
        settings_sha256=codec.sha256(bundles['settings.json']), content_sha256=codec.sha256(bundles['content.json']),
        simulation_contract_sha256=codec.sha256(bundles['simulation-contract.json']),
        mode=mode, profile=(None if mode == 'offline' else dict(id='synthetic.lab', revision=1,
            selected_sha256='3'*64)), cards=[None, None], baseline=None)
    stream = io.BytesIO(); encoder = codec.Encoder(stream, identity)
    encoder.append(dict(type='N', order=0, native=0, cycles=100, sim_tick=(None if mode == 'offline' else 0), frame=0,
                        caller=0x80012220, pads=[[0, 0, 0], [0, 0, 0]]))
    encoder.finish(failure=failure)
    bundles['inputs.jsonl'] = stream.getvalue()
    bundles['status.json'] = codec.canonical(dict(contract=codec.CONTRACT, epoch=1, failure=
        (failure if status_failure is None else status_failure) or '', schema=1,
        scope=runner.owner.artifacts.STATUS_SCOPE, status='failed' if failure else 'finalized'))
    for name, data in bundles.items():
        (directory/name).write_bytes(data)
    return directory, bundles


class TaintedAdmissionTests(unittest.TestCase):
    def test_netplay_requires_explicit_mode_and_still_refuses_capture_and_replay(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as directory:
            root = Path(directory); recording(root/'candidate', mode='netplay')
            with self.assertRaisesRegex(ValueError, 'exact offline'):
                runner.inspect_tainted_recording(root/'candidate', '1'*64, '2'*64, root/'wrong-mode')
            result = runner.inspect_tainted_recording(root/'candidate', '1'*64, '2'*64,
                root/'archive', expected_mode='netplay')
            self.assertFalse(result['replay_admitted']); self.assertFalse(result['finalized_capture_admitted'])
            self.assertEqual(result['strict_refusals']['ordinary_capture']['message'],
                'capture explicitly failed: '+runner.TAINT_FAILURE)
            self.assertEqual(result['strict_refusals']['offline_replay']['message'],
                'network trace cannot be replayed offline')

    def test_netplay_unrelated_failure_is_not_accepted_as_fixture_taint(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as directory:
            root = Path(directory)
            recording(root/'candidate', mode='netplay', failure='recording worker I/O or validation failed')
            with self.assertRaisesRegex(ValueError, 'exact canonical failed'):
                runner.inspect_tainted_recording(root/'candidate', '1'*64, '2'*64,
                    root/'archive', expected_mode='netplay')
            self.assertFalse((root/'archive').exists())

    def test_exact_failed_fixture_is_archived_and_both_strict_paths_refuse_it(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as directory:
            root = Path(directory); source, bundles = recording(root/'candidate')
            result = runner.inspect_tainted_recording(root/'candidate', '1'*64, '2'*64, root/'archive')
            self.assertEqual(result['terminal_failure'], runner.TAINT_FAILURE)
            self.assertFalse(result['replay_admitted']); self.assertFalse(result['finalized_capture_admitted'])
            self.assertEqual(set(result['strict_refusals']), {'ordinary_capture', 'offline_replay'})
            for name, data in bundles.items():
                self.assertEqual((root/'archive'/name).read_bytes(), data)
                self.assertEqual((source/name).read_bytes(), data)

    def test_clean_finalized_recording_cannot_be_labeled_fixture_failure(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as directory:
            root = Path(directory); recording(root/'candidate', failure=None)
            with self.assertRaisesRegex(ValueError, 'exact canonical failed'):
                runner.inspect_tainted_recording(root/'candidate', '1'*64, '2'*64, root/'archive')
            self.assertFalse((root/'archive').exists())

    def test_other_failure_truncation_and_status_mismatch_are_not_expected_taint(self):
        for mutation in ('other_failure', 'truncation', 'status_mismatch', 'image_mismatch', 'status_noncanonical'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(dir=os.environ['TEMP']) as directory:
                root = Path(directory)
                path, bundles = recording(root/'candidate',
                    failure='recording worker I/O or validation failed' if mutation == 'other_failure' else runner.TAINT_FAILURE,
                    status_failure='wrong failure' if mutation == 'status_mismatch' else None)
                if mutation == 'truncation':
                    (path/'inputs.jsonl').write_bytes(bundles['inputs.jsonl'][:-1])
                if mutation == 'status_noncanonical':
                    (path/'status.json').write_text(json.dumps(json.loads(bundles['status.json']), indent=2)+'\n')
                with self.assertRaises(ValueError):
                    runner.inspect_tainted_recording(root/'candidate', '3'*64 if mutation == 'image_mismatch' else '1'*64,
                                                    '2'*64, root/'archive')
                self.assertFalse((root/'archive').exists())


if __name__ == '__main__':
    unittest.main()
