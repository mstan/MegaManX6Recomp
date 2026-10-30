"""Reject unilateral/partial fixture receipts before named mechanic admission."""
import copy
from pathlib import Path
import tempfile
import tomllib
import unittest

import mmx6_coop_intro_fixture as intro


class NamedPrerequisiteCatalogTests(unittest.TestCase):
    def test_named_positions_are_explicit_lab_only_with_strict_choice_set(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source = Path(__file__).resolve().parents[1]
        normal = tomllib.loads((source/'mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml').read_text(encoding='utf-8'))
        self.assertFalse(any(o.get('id') in ('lab_checkpoint', 'lab_contact_protection', 'lab_starting_hp_p1', 'lab_starting_hp_p2', 'lab_earned_weapons') for o in normal.get('option', [])))
        catalog = (source/'packaging/lab/coop-checkpoint-option.toml').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True)
            manifest.write_text(catalog, encoding='utf-8')
            state = directory/'mods/state.toml'
            initial = '[[feature]]\nid = "prototype"\nenabled = true\n'
            state.write_text(initial, encoding='utf-8')
            for option in ('intro_before_doors', 'intro_before_explosion', 'recycle_cp2', 'recycle_portal_cp2', 'recycle_distant_cp2', 'recycle_fallen_cp2', 'recycle_fallen_guest_cp2', 'secretlab2b_enemy_cp0', 'refight_portal_cp1', 'refight_distant_cp1', 'heatnix_cp7', 'sigma_cp1', 'northpole_ice_cp3', 'turtloid_rain_cp1', 'alternate_boss_cp1'):
                state.write_text(initial, encoding='utf-8')
                receipt = pair.select_checkpoint(directory, enabled=True, option=option)
                self.assertEqual(receipt['option'], option)
                self.assertIn('lab_checkpoint = "'+option+'"', state.read_text(encoding='utf-8'))
            state.write_text(initial, encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, option='arbitrary_position')
            self.assertEqual(state.read_text(encoding='utf-8'), initial)
            # Recycle must be present in the exact agreed catalog. An otherwise
            # current old catalog cannot admit a unilateral new destination.
            recycle_choice = '\n[[option.choice]]\nvalue = "recycle_cp2"\nlabel = "Recycle section 1 checkpoint 2 prerequisite"\n'
            self.assertIn(recycle_choice, catalog)
            manifest.write_text(catalog.replace(recycle_choice, ''), encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, option='recycle_cp2')
            self.assertEqual(state.read_text(encoding='utf-8'), initial)
            # An old five-choice catalog cannot silently authorize the newly
            # named destination; every peer must hash the exact current set.
            old_catalog = catalog[:catalog.index('\n[[option.choice]]\nvalue = "intro_before_explosion"')]
            manifest.write_text(old_catalog, encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, option='intro_before_explosion')
            self.assertEqual(state.read_text(encoding='utf-8'), initial)
            manifest.write_text(catalog.replace('value = "intro_before_doors"', 'value = "arbitrary_position"'), encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, option='intro_before_doors')
            self.assertEqual(state.read_text(encoding='utf-8'), initial)

    def test_protection_requires_explicit_typed_prelaunch_choice(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source = Path(__file__).resolve().parents[1]
        catalog = (source/'packaging/lab/coop-checkpoint-option.toml').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True); manifest.write_text(catalog, encoding='utf-8')
            state = directory/'mods/state.toml'; initial = '[[feature]]\nid = "prototype"\nenabled = true\n'
            for selected in ('off', 'on'):
                state.write_text(initial, encoding='utf-8')
                receipt = pair.select_checkpoint(directory, enabled=True, option='recycle_cp2', contact_protection=selected)
                self.assertEqual(receipt['option'], 'recycle_cp2')
                self.assertEqual(receipt['contact_protection'], selected)
                parsed = tomllib.loads(state.read_text(encoding='utf-8'))
                self.assertEqual(parsed['feature'][0]['values']['lab_contact_protection'], selected)
                self.assertEqual(parsed['feature'][0]['values']['lab_checkpoint'], 'recycle_cp2')
                self.assertEqual(state.read_text(encoding='utf-8').count('lab_checkpoint ='), 1)
                self.assertEqual(state.read_text(encoding='utf-8').count('lab_contact_protection ='), 1)
            state.write_text(initial, encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, contact_protection='arbitrary')
            self.assertEqual(state.read_text(encoding='utf-8'), initial)
            manifest.write_text(catalog.replace('id = "lab_contact_protection"', 'id = "unrelated"'), encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, contact_protection='on')
            self.assertEqual(state.read_text(encoding='utf-8'), initial)

    def test_starting_hp_pair_is_exact_typed_prelaunch_only(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source = Path(__file__).resolve().parents[1]
        catalog = (source/'packaging/lab/coop-checkpoint-option.toml').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); manifest = directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True); manifest.write_text(catalog, encoding='utf-8')
            state = directory/'mods/state.toml'; initial = '[[feature]]\nid = "prototype"\nenabled = true\n'
            for hp in (('off', 'off'), ('1', '32'), ('17', '23')):
                state.write_text(initial, encoding='utf-8')
                receipt = pair.select_checkpoint(directory, enabled=True, option='turtloid_rain_cp1', starting_hp=hp)
                values = tomllib.loads(state.read_text())['feature'][0]['values']
                self.assertEqual(receipt['starting_hp'], list(hp))
                self.assertEqual([values['lab_starting_hp_p1'], values['lab_starting_hp_p2']], list(hp))
                for key in ('lab_checkpoint', 'lab_starting_hp_p1', 'lab_starting_hp_p2'):
                    self.assertEqual(state.read_text().count(key+' ='), 1)
            for hp in ((1, 'off'), ('0', 'off'), ('33', 'off'), ('01', 'off'), ('1',), '1'):
                state.write_text(initial, encoding='utf-8')
                with self.subTest(hp=hp), self.assertRaises(ValueError):
                    pair.select_checkpoint(directory, enabled=True, starting_hp=hp)
                self.assertEqual(state.read_text(), initial)
            bad = catalog.replace('value = "32"', 'value = "33"')
            manifest.write_text(bad, encoding='utf-8');state.write_text(initial, encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, starting_hp=('1', 'off'))
            self.assertEqual(state.read_text(), initial)

    def test_earned_weapons_commits_with_hp_and_refuses_unavailable_catalog(self):
        import qualify_mmx6_coop_intro_fixture_pair as pair
        source = Path(__file__).resolve().parents[1]
        catalog = (source/'packaging/lab/coop-checkpoint-option.toml').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); manifest = directory/'mods/bundled/mmx6.local-coop/0.0.1/manifest.toml'
            manifest.parent.mkdir(parents=True); manifest.write_text(catalog, encoding='utf-8')
            state = directory/'mods/state.toml'; initial = '[[feature]]\nid = "prototype"\nenabled = true\n'
            for selected in ('off', 'all'):
                state.write_text(initial, encoding='utf-8')
                receipt = pair.select_checkpoint(directory, enabled=True, option='recycle_cp2',
                    starting_hp=('17', '23'), earned_weapons=selected)
                values = tomllib.loads(state.read_text())['feature'][0]['values']
                self.assertEqual(receipt['earned_weapons'], selected)
                self.assertEqual(values['lab_earned_weapons'], selected)
                self.assertEqual([values['lab_starting_hp_p1'], values['lab_starting_hp_p2']], ['17', '23'])
            state.write_text(initial, encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, earned_weapons='invalid')
            self.assertEqual(state.read_text(), initial)
            manifest.write_text(catalog.replace('id = "lab_earned_weapons"', 'id = "unavailable"'), encoding='utf-8')
            with self.assertRaises(ValueError):
                pair.select_checkpoint(directory, enabled=True, earned_weapons='all')
            self.assertEqual(state.read_text(), initial)

    def test_hp_receipt_is_separate_from_checkpoint_authority(self):
        class Client:
            def read(self, address, size):
                self.requested = (address, size); return bytes((2, 1, 0, 1))
        client = Client(); actual = intro.starting_hp_receipt(client)
        self.assertEqual(actual, dict(status=2, requested=[1, 0], applied_mask=1, raw_hex='02010001'))
        self.assertEqual(client.requested, (intro.debug.DIAGNOSTIC_ADDRESS+0xC0, 4))


