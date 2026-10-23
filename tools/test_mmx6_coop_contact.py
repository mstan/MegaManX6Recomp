"""Read-only R2 evidence negatives; no native runtime result or original assets."""
import copy
import struct
import unittest
import mmx6_coop_contact as subject
from test_coop_debug_protocol import diagnostic

from mmx6_coop_contact import (
    CONTACT, CONTACT_RA, ZERO_BASE, ZERO_SIZE, complete_contact_trace,
    contact_evidence, ordinary_damage, player_fields, validate_zero_overlay, zero_box,
)


def before():
    fields = dict(hp_raw=32, hp=32, pending_hit=False, iframes=0, reaction=0,
                  reaction_lock=0, hit_pause=0, alternate_projection=False,
                  native_restriction=0, body_restriction=0, terrain=8, previous_terrain=8,
                  state=1, action=2)
    return dict(players=[copy.deepcopy(fields), copy.deepcopy(fields)],
        observation=dict(tick=100, native_timer=50, players=[
            dict(hp=32, weapon=0, ammo=[288] * 9), dict(hp=32, weapon=0, ammo=[288] * 9)]),
        instance=dict(address="0x8008ef48", origin="0x800fa2dc", flags=0x41,
                      type=1, subtype=1, hp=12, phase=1), p2_contact_counter=0,
        expected_damage=4, expected_reaction=1, damage_configuration=[1, 0, 0, 0],
        p2_box=dict(pointer="0x801eea04", x=-7, y=-30, width=14, height=30))


def hit(old):
    result = copy.deepcopy(old)
    result["observation"].update(tick=102, native_timer=52)
    result["observation"]["players"][1]["hp"] = 28
    result["players"][1].update(hp_raw=28, hp=28, iframes=75, reaction=1, reaction_lock=1, action=17)
    result["p2_contact_counter"] = 1
    return result


class ContactObservationTests(unittest.TestCase):
    def client(self,phase=0,hp=0,strength=0,pointer=0,box=bytes.fromhex('f4ec1828')):
        data=bytearray(diagnostic());data[0x100+0xE7]=5
        pool=bytearray(subject.enemy.STRIDE*subject.enemy.SLOTS)
        pool[:3]=bytes((0x41,1,1));pool[4]=phase;pool[0x5C]=hp;pool[0x60]=strength
        struct.pack_into('<I',pool,0x10,subject.enemy.RECORD);struct.pack_into('<I',pool,0x50,pointer)
        config=bytes(9)+b'\1'
        values={subject.debug.DIAGNOSTIC_ADDRESS:bytes(data),subject.enemy.POOL:bytes(pool),
            0x800CCF2F:config,subject.enemy.RECORD:bytes(8),0x80097202:bytes(6),0x800FAAE0:box}
        class Client:
            def read(self,address,count):
                result=values[address]
                if len(result)!=count:raise AssertionError('Unexpected observation span')
                return result
        return Client()

    def test_zeroed_phase0_is_retained_pending_not_contact_evidence(self):
        row=subject.observe_contact(self.client(),b'')
        self.assertIsNone(row['instance']);self.assertEqual(row['pending_initialization']['phase'],0)
        self.assertEqual(len(row['live_enemies']),1)

    def test_initialized_authored_descriptor_remains_required(self):
        row=subject.observe_contact(self.client(1,12,4,0x800FAAE0),b'')
        self.assertIsNone(row['pending_initialization']);self.assertEqual(row['instance']['contact_box'],'f4ec1828')
        for args in ((1,12,4,0),(0,12,0,0),(1,12,4,0x800FAAE4)):
            with self.subTest(args=args),self.assertRaises(subject.debug.DebugError):
                subject.observe_contact(self.client(*args),b'')
        with self.assertRaises(subject.debug.DebugError):
            subject.observe_contact(self.client(1,12,4,0x800FAAE0,b'\0'*4),b'')


class NativeFieldTests(unittest.TestCase):
    def test_hp_high_bit_is_pending_reaction_not_extra_health(self):
        body = bytearray(0x158)
        body[0x5C] = 0x9C
        body[0x61], body[0x63], body[0xA4], body[0xA5] = 75, 1, 1, 0x40
        struct.pack_into("<I", body, 0x54, 0x801EEA04)
        parsed = player_fields(body)
        self.assertEqual((parsed["hp_raw"], parsed["hp"], parsed["pending_hit"]), (0x9C, 28, True))
        self.assertEqual((parsed["iframes"], parsed["reaction"], parsed["reaction_lock"]), (75, 1, 1))
        self.assertEqual(parsed["box_pointer"], 0x801EEA04)
        with self.assertRaisesRegex(ValueError, "Truncated"):
            player_fields(body[:-1])

    def test_original_strength4_difficulty_and_half_damage_paths(self):
        self.assertEqual([ordinary_damage(d, 0, 0, 0) for d in (0, 1, 2)], [(3, 1), (4, 1), (5, 1)])
        for armor, parts, shared in ((1, 0, 0), (5, 0, 0x20), (5, 0x200, 0)):
            self.assertEqual(ordinary_damage(1, armor, parts, shared), (2, 4))
        self.assertEqual(ordinary_damage(1, 0, 0x200, 0), (2, 1))
        self.assertEqual(ordinary_damage(1, 0, 0, 0x20), (4, 4))
        with self.assertRaises(ValueError):
            ordinary_damage(3, 0, 0, 0)

    def test_zero_box_uses_explicit_immutable_payload_and_rejects_bad_pointer(self):
        payload = bytearray(ZERO_SIZE)
        offset = 0x801EEA04 - ZERO_BASE
        payload[offset:offset + 4] = bytes.fromhex("f9e20e1e")
        self.assertEqual(zero_box(0x801EEA04, payload)["x"], -7)
        self.assertEqual(zero_box(0x801EEA04, payload)["source"], "immutable_original_zero_overlay")
        self.assertIsNone(zero_box(0, payload))
        for pointer in (ZERO_BASE - 4, ZERO_BASE + ZERO_SIZE, 0x801EEA05, 0x800FAAE0):
            with self.assertRaises(ValueError):
                zero_box(pointer, payload)
        # The real case validates the whole member before resolving any box.
        # A synthetic descriptor cannot substitute for original-source identity.
        with self.assertRaisesRegex(ValueError, "pinned original"):
            validate_zero_overlay(payload)


