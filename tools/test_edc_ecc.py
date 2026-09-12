#!/usr/bin/env python3
"""Tests for the clean-room CD-ROM EDC/ECC recompute (tools/edc_ecc.py).

These check the code's defining properties rather than diffing against a
stored answer, so they prove correctness without depending on any other
implementation:

  * the EDC table matches a bit-at-a-time CRC over the ECMA-130 polynomial;
  * every P and Q vector of a recomputed sector has both Reed-Solomon
    syndromes zero (that IS the parity condition the standard states);
  * the fast whole-row parity path agrees with the scalar reference on
    random and adversarial sector contents;
  * non-Mode-2-Form-1 sectors are left untouched.

Set MMX6_EDC_ECC_REF_BIN to a known-good PS1 BIN image to additionally
verify that recomputing it changes nothing (the end-to-end check; it is
skipped when the variable is unset, since disc images are never committed).
"""

from __future__ import annotations

import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).absolute().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import edc_ecc


def make_sector(rng, *, mode=0x02, submode=0x08, data=None) -> bytearray:
    """A syntactically valid Mode 2 Form 1 sector with random payload."""
    sector = bytearray(edc_ecc.SECTOR_SIZE)
    sector[0:12] = edc_ecc.SYNC
    sector[12:16] = bytes([rng.randrange(256), rng.randrange(256),
                           rng.randrange(256), mode])
    subheader = bytes([0x01, 0x00, submode, 0x00])
    sector[16:20] = subheader
    sector[20:24] = subheader
    sector[24:2072] = data if data is not None else bytes(
        rng.randrange(256) for _ in range(2048))
    return sector


def crc_bitwise(data: bytes) -> int:
    """CRC-32 over P(x) = x^32+x^31+x^16+x^15+x^4+x^3+x+1, LSB-first."""
    reflected = 0xD8018001
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (reflected if crc & 1 else 0)
    return crc & 0xFFFFFFFF


