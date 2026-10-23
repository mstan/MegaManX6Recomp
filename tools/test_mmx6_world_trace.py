import unittest
from copy import deepcopy

from coop_debug import DebugError
from qualify_mmx6_world_trace import WORLD, DRIVER, RETURN, HANDLER, ALIVE, analyze, complete_page


class TraceAccountingTests(unittest.TestCase):
    def fixture(self):
        trace, direct, dirty = [], [], []
        for frame in range(41):
            for target in (0x8001E9EC, 0x8001E9EC, DRIVER, 0x8002012C, 0x8002012C,
                           WORLD, 0x8002003C, HANDLER, RETURN):
                trace.append(dict(seq=len(trace), frame=frame, target=hex(target), a0="0x8008ef48"))
            direct.append(dict(frame=frame, func=hex(WORLD)))
            dirty.append(dict(frame=frame, target=hex(ALIVE), a0="0x8008ef48"))
        return trace, direct, dirty

    def test_continuations_and_two_attack_pools_are_separate_from_world(self):
        result = analyze(*self.fixture(), [5, 35])
        self.assertTrue(all(result["checks"].values()))
        self.assertTrue(all(c["world"] == 1 and c["attack_pool"] == 2 and c["stage_wrapper"] == 2
                            for c in result["cycles"]))

    def test_duplicate_true_world_or_missing_direct_coverage_cannot_pass(self):
        trace, direct, dirty = self.fixture()
        trace[9 * 20 + 6]["target"] = hex(WORLD)
        result = analyze(trace, direct, dirty, [5, 35])
        self.assertFalse(result["checks"]["one_world_dispatch_and_prologue_per_interior_frame"])
        self.assertFalse(result["checks"]["one_world_per_complete_native_driver_cycle"])
        trace, direct, dirty = self.fixture()
        direct.pop(20)
        self.assertFalse(analyze(trace, direct, dirty, [5, 35])["checks"]["one_world_dispatch_and_prologue_per_interior_frame"])

    def test_missing_or_wrong_origin_alive_body_cannot_pass(self):
        trace, direct, dirty = self.fixture()
        dirty[20]["a0"] = "0x8008efe4"
        self.assertFalse(analyze(trace, direct, dirty, [5, 35])["checks"]["one_origin_bound_alive_body_per_interior_frame"])

    def test_page_rejects_eviction_sequence_gaps_and_truncation(self):
        page = dict(seq_lo=2, seq_hi=4, emitted=2,
                    entries=[dict(seq=2, target=hex(WORLD)), dict(seq=3, target=hex(RETURN))])
        self.assertEqual(complete_page(page, 2)[1], 4)
        for field, value in (("seq_lo", 3), ("seq_hi", 5), ("emitted", 1)):
            invalid = deepcopy(page); invalid[field] = value
            with self.assertRaises(DebugError):
                complete_page(invalid, 2)


if __name__ == "__main__":
    unittest.main()
