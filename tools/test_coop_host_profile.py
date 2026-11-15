"""Pure negative evidence tests; no runner, game, original assets or sockets."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from coop_host_profile import (HostProfileError, MissingHostProfile,
                               parse_host_profile, validate_build_manifest,
                               verify_host_profile_pair)


IMAGE, SELECTED = "a" * 64, "b" * 64
PROFILE = "mmx6.win64-clang22.loopback"


def capability(**changes):
    fields = dict(image=IMAGE, arch=2, features="7f", backend=2, fp=2, offers=1)
    fields.update(changes)
    return ("psxrecomp: actual-image-sha256={image} cpu-arch={arch} features={features} "
            "backend={backend} fp={fp} overlays=interpreted offers={offers}\n").format(**fields)


def settlement(**changes):
    fields = dict(profile=PROFILE, revision=1, selected=SELECTED, cycles=0, tick=0, before=1)
    fields.update(changes)
    return ("psxrecomp: host profile settled profile={profile} revision={revision} "
            "selected_sha256={selected} cycles={cycles} sim_tick={tick} "
            "before-enter-guest={before}\n").format(**fields)


VALID = capability() + settlement()


class HostProfileLogTests(unittest.TestCase):
    def verify(self, first=VALID, second=VALID, **kwargs):
        return verify_host_profile_pair([first, second], [IMAGE, IMAGE], PROFILE, 1, **kwargs)

    def test_installed_strings_with_unrelated_stderr_and_crlf(self):
        result = self.verify("unrelated startup\n" + VALID.replace("\n", "\r\n"))
        self.assertEqual(result["selected_sha256"], SELECTED)
        self.assertEqual(result["peers"][0]["capabilities"]["features"], 0x7F)

    def test_missing_and_uncommitted_records_never_qualify(self):
        for text in ("", capability(), settlement(), VALID.rstrip("\n")):
            with self.subTest(text=text), self.assertRaises(HostProfileError):
                self.verify(text)
        with self.assertRaises(MissingHostProfile):
            self.verify(VALID.rstrip("\n"), final=False)
        self.verify(VALID, final=False)

    def test_duplicate_including_identical_and_late_restart_rejected(self):
        for extra in (capability(), settlement(), VALID):
            with self.subTest(extra=extra), self.assertRaisesRegex(HostProfileError, "Duplicate"):
                self.verify(VALID + extra)
        self.verify(VALID, final=False)
        with self.assertRaises(HostProfileError):
            self.verify(VALID, VALID + settlement(), final=True)

    def test_malformed_marked_records_are_not_ignored(self):
        malformed = (VALID.replace(IMAGE, "a" * 63), VALID.replace(SELECTED, "g" * 64),
                     VALID.replace("features=7f", "features=0x7f"),
                     VALID.replace(" fp=2 ", " fp=2 fp=2 "),
                     VALID.replace("overlays=interpreted", "overlays=native"),
                     VALID.replace("cpu-arch=2", "cpu-arch=unknown"),
                     VALID.replace(PROFILE, "Upper"),
                     VALID.replace("psxrecomp:", "unexpected-prefix:"),
                     VALID.replace("offers=1\n", "offers=1 extra=1\n"),
                     VALID + "psxrecomp: host profile settled malformed\n")
        for text in malformed:
            with self.subTest(text=text), self.assertRaises(HostProfileError):
                self.verify(text)

    def test_late_guest_or_wrong_preguest_marker_rejected(self):
        for changes in (dict(cycles=1), dict(tick=1), dict(before=0), dict(before=2)):
            with self.subTest(changes=changes), self.assertRaises(HostProfileError):
                self.verify(capability() + settlement(**changes))

    def test_expected_image_profile_revision_and_peer_identity_are_bound(self):
        for text in (capability(image="c" * 64) + settlement(),
                     capability() + settlement(profile="other"),
                     capability() + settlement(revision=2),
                     capability() + settlement(selected="d" * 64)):
            with self.subTest(text=text), self.assertRaises(HostProfileError):
                self.verify(VALID, text)
        with self.assertRaises(HostProfileError):
            verify_host_profile_pair([VALID, VALID], [IMAGE, "c" * 64], PROFILE, 1)

    def test_unknown_cpu_backend_fp_and_empty_or_unbounded_offers_fail(self):
        for changes in (dict(arch=0), dict(arch=4), dict(features="3f"),
                        dict(backend=1), dict(backend=3), dict(fp=0), dict(fp=1),
                        dict(offers=0), dict(offers=2), dict(offers=9)):
            with self.subTest(changes=changes), self.assertRaises(HostProfileError):
                self.verify(capability(**changes) + settlement())

    def test_extra_feature_bits_cannot_extend_the_current_lab_rule(self):
        future = capability(features="1000000007f") + settlement()
        with self.assertRaises(HostProfileError):
            self.verify(future, future)
        with self.assertRaises(HostProfileError):
            self.verify(future, VALID)

    def test_runtime_integer_widths_and_record_order_are_checked(self):
        for text in (capability(arch=1 << 32) + settlement(),
                     capability(features="1" + "0" * 16) + settlement(),
                     capability() + settlement(revision=1 << 32),
                     capability() + settlement(cycles=1 << 64),
                     capability() + settlement(tick=1 << 32),
                     settlement() + capability()):
            with self.subTest(text=text), self.assertRaises(HostProfileError):
                self.verify(text)


class BuildManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mmx6-host-profile-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = self.root / "psx_build_manifest/psx-runtime/Release"
        self.directory.mkdir(parents=True)
        self.images = [self.root / f"peer-{seat}.exe" for seat in range(2)]
        self.item = dict(schema=1, coverage="declared-build-inputs-v1", whole_binary=False,
                         heterogeneous_qualified=False,
                         files={"game/src/plugin.inc": dict(sha256="e" * 64, bytes=123)},
                         configuration_by_language={"C": {"compiler": "Clang 22.1.8"}})
        self.write()

    def write(self):
        item = dict(self.item)
        digest = hashlib.sha256(json.dumps(item, sort_keys=True, separators=(",", ":"),
                                          ensure_ascii=True).encode("ascii")).hexdigest()
        item["sha256"] = digest
        (self.directory / "manifest.json").write_text(json.dumps(item), encoding="utf8")
        (self.directory / "manifest.h").write_text(
            f'#pragma once\n#define PSX_BUILD_MANIFEST_SHA256 "{digest}"\n'
            '#define PSX_BUILD_MANIFEST_SCHEMA 1\n', encoding="ascii")
        for image in self.images:
            image.write_bytes(b"fixture-image\0" + digest.encode("ascii") + b"\0end")
        return digest

    def validate(self, **kwargs):
        return validate_build_manifest(self.root, self.images, **kwargs)

    def test_actual_manifest_schema_canonical_hash_header_and_image_binding(self):
        record = self.validate(evidence_directory=self.root / "evidence")
        self.assertFalse(record["whole_binary"])
        self.assertTrue(record["staged_images_contain_compiled_sha256"])
        self.assertEqual((self.root / "evidence/host-profile-build-manifest.json").read_bytes(),
                         (self.directory / "manifest.json").read_bytes())

    def test_explicit_pgxp_target_preserves_same_manifest_validation(self):
        target = self.root / "psx_build_manifest/psx-runtime-pgxp"
        self.directory.parent.rename(target)
        self.directory = target / self.directory.name
        self.validate(target="psx-runtime-pgxp")
        with self.assertRaises(HostProfileError):
            self.validate()
        with self.assertRaises(HostProfileError):
            self.validate(target="../other")

    def test_canonical_digest_rejects_changed_input_and_header(self):
        path = self.directory / "manifest.json"
        item = json.loads(path.read_text())
        item["files"]["game/src/plugin.inc"]["sha256"] = "f" * 64
        path.write_text(json.dumps(item))
        with self.assertRaisesRegex(HostProfileError, "canonical"):
            self.validate()
        self.write()
        header = self.directory / "manifest.h"
        header.write_text(header.read_text().replace("SHA256 \"", "SHA256 \"0"))
        with self.assertRaisesRegex(HostProfileError, "header"):
            self.validate()

    def test_missing_ambiguous_or_duplicate_json_evidence_rejected(self):
        header = self.directory / "manifest.h"
        header.unlink()
        with self.assertRaises(HostProfileError):
            self.validate()
        self.write()
        alternate = self.directory.parent / "Debug"
        alternate.mkdir()
        (alternate / "manifest.json").write_bytes((self.directory / "manifest.json").read_bytes())
        with self.assertRaisesRegex(HostProfileError, "unambiguous"):
            self.validate()
        (alternate / "manifest.json").unlink()
        path = self.directory / "manifest.json"
        path.write_text(path.read_text().replace('"schema": 1', '"schema": 1, "schema": 1'))
        with self.assertRaisesRegex(HostProfileError, "Duplicate"):
            self.validate()

    def test_one_unbound_staged_image_or_duplicate_header_cannot_pass(self):
        self.images[1].write_bytes(b"different compiled manifest")
        with self.assertRaisesRegex(HostProfileError, "staged executable"):
            self.validate()
        digest = self.write()
        header = self.directory / "manifest.h"
        header.write_text(header.read_text() + f'#define PSX_BUILD_MANIFEST_SHA256 "{digest}"\n')
        with self.assertRaises(HostProfileError):
            self.validate()

    def test_malformed_metadata_and_broader_qualification_claims_rejected(self):
        for change in (dict(schema=True), dict(whole_binary=True), dict(heterogeneous_qualified=True),
                       dict(files={}), dict(files={"game/a": dict(sha256="bad", bytes=3)}),
                       dict(files={"game/a": dict(sha256="e" * 64, bytes=-1)})):
            original = self.item
            self.item = dict(original, **change)
            self.write()
            with self.subTest(change=change), self.assertRaises(HostProfileError):
                self.validate()
            self.item = original

    def test_non_json_number_and_extra_header_schema_rejected(self):
        path = self.directory / "manifest.json"
        path.write_text(path.read_text().replace('"bytes": 123', '"bytes": NaN'))
        with self.assertRaises(HostProfileError):
            self.validate()
        self.write()
        header = self.directory / "manifest.h"
        header.write_text(header.read_text() + '#define PSX_BUILD_MANIFEST_SCHEMA 1\n')
        with self.assertRaises(HostProfileError):
            self.validate()

    def test_embedded_digest_crossing_stream_chunk_boundary_is_found(self):
        digest = self.write().encode("ascii")
        self.images[0].write_bytes(b"x" * (1024 * 1024 - 32) + digest + b"y")
        self.validate()


if __name__ == "__main__":
    unittest.main()
