"""Offline contact CLI guards only; no process, original disc or profile created."""
import contextlib
import io
import unittest

from qualify_mmx6_coop_contact import make_parser, validate_options
from mmx6_coop_contact import EXE_SHA


class OfflineContactOptions(unittest.TestCase):
    identity = ["--original-disc", "original.bin", "--expected-exe-sha256", EXE_SHA]

    def parse(self, *options):
        parser = make_parser()
        args = parser.parse_args(list(options))
        validate_options(parser, args)
        return args

    def rejected(self, *options):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.parse(*options)

    def test_prepared_profile_requires_raw_bin_and_exact_frozen_hash(self):
        args = self.parse("--candidate", "fresh", *self.identity)
        self.assertEqual(args.port, 24897)
        self.assertEqual(args.expected_exe_sha256, EXE_SHA)
        self.assertIsNone(args.build)
        self.assertIsNone(args.disc)
        self.rejected("--candidate", "fresh", "--expected-exe-sha256", EXE_SHA)
        self.rejected("--candidate", "fresh", "--original-disc", "original.bin")
        self.rejected("--candidate", "fresh", *self.identity, "--expected-exe-sha256", "a" * 64)
        self.rejected("--candidate", "fresh", *self.identity, "--original-disc", "original.cue")

    def test_build_mode_requires_all_staging_inputs_distinct_from_original_source(self):
        base = ["--build", "compiled", *self.identity]
        self.rejected(*base)
        self.rejected(*base, "--source", "source", "--disc", "runtime.cue")
        args = self.parse(*base, "--source", "source", "--disc", "runtime.cue", "--output", "fresh")
        self.assertEqual(str(args.disc), "runtime.cue")
        self.assertEqual(str(args.original_disc), "original.bin")
        self.rejected(*base, "--candidate", "prepared", "--source", "source", "--disc", "runtime.cue", "--output", "fresh")

    def test_candidate_cannot_restage_or_silently_override_r2_cursor_route(self):
        for flag in ("--source", "--disc", "--output"):
            self.rejected("--candidate", "fresh", *self.identity, flag, "unused")
        self.rejected("--candidate", "fresh", *self.identity, "--cursor-change", "right")

    def test_shared_port_and_deadline_guards_remain_in_force(self):
        for flag, value in (("--port", "0"), ("--timeout", "nan"),
                            ("--timeout", "601"), ("--progress-timeout", "0")):
            self.rejected("--candidate", "fresh", *self.identity, flag, value)


if __name__ == "__main__":
    unittest.main()