class ContactReducerTests(unittest.TestCase):
    def setUp(self):
        self.before = before()
        self.hit = hit(self.before)

    def test_native_hp_reaction_and_successful_retry_must_agree(self):
        self.assertIs(contact_evidence(self.before, [self.hit]), self.hit)
        for change in ("no_counter", "two_contacts", "no_hp_drop", "no_hurt", "no_iframes", "no_lock", "pending"):
            row = copy.deepcopy(self.hit)
            if change == "no_counter": row["p2_contact_counter"] = 0
            elif change == "two_contacts": row["p2_contact_counter"] = 2
            elif change == "no_hp_drop": row["players"][1]["hp"] = 32
            elif change == "no_hurt": row["players"][1]["action"] = 2
            elif change == "no_iframes": row["players"][1]["iframes"] = 0
            elif change == "no_lock": row["players"][1]["reaction_lock"] = 0
            else: row["players"][1]["pending_hit"] = True
            self.assertIsNone(contact_evidence(self.before, [row]), change)

    def test_dead_stale_wrong_origin_or_outgoing_enemy_damage_cannot_pass(self):
        for field, value in (("flags", 0), ("type", 2), ("subtype", 2), ("address", "0x8008efe4"),
                             ("origin", "0x800fa2e4"), ("hp", 0), ("phase", 2)):
            row = copy.deepcopy(self.hit)
            row["instance"][field] = value
            self.assertIsNone(contact_evidence(self.before, [row]), field)
        row = copy.deepcopy(self.hit)
        row["observation"]["tick"] = self.before["observation"]["tick"]
        self.assertIsNone(contact_evidence(self.before, [row]))

    def test_invulnerable_start_changed_damage_context_terrain_or_x_resource_loss_rejects(self):
        for field, value in (("iframes", 1), ("reaction_lock", 1), ("hit_pause", 1), ("pending_hit", True)):
            old = copy.deepcopy(self.before)
            old["players"][1][field] = value
            self.assertIsNone(contact_evidence(old, [self.hit]), field)
        row = copy.deepcopy(self.hit)
        row["damage_configuration"][0] = 2
        self.assertIsNone(contact_evidence(self.before, [row]))
        row = copy.deepcopy(self.hit)
        row["players"][1]["terrain"] = 0x0C
        self.assertIsNone(contact_evidence(self.before, [row]))
        for field in ("hp", "weapon", "ammo"):
            row = copy.deepcopy(self.hit)
            if field == "ammo": row["observation"]["players"][0][field][0] -= 1
            else: row["observation"]["players"][0][field] -= 1
            self.assertIsNone(contact_evidence(self.before, [row]), field)

    def test_retained_hurt_sample_is_kept_when_later_endpoint_has_recovered(self):
        recovered = copy.deepcopy(self.hit)
        recovered["players"][1].update(action=2, iframes=0, reaction_lock=0)
        recovered["observation"]["tick"] = 200
        self.assertIs(contact_evidence(self.before, [self.hit, recovered]), self.hit)
        self.assertIsNone(contact_evidence(self.before, [recovered]))


class TraceAttributionTests(unittest.TestCase):
    def page(self):
        rows = [dict(seq=i, target=hex(CONTACT), a0="0x8008ef48", ra=hex(CONTACT_RA)) for i in range(3)]
        return dict(seq_lo=0, seq_hi=3, emitted=3, entries=rows)

    def test_multiple_wrapper_original_entries_are_not_three_accepted_hits(self):
        self.assertEqual(len(complete_contact_trace(self.page(), "0x8008ef48")), 3)

    def test_truncated_evicted_empty_or_foreign_actor_window_is_rejected(self):
        for field, value in (("seq_lo", 1), ("seq_hi", 0), ("seq_hi", 4097), ("emitted", 2)):
            page = self.page()
            page[field] = value
            with self.assertRaisesRegex(Exception, "trace window"):
                complete_contact_trace(page, "0x8008ef48")
        for field, value in (("seq", 4), ("a0", "0x80093c98"), ("ra", "0x800eaf98"), ("target", "0x80031474")):
            page = self.page()
            page["entries"][1][field] = value
            with self.assertRaises(Exception):
                complete_contact_trace(page, "0x8008ef48")


if __name__ == "__main__":
    unittest.main()
