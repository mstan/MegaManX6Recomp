"""Pure parser/protocol checks. No game process or network server is needed."""
from dataclasses import replace
import json
import socket
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch

from coop_debug import (DIAGNOSTIC_ADDRESS, DIAGNOSTIC_BYTES, DebugClient,
                        DebugError, UnstableObservation, observe, parse_diagnostic)
from test_mmx6_coop_netplay import (FailedSetup, ValidationFailure, main,
                                   native_ready, pair_match, require_framework_digest,
                                   validate_status)
from coop_state_crc import (MissingStateCrc, StateCrcError, parse_state_crc,
                            resolved_state_crc)


def diagnostic(*, tick=10, sequence=20, digest=0x12345678):
    data = bytearray(DIAGNOSTIC_BYTES)
    struct.pack_into("<II", data, 0, 0x434F4F50, tick)
    struct.pack_into("<III", data, 0x80, 1, DIAGNOSTIC_BYTES, sequence)
    data[0x8C:0x8F] = bytes((1, 1, 0))
    data[0x90:0x92] = bytes((10, 0))
    struct.pack_into("<II", data, 0x94, digest, 1)
    for base, character in ((0x100, 1), (0x1800, 0)):
        data[base] = 1
        data[base+2] = character
        data[base+4:base+6] = bytes((1, 2))
        data[base+0x5C] = 16
        struct.pack_into("<ii", data, base+8, (100+character*40) << 16, 200 << 16)
    data[8:16] = data[0x108:0x110]
    data[24] = data[0x15C]
    return bytes(data)


