"""Evidence-reducer negatives only; these tests do not qualify a running game."""
import copy
import unittest

from mmx6_coop_personal_menu import (
    native_square_evidence, personal_menu_smoke, reduce_frozen_window,
    resources_preserved,
)


def peer(tick=100, *, timer=50, phase=2, owner=2, menu=(1, 0), cursor=0):
    return dict(observation=dict(tick=tick, native_timer=timer, native_mode=10,
        native_phase=phase, pause_owner=owner, lifecycle=[0, 0], players=[
            dict(active=1, character=0, state=1, action=2, hp=32,
                 x_raw=144 << 16, weapon=0, ammo=[288] * 9),
            dict(active=1, character=1, state=1, action=2, hp=32,
                 x_raw=181 << 16, weapon=0, ammo=[288] * 9)]), menu=list(menu), cursor=cursor)


def samples(*, online=False):
    result = []
    for offset in (0, 6, 12):
        row = dict(peers=[peer(100 + offset) for _ in range(2 if online else 1)])
        if online:
            row["network"] = [dict(active=1, players=2, max_players=2, rollback=0,
                desync=0, tick=1000 + offset, resolved_through=998 + offset) for _ in range(2)]
        result.append(row)
    return result


class FrozenMenuTests(unittest.TestCase):
    def test_both_observed_native_substates_are_allowed_without_inventing_state1_1(self):
        for substate in (0, 1):
            history = samples()
            for row in history:
                row["peers"][0]["menu"][1] = substate
            self.assertTrue(all(reduce_frozen_window(history, 1, expected_cursors=[0]).values()))
        history[1]["peers"][0]["menu"][0] = 0
        self.assertFalse(reduce_frozen_window(history, 1)["native_menu_input_state"])

    def test_transient_wrong_owner_or_resume_is_rejected_even_if_endpoints_match(self):
        for field, value in (("pause_owner", 1), ("native_phase", 0)):
            history = samples()
            history[1]["peers"][0]["observation"][field] = value
            self.assertFalse(reduce_frozen_window(history, 1)["native_pause_owned"])

    def test_transient_clock_change_and_advance_between_input_windows_are_rejected(self):
        history = samples()
        history[1]["peers"][0]["observation"]["native_timer"] += 1
        self.assertFalse(reduce_frozen_window(history, 1)["world_timer_frozen"])
        # A later window can look internally frozen after the wrong input
        # advanced time. It must still match the original menu-entry timer.
        history = samples()
        self.assertFalse(reduce_frozen_window(history, 1, reference_timers=[49])["world_timer_frozen"])

    def test_frozen_engine_is_not_native_world_pause_evidence(self):
        history = samples()
        for row in history:
            row["peers"][0]["observation"]["tick"] = 100
        self.assertTrue(reduce_frozen_window(history, 1)["world_timer_frozen"])
        self.assertFalse(reduce_frozen_window(history, 1)["diagnostic_publications_advanced"])
        self.assertFalse(reduce_frozen_window(history[:2], 1)["enough_samples"])

    def test_other_seat_cursor_leak_is_rejected(self):
        history = samples()
        history[1]["peers"][0]["cursor"] = 10
        self.assertFalse(reduce_frozen_window(history, 1, expected_cursors=[0])["cursor_unchanged"])

    def test_actual_network_tick_and_resolution_progress_are_both_required(self):
        history = samples(online=True)
        self.assertTrue(all(reduce_frozen_window(history, 1, networked=True).values()))
        for row in history:
            row["network"][1]["resolved_through"] = 998
        reduced = reduce_frozen_window(history, 1, networked=True)
        self.assertTrue(reduced["transport_ticks_advanced"])
        self.assertFalse(reduced["resolved_ticks_advanced"])
        for row in history:
            row["network"][0]["tick"] = 1000
        self.assertFalse(reduce_frozen_window(history, 1, networked=True)["transport_ticks_advanced"])

    def test_transient_desync_or_inactive_network_cannot_be_hidden_by_final_status(self):
        for field, value in (("desync", 1), ("active", 0), ("players", 1), ("rollback", 1)):
            history = samples(online=True)
            history[1]["network"][0][field] = value
            self.assertFalse(reduce_frozen_window(history, 1, networked=True)["network_active_without_desync"])

    def test_personal_resources_compare_both_seats_including_weapon_and_ammo(self):
        before = [peer()]
        self.assertTrue(resources_preserved(before, copy.deepcopy(before)))
        for seat in (0, 1):
            for field in ("hp", "weapon", "ammo"):
                after = copy.deepcopy(before)
                if field == "ammo":
                    after[0]["observation"]["players"][seat][field][0] -= 1
                else:
                    after[0]["observation"]["players"][seat][field] -= 1
                self.assertFalse(resources_preserved(before, after))

    def test_publication_wrap_is_forward_but_backward_history_is_rejected(self):
        history = samples()
        for row, tick in zip(history, (0xFFFFFFFC, 2, 8)):
            row["peers"][0]["observation"]["tick"] = tick
        self.assertTrue(reduce_frozen_window(history, 1)["diagnostic_publications_advanced"])
        history[-1]["peers"][0]["observation"]["tick"] = 0xFFFFFFFB
        self.assertFalse(reduce_frozen_window(history, 1)["diagnostic_publications_advanced"])