def vector_syndromes(sector, geom, dest):
    """Yield (s0, s1) for every code vector of one pass of a sector.

    The ECC treats the header as zero, so the caller passes a sector whose
    bytes 12..15 are already zeroed.
    """
    major_count, minor_count, major_mult, minor_inc = geom
    size = major_count * minor_count
    for major in range(major_count):
        index = (major // 2) * major_mult + (major % 2)
        members = []
        for _ in range(minor_count):
            members.append(sector[edc_ecc._ECC_BASE + index])
            index += minor_inc
            if index >= size:
                index -= size
        members.append(sector[dest + major])
        members.append(sector[dest + major + major_count])
        s0 = 0
        s1 = 0
        power = len(members) - 1
        for value in members:
            s0 ^= value
            s1 ^= edc_ecc._gf_mul(value, edc_ecc._GF_EXP[power % 255])
            power -= 1
        yield s0, s1


class EdcTests(unittest.TestCase):
    def test_table_matches_bitwise_crc(self) -> None:
        rng = random.Random(1)
        for length in (0, 1, 7, 64, 2056):
            data = bytes(rng.randrange(256) for _ in range(length))
            self.assertEqual(edc_ecc.edc_block(data), crc_bitwise(data),
                             f"length {length}")

    def test_edc_is_stored_little_endian_over_subheader_and_data(self) -> None:
        sector = make_sector(random.Random(2))
        self.assertTrue(edc_ecc.recompute_sector(sector))
        expected = edc_ecc.edc_block(bytes(sector[16:2072]))
        self.assertEqual(bytes(sector[2072:2076]),
                         expected.to_bytes(4, "little"))

    def test_edc_detects_a_single_bit_flip(self) -> None:
        rng = random.Random(3)
        sector = make_sector(rng)
        edc_ecc.recompute_sector(sector)
        before = bytes(sector[2072:2076])
        sector[24 + rng.randrange(2048)] ^= 0x01
        self.assertNotEqual(
            edc_ecc.edc_block(bytes(sector[16:2072])).to_bytes(4, "little"),
            before)


class EccParityTests(unittest.TestCase):
    def assert_parity_holds(self, sector: bytearray) -> None:
        probe = bytearray(sector)
        probe[12:16] = b"\x00\x00\x00\x00"
        for name, geom, dest in (("P", edc_ecc._P_GEOM, edc_ecc._P_DEST),
                                 ("Q", edc_ecc._Q_GEOM, edc_ecc._Q_DEST)):
            for major, (s0, s1) in enumerate(
                    vector_syndromes(probe, geom, dest)):
                self.assertEqual((s0, s1), (0, 0),
                                 f"{name} vector {major} syndromes {s0},{s1}")

    def test_syndromes_vanish_on_random_sectors(self) -> None:
        rng = random.Random(4)
        for _ in range(4):
            sector = make_sector(rng)
            self.assertTrue(edc_ecc.recompute_sector(sector))
            self.assert_parity_holds(sector)

    def test_syndromes_vanish_on_degenerate_payloads(self) -> None:
        rng = random.Random(5)
        for payload in (bytes(2048), b"\xff" * 2048,
                        bytes(range(256)) * 8):
            sector = make_sector(rng, data=payload)
            self.assertTrue(edc_ecc.recompute_sector(sector))
            self.assert_parity_holds(sector)

    def test_fast_path_matches_scalar_reference(self) -> None:
        rng = random.Random(6)
        for _ in range(6):
            base = make_sector(rng)
            fast = bytearray(base)
            slow = bytearray(base)
            self.assertTrue(edc_ecc.recompute_sector(fast))
            self.assertTrue(edc_ecc.recompute_sector_reference(slow))
            self.assertEqual(bytes(fast), bytes(slow))

    def test_parity_is_independent_of_the_header_address(self) -> None:
        rng = random.Random(7)
        payload = bytes(rng.randrange(256) for _ in range(2048))
        first = make_sector(random.Random(8), data=payload)
        second = make_sector(random.Random(9), data=payload)
        self.assertNotEqual(bytes(first[12:16]), bytes(second[12:16]))
        edc_ecc.recompute_sector(first)
        edc_ecc.recompute_sector(second)
        self.assertEqual(bytes(first[2072:]), bytes(second[2072:]))


class SectorSelectionTests(unittest.TestCase):
    def test_form2_sector_is_left_alone(self) -> None:
        sector = make_sector(random.Random(10), submode=0x28)  # bit 5 set
        before = bytes(sector)
        self.assertFalse(edc_ecc.recompute_sector(sector))
        self.assertEqual(bytes(sector), before)

    def test_mode1_and_audio_sectors_are_left_alone(self) -> None:
        mode1 = make_sector(random.Random(11), mode=0x01)
        before = bytes(mode1)
        self.assertFalse(edc_ecc.recompute_sector(mode1))
        self.assertEqual(bytes(mode1), before)

        audio = bytearray(random.Random(12).randbytes(edc_ecc.SECTOR_SIZE))
        audio[0:12] = b"\x11" * 12          # no sync pattern
        before = bytes(audio)
        self.assertFalse(edc_ecc.recompute_sector(audio))
        self.assertEqual(bytes(audio), before)

    def test_wrong_sector_length_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            edc_ecc.recompute_sector(bytearray(2048))


class ImageTests(unittest.TestCase):
    def _write_image(self, sectors) -> Path:
        handle = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
        for sector in sectors:
            handle.write(bytes(sector))
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return Path(handle.name)

    def test_recompute_then_verify_is_clean(self) -> None:
        rng = random.Random(13)
        sectors = [make_sector(rng) for _ in range(6)]
        sectors.append(make_sector(rng, submode=0x28))
        path = self._write_image(sectors)

        first = edc_ecc.recompute_image(path)
        self.assertEqual(first["sectors"], 7)
        self.assertEqual(first["form1"], 6)
        self.assertEqual(first["skipped"], 1)
        self.assertEqual(first["changed"], 6)

        second = edc_ecc.recompute_image(path, verify_only=True)
        self.assertEqual(second["changed"], 0)

    def test_recompute_ranges_touches_only_the_written_sectors(self) -> None:
        rng = random.Random(14)
        sectors = [make_sector(rng) for _ in range(5)]
        path = self._write_image(sectors)
        edc_ecc.recompute_image(path)
        original = path.read_bytes()

        # Corrupt the user data of sectors 1 and 3, but only declare sector 1.
        blob = bytearray(original)
        for index in (1, 3):
            blob[index * edc_ecc.SECTOR_SIZE + 100] ^= 0x5A
        path.write_bytes(bytes(blob))

        stats = edc_ecc.recompute_ranges(
            path, [(edc_ecc.SECTOR_SIZE * 1 + 100, 1)])
        self.assertEqual(stats["sectors"], 1)
        self.assertEqual(stats["changed"], 1)

        result = path.read_bytes()
        one = slice(edc_ecc.SECTOR_SIZE, 2 * edc_ecc.SECTOR_SIZE)
        three = slice(3 * edc_ecc.SECTOR_SIZE, 4 * edc_ecc.SECTOR_SIZE)
        self.assertNotEqual(result[one][2072:], original[one][2072:])
        self.assertEqual(result[three][2072:], original[three][2072:])

    def test_recompute_ranges_rejects_a_write_past_the_end(self) -> None:
        path = self._write_image([make_sector(random.Random(15))])
        with self.assertRaises(ValueError):
            edc_ecc.recompute_ranges(path, [(edc_ecc.SECTOR_SIZE, 4)])

    def test_ragged_image_is_rejected(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
        handle.write(b"\x00" * (edc_ecc.SECTOR_SIZE + 7))
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        with self.assertRaises(ValueError):
            edc_ecc.recompute_image(handle.name, verify_only=True)


class ReferenceImageTests(unittest.TestCase):
    """End-to-end check against a real disc, when one is available locally."""

    def test_known_good_image_needs_no_change(self) -> None:
        reference = os.environ.get("MMX6_EDC_ECC_REF_BIN")
        if not reference:
            self.skipTest("set MMX6_EDC_ECC_REF_BIN to a known-good PS1 BIN")
        stats = edc_ecc.recompute_image(reference, verify_only=True)
        self.assertGreater(stats["form1"], 0, "no Mode 2 Form 1 sectors found")
        self.assertEqual(stats["changed"], 0,
                         f"{stats['changed']} of {stats['form1']} Mode 2 "
                         "Form 1 sectors disagree with the recompute")


if __name__ == "__main__":
    unittest.main()
