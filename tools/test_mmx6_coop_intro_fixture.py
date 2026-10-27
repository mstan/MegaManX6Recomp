"""Reject unilateral/partial fixture receipts before named mechanic admission."""
import copy
import unittest

import mmx6_coop_intro_fixture as intro


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


if __name__ == '__main__':
    unittest.main()