class NativeAttackTests(unittest.TestCase):
    def setUp(self):
        self.before = peer(100, phase=0, owner=0)
        self.attack = peer(102, phase=0, owner=0)
        self.attack["observation"]["players"][1]["action"] = 48

    def test_retained_transient_native_action_counts_after_it_returns_to_idle(self):
        idle = peer(105, phase=0, owner=0)
        self.assertIs(native_square_evidence(self.before, [self.attack, idle]), self.attack)
        self.assertIsNone(native_square_evidence(self.before, [idle]))

    def test_acknowledgment_stale_sample_and_preexisting_attack_are_not_new_square_effects(self):
        self.assertIsNone(native_square_evidence(self.before, []))
        stale = copy.deepcopy(self.attack)
        stale["observation"]["tick"] = 100
        self.assertIsNone(native_square_evidence(self.before, [stale]))
        old_attack = copy.deepcopy(self.before)
        old_attack["observation"]["players"][1]["action"] = 48
        self.assertIsNone(native_square_evidence(old_attack, [self.attack]))

    def test_wrong_character_phase_or_other_seat_movement_rejects_attack_evidence(self):
        for mutation in ("character", "phase", "other_moved", "dead"):
            row = copy.deepcopy(self.attack)
            if mutation == "character":
                row["observation"]["players"][1]["character"] = 0
            elif mutation == "phase":
                row["observation"]["native_phase"] = 2
            elif mutation == "other_moved":
                row["observation"]["players"][0]["x_raw"] += 1
            else:
                row["observation"]["players"][1]["hp"] = 0
            self.assertIsNone(native_square_evidence(self.before, [row]))
        with self.assertRaisesRegex(ValueError, "Zero only"):
            native_square_evidence(self.before, [self.attack], 0)


class CallbackContractTests(unittest.TestCase):
    def context(self):
        return dict(mode="netplay", input_path="published_host", clients=[None, None],
                    both=None, debug=None, report={}, output="G:/Temp/Codex/psxrecomp/x6-parity/menu-unit-unused",
                    hold=None, native_advance=None, transport_window=None, network=lambda: [])

    def test_online_sio_or_mailbox_adapter_is_rejected_before_any_control_or_file_io(self):
        for path in ("offline_native", "direct_sio", "mailbox"):
            ctx = self.context()
            ctx["input_path"] = path
            with self.assertRaisesRegex(ValueError, "published host"):
                personal_menu_smoke(ctx)
            self.assertEqual(ctx["report"], {})

    def test_online_status_and_explicit_p1_attack_contract_are_required(self):
        ctx = self.context()
        del ctx["network"]
        with self.assertRaisesRegex(ValueError, "transport status"):
            personal_menu_smoke(ctx)
        ctx = self.context()
        with self.assertRaisesRegex(ValueError, "source-backed"):
            personal_menu_smoke(ctx, owner=0)
        self.assertEqual(ctx["report"], {})

    def test_expected_hp_rejects_dead_pending_hit_and_invalid_values_before_controls(self):
        for values in ((32, 0), (0, 28), (32, -1), (32, 0x9C), (32, 128),
                       (32, True), (32, 28.0), (32,), "32,28", None):
            ctx = self.context()
            with self.assertRaisesRegex(ValueError, "two living positive"):
                personal_menu_smoke(ctx, expected_hp=values)
            self.assertEqual(ctx["report"], {})

    def test_reduced_living_hp_is_allowed_without_enabling_any_other_bypass(self):
        for values in ((32, 28), (32, 1), (32, 32)):
            ctx = self.context()
            ctx["input_path"] = "mailbox"
            with self.assertRaisesRegex(ValueError, "published host"):
                personal_menu_smoke(ctx, expected_hp=values)
            self.assertEqual(ctx["report"], {})
        before = [peer()]
        before[0]["observation"]["players"][1]["hp"] = 28
        after = copy.deepcopy(before)
        self.assertTrue(resources_preserved(before, after))
        after[0]["observation"]["players"][1]["hp"] = 32
        self.assertFalse(resources_preserved(before, after))


if __name__ == "__main__":
    unittest.main()
