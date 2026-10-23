"""Public paired qualification options preserve existing lifecycle coverage."""
import contextlib
import io
import unittest

from qualify_mmx6_coop_pair import make_parser, validate_options


class PairOptionTests(unittest.TestCase):
    base = ["--tools-root", "tools", "--build", "build", "--disc", "disc.cue", "--out", "output"]

    def parse(self, *options):
        parser = make_parser()
        args = parser.parse_args(self.base + list(options))
        validate_options(parser, args)
        return args

    def rejected(self, *options):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.parse(*options)

    def test_existing_lifecycle_remains_opt_in_without_enemy_requirements(self):
        default = self.parse()
        self.assertFalse(default.lifecycle_smoke)
        self.assertFalse(default.enemy_targeting_smoke)
        self.assertFalse(default.require_host_profile)
        lifecycle = self.parse("--lifecycle-smoke")
        self.assertTrue(lifecycle.lifecycle_smoke)
        self.assertFalse(lifecycle.require_state_crc)

    def test_enemy_can_combine_with_existing_lifecycle_and_resolved_crc(self):
        args = self.parse("--enemy-targeting-smoke", "--require-state-crc", "--lifecycle-smoke",
                          "--expected-exe-sha256", "a" * 64)
        self.assertTrue(args.enemy_targeting_smoke and args.lifecycle_smoke and args.require_state_crc)

    def test_enemy_cannot_qualify_without_core_mod_or_default_loading(self):
        self.rejected("--enemy-targeting-smoke")
        self.rejected("--enemy-targeting-smoke", "--require-state-crc", "--native-loader-diagnostic")
        self.rejected("--enemy-targeting-smoke", "--require-state-crc", "--admission-only")

    def test_existing_admission_lifecycle_exclusion_and_explicit_hash(self):
        self.rejected("--admission-only", "--lifecycle-smoke")
        self.rejected("--expected-exe-sha256", "wrong")

    def test_host_profile_requires_explicit_expected_catalog_identity(self):
        self.rejected("--require-host-profile")
        self.rejected("--require-host-profile", "--expected-host-profile", "lab")
        self.rejected("--expected-host-profile", "lab", "--expected-host-profile-revision", "1")
        for name, revision in (("bad/name", "1"), ("Upper", "1"), ("a" * 32, "1"),
                               ("lab", "0"), ("lab", "4294967296")):
            self.rejected("--require-host-profile", "--expected-host-profile", name,
                          "--expected-host-profile-revision", revision)
        args = self.parse("--require-host-profile", "--expected-host-profile",
                          "mmx6.win64-clang22.loopback", "--expected-host-profile-revision", "1",
                          "--admission-only")
        self.assertTrue(args.require_host_profile and args.admission_only)
        self.assertFalse(args.require_state_crc)


if __name__ == "__main__":
    unittest.main()
