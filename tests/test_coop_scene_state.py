"""Scene proof must observe nonzero ownership and its current wire context."""
from pathlib import Path
import copy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import mmx6_coop_scene_state as subject
from test_coop_private_state_protocol import image


class SceneStateTests(unittest.TestCase):
    def test_scene_restore_never_ignores_ownership_resources_or_passenger_corruption(self):
        saved = subject.state.parse_state_image(image())
        self.assertTrue(all(subject.provider_checks(saved, saved, 1).values()))
        changed = copy.deepcopy(saved)
        core = bytearray.fromhex(changed['semantic_core_hex'])
        core[subject.state.HOST_PLAYER_BYTES+19] ^= 1
        changed['semantic_core_hex'] = core.hex()
        self.assertFalse(all(subject.provider_checks(saved, changed, 1, rewind=True).values()))
        for seat, key, offset in ((1, 'p1_body_hex', 0x34), (0, 'private_body_hex', 0x34),
                                  (1, 'private_body_hex', 0x5C), (0, 'p1_body_hex', 0x93)):
            changed = copy.deepcopy(saved); body = bytearray.fromhex(changed[key]); body[offset] ^= 1
            changed[key] = body.hex()
            self.assertFalse(all(subject.provider_checks(saved, changed, seat, rewind=True).values()))
        changed = dict(saved, banks_sha256='later animation cache', bank_count=saved['bank_count']+1)
        self.assertFalse(all(subject.provider_checks(saved, changed, 1).values()))
        self.assertTrue(all(subject.provider_checks(saved, changed, 1, rewind=True).values()))

    def test_complete_scene_context_includes_both_retained_actor_bodies(self):
        core = bytearray(subject.state.HOST_SEMANTIC_BYTES)
        at = subject.state.HOST_PLAYER_BYTES+19
        core[at:at+2] = b'\x02\x03'
        core[at+6] = 0x42
        core[at+6+0x158] = 0x81
        image = dict(internal_wire_schema=3, semantic_core_hex=core.hex())
        scene = subject.scene_wire(image)
        self.assertEqual((scene['owner'], scene['phase']), (2, 3))
        self.assertEqual(len(bytes.fromhex(scene['context_hex'])), 6+2*0x158)
        for offset in (at+2, at+6, at+6+0x158, at+6+2*0x158-1):
            other = bytearray(core); other[offset] ^= 1
            self.assertNotEqual(scene, subject.scene_wire(dict(image, semantic_core_hex=other.hex())))

    def test_unknown_or_invalid_scene_wire_cannot_establish_restore(self):
        core = bytearray(subject.state.HOST_SEMANTIC_BYTES)
        image = dict(internal_wire_schema=3, semantic_core_hex=core.hex())
        for changes in (dict(internal_wire_schema=4), dict(semantic_core_hex=core[:-1].hex())):
            with self.assertRaises(subject.mapped.debug.DebugError):
                subject.scene_wire(dict(image, **changes))
        at = subject.state.HOST_PLAYER_BYTES+19
        for owner, phase in ((3, 3), (1, 6), (0, 3)):
            core[at:at+2] = bytes((owner, phase))
            with self.assertRaises(subject.mapped.debug.DebugError):
                subject.scene_wire(dict(image, semantic_core_hex=core.hex()))

    def test_named_owner_requires_that_actors_actual_native_script_lock(self):
        lock = bytearray(0x158); lock[0xD0] = lock[0x7A] = 1
        neutral = bytes(0x158).hex()
        obs = dict(scene_owner=2, scene_phase=3, native_mode=10, native_phase=0)
        row = dict(observation=obs, p1_body_hex=neutral, p2_body_hex=lock.hex())
        self.assertTrue(subject.locked(row, 1))
        lock[0xD0] = 0xFF  # Original native script advances its lock sentinel.
        self.assertTrue(subject.locked(dict(row, p2_body_hex=lock.hex()), 1))
        self.assertFalse(subject.locked(row, 0))
        self.assertFalse(subject.locked(dict(row, p2_body_hex=neutral, p1_body_hex=lock.hex()), 1))
        for changes in (dict(scene_owner=0), dict(scene_phase=2), dict(native_phase=2)):
            self.assertFalse(subject.locked(dict(row, observation=dict(obs, **changes)), 1))


if __name__ == '__main__':
    unittest.main()
