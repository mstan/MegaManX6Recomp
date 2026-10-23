import struct
import unittest

import coop_debug as debug
import mmx6_coop_collision_boxes as boxes


def publication():
    raw = bytearray(boxes.END)
    struct.pack_into("<II", raw, 0, 0x434F4F50, 7)
    struct.pack_into("<III", raw, 0x80, 1, debug.DIAGNOSTIC_BYTES, 14)
    raw[0x8C:0x8F] = bytes((1, 1, 0))
    raw[0x90] = 10
    struct.pack_into("<I", raw, 0x98, 1)
    for at, character in ((0x1800, 0), (0x100, 1)):
        raw[at] = 1
        raw[at + 2:at + 6] = bytes((character, 1, 1, 2))
        raw[at + 0x5C] = 32
    raw[24] = 32
    struct.pack_into("<4I", raw, boxes.HEADER, boxes.MAGIC, 1, boxes.SIZE, 7)
    for i, ((_, offset), pointer, origin, value) in enumerate(zip(
            boxes.FIELDS, (boxes.OVERLAY + 4, 0x80073D54, 0), (2, 1, 0),
            (bytes((0, 3, 11, 19)), bytes((246, 239, 21, 39)), bytes(4)))):
        struct.pack_into("<I", raw, 0x100 + offset, pointer)
        struct.pack_into("<II4s", raw, boxes.HEADER + 16 + i * 12, pointer, origin, value)
    return raw


class CollisionBoxes(unittest.TestCase):
    def test_private_bytes_and_same_publication_body(self):
        result = boxes.parse_publication(bytes(publication()))
        self.assertEqual(result["boxes"]["attack"], dict(pointer=boxes.OVERLAY + 4,
            origin="private_overlay", available=True, hex="00030b13"))
        self.assertEqual(result["boxes"]["damage"]["origin"], "native_ram")
        self.assertIsNone(result["boxes"]["body"]["hex"])
        self.assertEqual(result["observation"]["tick"], 7)
        self.assertEqual(len(bytes.fromhex(result["p2_body_hex"])), 0x158)

    def test_one_exact_read_and_no_control(self):
        calls = []
        def request(command, **fields):
            calls.append((command, fields))
            return dict(ok=True, addr="0x9F080000", len=boxes.END, hex=publication().hex())
        boxes.observe_owned(request)
        self.assertEqual(calls, [("read_ram", dict(addr="0x9f080000", len=boxes.END))])

    def test_partial_old_or_extended_block_refused(self):
        for data in (bytes(publication())[:-1], bytes(publication()) + b"\0", bytes(boxes.HEADER)):
            with self.assertRaises(debug.DebugError): boxes.parse_publication(data)

    def test_unstable_base_box_tick_and_pointer_refused(self):
        for at, value in ((0x88, 15), (boxes.HEADER + 12, 6), (boxes.HEADER + 16, boxes.OVERLAY + 8)):
            raw = publication(); struct.pack_into("<I", raw, at, value)
            with self.assertRaises(debug.UnstableObservation): boxes.parse_publication(bytes(raw))

    def test_unknown_headers_origins_and_padding_refused(self):
        for at, value in ((boxes.HEADER, 0), (boxes.HEADER + 4, 2),
                          (boxes.HEADER + 8, 0x44), (boxes.HEADER + 20, 3), (boxes.END - 4, 1)):
            raw = publication(); struct.pack_into("<I", raw, at, value)
            with self.assertRaises(debug.DebugError): boxes.parse_publication(bytes(raw))

    def test_source_ranges_and_bank_readiness_refused(self):
        for pointer in (0, boxes.OVERLAY - 1, boxes.OVERLAY + boxes.OVERLAY_SIZE - 3, 0xFFFFFFFF):
            raw = publication()
            struct.pack_into("<I", raw, 0x150, pointer)
            struct.pack_into("<I", raw, boxes.HEADER + 16, pointer)
            with self.assertRaises(debug.DebugError): boxes.parse_publication(bytes(raw))
        raw = publication(); raw[0x8C] = 0
        with self.assertRaises(debug.DebugError): boxes.parse_publication(bytes(raw))

    def test_unavailable_clears_old_data_without_inventing_validity(self):
        raw = publication(); struct.pack_into("<I", raw, boxes.HEADER + 20, 0)
        with self.assertRaises(debug.DebugError): boxes.parse_publication(bytes(raw))
        raw[boxes.HEADER + 24:boxes.HEADER + 28] = bytes(4)
        result = boxes.parse_publication(bytes(raw))
        self.assertFalse(result["boxes"]["attack"]["available"])

    def test_bad_rpc_envelopes_and_noncanonical_hex_refused(self):
        good = dict(ok=True, addr="0x9F080000", len=boxes.END, hex=publication().hex())
        for changes in (dict(ok=False), dict(addr="0x9F080001"), dict(len=boxes.END-1),
                        dict(hex=good["hex"][:-1]), dict(hex=" " + good["hex"][1:])):
            with self.assertRaises(debug.DebugError):
                boxes.observe_owned(lambda *a, **k: dict(good, **changes))


if __name__ == "__main__": unittest.main()
