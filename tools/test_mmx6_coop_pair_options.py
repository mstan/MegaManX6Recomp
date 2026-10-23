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


if __name__ == "__main__":
    unittest.main()