class DiagnosticTests(unittest.TestCase):
    def test_owned_weapon_and_ammo_are_part_of_the_same_publication(self):
        data = bytearray(diagnostic())
        data[0x100+0x93] = 7
        struct.pack_into("<9H", data, 0x100+0xA8, *range(9))
        row = parse_diagnostic(bytes(data))
        self.assertEqual(row.players[1].weapon, 7)
        self.assertEqual(row.players[1].ammo, tuple(range(9)))

    def test_pause_owner_uses_one_based_wire_seats(self):
        for owner in (0, 1, 2):
            data = bytearray(diagnostic())
            data[0x3C] = owner
            self.assertEqual(parse_diagnostic(bytes(data)).pause_owner, owner)

    def test_unregistered_framework_digest_cannot_qualify_crc_mode(self):
        unregistered = parse_diagnostic(diagnostic(digest=0))
        with self.assertRaises(FailedSetup):
            require_framework_digest([unregistered, unregistered])
        data = bytearray(diagnostic(digest=0))
        data[0x9C] = 1
        registered = parse_diagnostic(bytes(data))
        require_framework_digest([registered, registered])
        with self.assertRaises(FailedSetup):
            require_framework_digest([registered, unregistered])

    def test_versioned_fields_and_canonical_player_order(self):
        row = parse_diagnostic(diagnostic(digest=0))
        self.assertEqual((row.tick, row.sequence, row.host_digest), (10, 20, 0))
        self.assertEqual([body.character for body in row.players], [0, 1])
        self.assertTrue(native_ready(row))
        self.assertEqual(row.json()["players"][1]["x_raw"], 140 << 16)

    def test_invalid_magic_length_and_schema_rejected(self):
        for offset, value in ((0, 0), (0x80, 2), (0x84, 4), (0x98, 2)):
            data = bytearray(diagnostic())
            struct.pack_into("<I", data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(DebugError):
                parse_diagnostic(bytes(data))
        with self.assertRaises(DebugError):
            parse_diagnostic(diagnostic()[:-1])

    def test_odd_sequence_and_mixed_player_mirror_rejected(self):
        with self.assertRaises(UnstableObservation):
            parse_diagnostic(diagnostic(sequence=21))
        data = bytearray(diagnostic())
        data[8] ^= 1
        with self.assertRaises(UnstableObservation):
            parse_diagnostic(bytes(data))
        with self.assertRaises(UnstableObservation):
            parse_diagnostic(diagnostic(tick=11, sequence=20))

    def test_invalid_ownership_and_boolean_rejected(self):
        for offset, value in ((0x38, 6), (0x3C, 3), (0x3E, 3), (0x8E, 2)):
            data = bytearray(diagnostic())
            data[offset] = value
            with self.subTest(offset=offset), self.assertRaises(DebugError):
                parse_diagnostic(bytes(data))

    def test_legacy_requires_explicit_opt_in(self):
        data = bytearray(diagnostic())
        data[0x80:0x9C] = bytes(0x1C)
        with self.assertRaises(DebugError):
            parse_diagnostic(bytes(data))
        row = parse_diagnostic(bytes(data), allow_legacy=True)
        self.assertIsNone(row.sequence)
        self.assertIsNone(row.host_digest)
        self.assertFalse(native_ready(row))

    def test_snapshot_retries_unfinished_publication(self):
        client = Mock()
        client.read.side_effect = [diagnostic(sequence=19), diagnostic()]
        row = observe(client, attempts=2)
        self.assertEqual(row.sequence, 20)
        self.assertEqual(client.read.call_count, 2)
        client.read.assert_any_call(DIAGNOSTIC_ADDRESS, DIAGNOSTIC_BYTES)

    def test_never_stable_is_bounded(self):
        client = Mock()
        client.read.side_effect = [diagnostic(sequence=19)] * 3
        with self.assertRaises(UnstableObservation):
            observe(client, attempts=3)
        self.assertEqual(client.read.call_count, 3)

    def test_pair_same_tick_and_digest_is_partial_evidence(self):
        row = parse_diagnostic(diagnostic())
        self.assertIn("not a framework simulation tick", pair_match(row, row)["evidence"])
        for bad in (replace(row, tick=11), replace(row, host_digest=42),
                    replace(row, players=(row.players[1], row.players[0]))):
            with self.assertRaises(ValidationFailure):
                pair_match(row, bad)

    def test_network_status_requires_correct_session(self):
        host = dict(active=1, rollback=0, players=2, desync=0, host=1)
        guest = dict(host, host=0)
        validate_status([host, guest])
        with self.assertRaises(FailedSetup):
            validate_status([guest, host])
        with self.assertRaises(FailedSetup):
            validate_status([host, dict(guest, rollback=1)])
        with self.assertRaises(ValidationFailure):
            validate_status([host, dict(guest, desync=1)])


class ProtocolTests(unittest.TestCase):
    def connection(self, chunks):
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.recv.side_effect = chunks
        return connection

    def test_fragmented_json_and_request_id(self):
        connection = self.connection([b'{"id":1,', b'"ok":true}\n'])
        with patch("coop_debug.socket.create_connection", return_value=connection):
            self.assertTrue(DebugClient(12345).request("frame")["ok"])
        payload = json.loads(connection.sendall.call_args.args[0])
        self.assertEqual(payload, dict(id=1, cmd="frame"))

    def test_malformed_oversized_closed_or_rejected_response(self):
        for chunks in ([b""], [b"{" + b"x"*64], [b"no json\n"],
                       [b'{"id":2,"ok":true}\n'], [b'{"id":1,"ok":false}\n'],
                       [b'{"id":1,"ok":true}\nextra'], [b'[]\n']):
            with self.subTest(chunks=chunks):
                connection = self.connection(chunks)
                with patch("coop_debug.socket.create_connection", return_value=connection):
                    with self.assertRaises(DebugError):
                        DebugClient(12345, max_response_bytes=64).request("frame")

    def test_timeout_and_total_deadline(self):
        connection = self.connection([socket.timeout("late")])
        with patch("coop_debug.socket.create_connection", return_value=connection):
            with self.assertRaises(DebugError):
                DebugClient(12345).request("frame")
        connection = self.connection([b"{"])
        with patch("coop_debug.socket.create_connection", return_value=connection), \
                patch("coop_debug.time.monotonic", side_effect=[0, .1, .2, 4]):
            with self.assertRaises(DebugError):
                DebugClient(12345, timeout=3).request("frame")
        self.assertEqual(connection.recv.call_count, 1)

    def test_read_requires_exact_hex_bytes(self):
        client = DebugClient(12345)
        for payload in ("000", "zzzz", "00  ", None):
            with self.subTest(payload=payload), patch.object(client, "request", return_value={"hex": payload}):
                with self.assertRaises(DebugError):
                    client.read(0x80000000, 2)

    def test_host_input_is_acknowledged_and_never_simulation_override(self):
        client = DebugClient(12345)
        with patch.object(client, "request", side_effect=[{}, dict(host_layer=True, host_buttons="0xFFDF")]) as request:
            client.host_input(0x20)
            self.assertEqual(request.call_args_list[0].kwargs, dict(layer="host", buttons="0xffdf"))
        with patch.object(client, "request", side_effect=[{}, dict(override=0xFFDF)]):
            with self.assertRaises(DebugError):
                client.host_input(0x20)

    def test_bad_ports_sizes_and_reserved_fields(self):
        for port in (0, 65536, True):
            with self.assertRaises(ValueError):
                DebugClient(port)
        client = DebugClient(12345)
        with self.assertRaises(ValueError):
            client.request("frame", id=42)
        with self.assertRaises(ValueError):
            client.read(0xFFFFFFFF, 2)

    def test_failed_setup_report_survives_unavailable_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch("test_mmx6_coop_netplay.DebugClient") as client:
            client.return_value.request.side_effect = DebugError("Connection refused")
            result = main(["--host-port", "12345", "--guest-port", "12346", "--output", directory,
                           "--candidate", "unit-test synthetic process"])
            from pathlib import Path
            report = json.loads((Path(directory)/"result.json").read_text())
        self.assertEqual(result, 2)
        self.assertEqual(report["result"], "failed_setup")
        self.assertEqual(report["whole_machine_determinism"], "unverified")


class StateCrcTests(unittest.TestCase):
    @staticmethod
    def line(tick, core="12345678", mod="ABCDEF00"):
        return f"psxrecomp: rb live dig local sim={tick} core={core} cpu=00000001 mod={mod} av=00000002\n"

    def test_only_complete_mod_partition_lines_qualify(self):
        text = "rb live dig local sim=32 core=12345678 ram=87654321\n"
        self.assertEqual(parse_state_crc(text+self.line(64).rstrip()), {})
        self.assertEqual(parse_state_crc(self.line(64))[64].mod, "abcdef00")

    def test_conflicting_repeated_tick_is_rejected(self):
        self.assertEqual(len(parse_state_crc(self.line(32)*2)), 1)
        with self.assertRaises(StateCrcError):
            parse_state_crc(self.line(32)+self.line(32, mod="00000000"))

    def test_only_common_simulation_ticks_below_watermark_qualify(self):
        host = parse_state_crc("".join(self.line(tick) for tick in (0, 32, 64, 96)))
        guest = parse_state_crc("".join(self.line(tick) for tick in (32, 64, 96, 128)))
        samples = resolved_state_crc(host, guest, 96, after=0)
        self.assertEqual([row["simulation_tick"] for row in samples], [32, 64])
        with self.assertRaises(MissingStateCrc):
            resolved_state_crc(host, guest, 64, after=0)

    def test_mod_divergence_fails_with_identical_core(self):
        host = parse_state_crc(self.line(32)+self.line(64))
        guest = parse_state_crc(self.line(32)+self.line(64, mod="00000000"))
        with self.assertRaises(StateCrcError):
            resolved_state_crc(host, guest, 96)


if __name__ == "__main__":
    unittest.main()
