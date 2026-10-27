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


if __name__ == '__main__':
    unittest.main()
