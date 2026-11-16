"""Source/card preservation and catalog isolation for local QA staging."""
import json
from pathlib import Path
import tempfile
import shutil
import subprocess
import tomllib
import unittest

from prepare_mmx6_coop_playtest import prepare, sha256
from qualify_mmx6_coop_baseline import candidate_environment


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.build, self.source, self.discs = [self.root / name for name in ("build", "source", "disc")]
        for path in (self.build / "bios", self.source, self.discs):
            path.mkdir(parents=True)
        (self.build / "mmx6-runtime.exe").write_bytes(b"fixture, never executed")
        (self.build / "bios/openbios.bin").write_bytes(b"fixture BIOS")
        (self.source / "game.toml").write_text('[game]\nexe="mmx6/SLUS_013.95"\ndisc="old.cue"\n[runtime]\nmemcard_dir="old"\noverlay_autocompile_cmd="old command"\n')
        self.disc = self.discs / "original.cue"
        self.disc.write_text('FILE "original.bin" BINARY\n')
        (self.discs / "SLUS_013.95").write_bytes(b"original boot executable")
        self.package("mmx6.local-coop")

    def package(self, name):
        path = self.build / "mods/bundled" / name / "0.0.1"
        path.mkdir(parents=True)
        (path / "manifest.toml").write_text(f'format_version=5\nid="{name}"\nversion="0.0.1"\n')

    def test_original_card_and_build_are_preserved(self):
        card = self.root / "genuine.mcd"
        original = bytes(range(256)) * 512
        card.write_bytes(original)
        before = (self.source / "game.toml").read_bytes()
        result = prepare(self.build, self.source, self.root / "candidate", self.disc, card)
        self.assertEqual(card.read_bytes(), original)
        self.assertEqual((self.source / "game.toml").read_bytes(), before)
        self.assertEqual((self.root / "candidate/saves/card1.mcd").read_bytes(), original)
        self.assertFalse(result["runtime_qualified"])

    def test_forbidden_packages_never_reach_candidate(self):
        self.package("psx.enhancement.cd-speed")
        self.package("psx.enhancement.fast-loading")
        output = self.root / "candidate"
        result = prepare(self.build, self.source, output, self.disc)
        self.assertEqual(result["packages"], ["mmx6.local-coop"])
        self.assertFalse((output / "mods/bundled/psx.enhancement.cd-speed").exists())
        self.assertFalse((output / "mods/bundled/psx.enhancement.fast-loading").exists())
        config = tomllib.loads((output / "game.toml").read_text())
        self.assertEqual(Path(config["game"]["exe"]), self.discs / "SLUS_013.95")
        self.assertEqual(config["runtime"]["overlay_autocompile_cmd"], "")
        environment = json.loads((output / "environment.json").read_text())
        self.assertTrue(all(str(output.resolve()) in environment[name]
                            for name in ("TEMP", "TMP", "APPDATA", "LOCALAPPDATA", "PSX_RESIDENT_CACHE")))

    def test_pgxp_peer_staging_selects_the_exact_image(self):
        image = self.build / "mmx6-runtime_pgxp.exe"
        image.write_bytes(b"PGXP fixture, never executed")
        output = self.root / "candidate"
        result = prepare(self.build, self.source, output, self.disc,
                         executable_name=image.name)
        self.assertEqual((output / "mmx6-runtime.exe").read_bytes(), image.read_bytes())
        self.assertEqual(result["exe_sha256"], sha256(image))
        self.assertEqual((self.build / "mmx6-runtime.exe").read_bytes(), b"fixture, never executed")

    def test_existing_output_is_never_overwritten(self):
        output = self.root / "candidate"
        output.mkdir()
        marker = output / "owner-file"
        marker.write_text("preserve")
        with self.assertRaisesRegex(ValueError, "already exists"):
            prepare(self.build, self.source, output, self.disc)
        self.assertEqual(marker.read_text(), "preserve")

    def test_reject_bad_card_before_any_output(self):
        card = self.root / "invalid.mcd"
        card.write_bytes(b"not a native card")
        output = self.root / "candidate"
        with self.assertRaisesRegex(ValueError, "128 KiB"):
            prepare(self.build, self.source, output, self.disc, card)
        self.assertFalse(output.exists())

    def test_automated_profile_and_environment_cannot_escape(self):
        output = self.root / "candidate"
        receipt = prepare(self.build, self.source, output, self.disc, automated=True)
        settings = tomllib.loads((output / "settings.toml").read_text())
        self.assertEqual(settings["controller"]["p1_device"], "keyboard")
        self.assertEqual(candidate_environment(output.resolve(), receipt)["SDL_AUDIODRIVER"], "dummy")
        env_path = output / "environment.json"
        original = json.loads(env_path.read_text())
        changed = dict(original, TEMP=str(self.root / "outside"))
        env_path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, "private profile"):
            candidate_environment(output.resolve(), receipt)
        env_path.write_text(json.dumps(dict(original, UNEXPECTED="unsafe")))
        with self.assertRaisesRegex(ValueError, "environment keys"):
            candidate_environment(output.resolve(), receipt)
        env_path.write_text(json.dumps(original))
        (output / "game.toml").write_text("changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            candidate_environment(output.resolve(), receipt)

    @unittest.skipUnless(shutil.which("git"), "Git is required for source-observation evidence")
    def test_tracked_source_changes_are_retained_without_claiming_build_binding(self):
        git = [shutil.which("git"), "-C", str(self.source)]
        def run(*args):
            return subprocess.run(git + list(args), check=True, capture_output=True).stdout
        run("init")
        run("add", "game.toml")
        run("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-m", "Synthetic source fixture")
        head = run("rev-parse", "HEAD").decode().strip()
        (self.source / "game.toml").write_text((self.source / "game.toml").read_text()+"# local edit\n")
        output = self.root / "candidate"
        receipt = prepare(self.build, self.source, output, self.disc)
        observation = receipt["source_observation"]
        self.assertEqual(observation["build_source_binding"], "unverified_from_staging")
        record = observation["repositories"]["game"]
        self.assertEqual(record["commit"], head)
        self.assertTrue(record["tracked_changes"])
        self.assertIn(b"local edit", Path(record["patch"]).read_bytes())
        self.assertEqual(record["patch_sha256"], sha256(Path(record["patch"])))
        candidate_environment(output.resolve(), receipt)
        Path(record["patch"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "Source observation artifact changed"):
            candidate_environment(output.resolve(), receipt)


if __name__ == "__main__":
    unittest.main()
