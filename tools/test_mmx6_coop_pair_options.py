"""Public paired qualification options preserve existing lifecycle coverage."""
import contextlib
import io
import unittest

from qualify_mmx6_coop_pair import CONTACT_EXE_SHA, make_parser, validate_options
from mmx6_coop_contact import EXE_SHA


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
        self.assertFalse(default.personal_menu_smoke)
        self.assertFalse(default.contact_pause_contact_smoke)
        self.assertIsNone(default.original_disc)
        self.assertFalse(default.private_pause_smoke)
        self.assertIsNone(default.native_quit_scenario)
        self.assertIsNone(default.original_exe)
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

    def test_personal_menu_requires_crc_native_gameplay_and_default_loader(self):
        self.rejected("--personal-menu-smoke")
        self.rejected("--personal-menu-smoke", "--require-state-crc", "--admission-only")
        self.rejected("--personal-menu-smoke", "--require-state-crc", "--native-loader-diagnostic")
        args = self.parse("--personal-menu-smoke", "--require-state-crc")
        self.assertTrue(args.personal_menu_smoke and args.require_state_crc)
        self.assertFalse(args.lifecycle_smoke or args.enemy_targeting_smoke)

    def test_personal_menu_combines_with_existing_native_and_host_profile_checks(self):
        args = self.parse("--personal-menu-smoke", "--require-state-crc", "--lifecycle-smoke",
                          "--enemy-targeting-smoke", "--require-host-profile",
                          "--expected-host-profile", "mmx6.win64-clang22.loopback",
                          "--expected-host-profile-revision", "1")
        self.assertTrue(args.personal_menu_smoke and args.lifecycle_smoke and
                        args.enemy_targeting_smoke and args.require_host_profile)

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

    def contact_options(self):
        return ["--contact-pause-contact-smoke", "--original-disc", "original.bin",
                "--expected-exe-sha256", EXE_SHA, "--require-state-crc", "--require-host-profile",
                "--expected-host-profile", "mmx6.win64-clang22.loopback", "--expected-host-profile-revision", "1"]

    def test_contact_requires_exact_candidate_source_default_loader_crc_and_profile(self):
        self.assertEqual(CONTACT_EXE_SHA, EXE_SHA)
        args = self.parse(*self.contact_options())
        self.assertTrue(args.contact_pause_contact_smoke and args.require_state_crc and args.require_host_profile)
        self.assertEqual(args.expected_exe_sha256, EXE_SHA)
        for flag in ("--native-loader-diagnostic", "--admission-only"):
            self.rejected(*self.contact_options(), flag)
        self.rejected("--contact-pause-contact-smoke")
        self.rejected(*self.contact_options(), "--expected-exe-sha256", "a" * 64)
        self.rejected(*self.contact_options(), "--original-disc", "original.cue")

    def test_contact_cannot_omit_any_identity_or_evidence_guard(self):
        for flag, takes_value in (("--original-disc", True), ("--expected-exe-sha256", True),
                                  ("--require-state-crc", False), ("--require-host-profile", False),
                                  ("--expected-host-profile", True), ("--expected-host-profile-revision", True)):
            options = self.contact_options()
            index = options.index(flag)
            del options[index:index + (2 if takes_value else 1)]
            self.rejected(*options)
        self.rejected("--original-disc", "original.bin")

    def test_contact_keeps_existing_menu_lifecycle_options_but_needs_separate_r13_actor_case(self):
        args = self.parse(*self.contact_options(), "--personal-menu-smoke", "--lifecycle-smoke")
        self.assertTrue(args.personal_menu_smoke and args.lifecycle_smoke and args.contact_pause_contact_smoke)
        self.rejected(*self.contact_options(), "--enemy-targeting-smoke")

    def test_private_pause_requires_exact_image_profile_crc_and_its_own_fresh_case(self):
        options = ["--private-pause-smoke", "--expected-exe-sha256", "a"*64,
                   "--require-state-crc", "--require-host-profile",
                   "--expected-host-profile", "mmx6.win64-clang22.loopback",
                   "--expected-host-profile-revision", "2"]
        self.assertTrue(self.parse(*options).private_pause_smoke)
        for flag,takes_value in (("--expected-exe-sha256",True),("--require-state-crc",False),
                                 ("--require-host-profile",False)):
            incomplete=options.copy();at=incomplete.index(flag)
            del incomplete[at:at+(2 if takes_value else 1)]
            self.rejected(*incomplete)
        for flag in ("--admission-only","--native-loader-diagnostic","--personal-menu-smoke",
                     "--enemy-targeting-smoke","--lifecycle-smoke"):
            self.rejected(*options,flag)

    def quit_options(self):
        return ["--native-quit-scenario","guest_authority","--original-exe","SLUS_013.95",
                "--expected-exe-sha256","a"*64,"--require-state-crc","--require-host-profile",
                "--expected-host-profile","mmx6.win64-clang22.loopback","--expected-host-profile-revision","2"]

    def test_native_quit_requires_all_explicit_source_image_profile_and_crc_guards(self):
        args=self.parse(*self.quit_options())
        self.assertEqual(args.native_quit_scenario,"guest_authority")
        self.assertEqual(str(args.original_exe),"SLUS_013.95")
        self.assertEqual(self.parse(*self.quit_options(),"--native-quit-scenario","p1_pages_cancel").native_quit_scenario,"p1_pages_cancel")
        for flag,takes_value in (("--original-exe",True),("--expected-exe-sha256",True),
                                 ("--require-state-crc",False),("--require-host-profile",False),
                                 ("--expected-host-profile",True),("--expected-host-profile-revision",True)):
            options=self.quit_options();at=options.index(flag);del options[at:at+(2 if takes_value else 1)]
            self.rejected(*options)
        self.rejected("--original-exe","SLUS_013.95")
        self.rejected(*self.quit_options(),"--native-quit-scenario","final_quit")

    def test_native_quit_requires_separate_fresh_default_loader_pair(self):
        for flag in ("--admission-only","--native-loader-diagnostic","--personal-menu-smoke",
                     "--enemy-targeting-smoke","--lifecycle-smoke","--private-pause-smoke",
                     "--contact-pause-contact-smoke"):
            self.rejected(*self.quit_options(),flag)


if __name__ == "__main__":
    unittest.main()