class NegotiatedReceiptTests(unittest.TestCase):
    def complete(self):
        return dict(generation=1, state=3, reason=0, stage=0, section=0, checkpoint=2,
            nonce=intro.NONCE, initializer_entries=1, record=intro.RECORD, tainted=1,
            authority=1, latch=2, prior_chord=0)

    def test_matching_one_shot_receipts_and_ordinary_mailbox_are_distinct(self):
        good = self.complete()
        self.assertEqual(intro.validate_completion([good, copy.deepcopy(good)])['checkpoint'], 2)
        for field, value in (('authority', 0), ('tainted', 0), ('latch', 1), ('state', 2),
                             ('initializer_entries', 0), ('initializer_entries', 2), ('generation', 2),
                             ('nonce', 1), ('record', '8007212C'), ('checkpoint', 1), ('reason', 1)):
            wrong = dict(good, **{field:value})
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                intro.validate_completion([good, wrong])

    def test_missing_peer_empty_and_noninteger_receipts_are_refused(self):
        good = self.complete()
        for values in ([], [good, good, good], [good, {}], [dict(good, authority=True)]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                intro.validate_completion(values)


class NativeControlWitnessTests(unittest.TestCase):
    def row(self):
        players = [dict(character=seat, state=1, hp=32, action=2, x_raw=100*65536) for seat in (0, 1)]
        return dict(peers=[dict(peer=0, observation=dict(players=players))])

    def test_controlled_native_walk_and_genuine_other_actor_damage_are_separate(self):
        before = self.row(); after = copy.deepcopy(before)
        after['peers'][0]['observation']['players'][0].update(action=3, x_raw=97*65536)
        self.assertTrue(intro.independent_walk(before, after, 0)[0]['other_stationary'])
        after['peers'][0]['observation']['players'][0]['action'] = 4
        self.assertTrue(intro.independent_walk(before, after, 0))
        other = after['peers'][0]['observation']['players'][1]
        other.update(x_raw=101*65536)
        self.assertIsNone(intro.independent_walk(before, after, 0))
        other.update(hp=30, action=17)
        witness = intro.independent_walk(before, after, 0)[0]
        self.assertFalse(witness['other_stationary']); self.assertTrue(witness['other_HP_drop'])
        after['peers'][0]['observation']['players'][0]['action'] = 17
        self.assertIsNone(intro.independent_walk(before, after, 0))

    def test_dead_nonparticipant_cannot_supply_restored_controls(self):
        before = self.row(); after = copy.deepcopy(before)
        after['peers'][0]['observation']['players'][1].update(action=4, x_raw=97*65536)
        after['peers'][0]['observation']['players'][0]['hp'] = 0
        self.assertIsNone(intro.independent_walk(before, after, 1))


class NativeTransportBoundaryTests(unittest.TestCase):
    def test_zero_HP_passenger_requires_actual_transport_phase_and_alive_lifecycle(self):
        value = dict(scene_owner=1, scene_phase=2, lifecycle=[0, 0], players=[dict(hp=32), dict(hp=0)])
        self.assertTrue(intro.native_admission_health(value, 0))
        for change in (dict(scene_owner=0), dict(scene_owner=2), dict(scene_phase=0),
                       dict(scene_phase=1), dict(scene_phase=4), dict(scene_phase=5),
                       dict(lifecycle=[0, 3]), dict(lifecycle=[0, 4]), dict(lifecycle=[0, 5])):
            with self.subTest(change=change):
                self.assertFalse(intro.native_admission_health(dict(value, **change), 0))
        value['players'][0]['hp'] = 0
        self.assertFalse(intro.native_admission_health(value, 0))

    def test_CP2_metadata_with_old_CP0_bodies_does_not_establish_arrival(self):
        def peers(xs):
            return [dict(checkpoint=2, observation=dict(players=[dict(x_raw=x*65536) for x in xs]))]
        self.assertFalse(intro.authored_checkpoint_arrivals(peers((144, 168))))
        self.assertTrue(intro.authored_checkpoint_arrivals(peers((5904, 5928))))
        self.assertFalse(intro.authored_checkpoint_arrivals([]))


if __name__ == '__main__':
    unittest.main()
