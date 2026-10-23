"""Pure private replay preparation checks, no executable/game is launched."""
from __future__ import annotations
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

import mmx6_input_recording as codec
from prepare_mmx6_input_replay import prepare, STATUS_SCOPE


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mmx6-replay-preparation-", dir=os.environ["TEMP"])
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.recording, self.candidate, self.output = (self.root / name for name in ("recording", "candidate", "private"))
        self.recording.mkdir(); self.candidate.mkdir()
        self.exe = b"synthetic executable fixture bytes; declared manifest=" + b"2" * 64
        (self.candidate / "mmx6-runtime.exe").write_bytes(self.exe)
        (self.candidate / "game.toml").write_text('[game]\nexe = "original-exe"\n')
        (self.candidate / "settings.toml").write_text('[video]\naspect_ratio = "4:3"\n')
        (self.candidate / "keybinds.ini").write_text("original key alternatives\n")
        self.card = bytes(range(256)) * 512
        settings, content, implementation = b'{}\n', b'{"content":1}\n', b'{"sealed":1}\n'
        self.identity = dict(image_sha256=codec.sha256(self.exe), manifest_sha256="2" * 64,
                             execution_id="fixture-execution", settings_sha256=codec.sha256(settings),
                             content_sha256=codec.sha256(content), simulation_contract_sha256=codec.sha256(implementation),
                             mode="offline", profile=None, cards=[dict(sha256=codec.sha256(self.card), bytes=len(self.card)), None], baseline=None)
        for name, data in (("settings.json", settings), ("content.json", content),
                           ("simulation-contract.json", implementation), ("card1.initial.mcd", self.card)):
            (self.recording / name).write_bytes(data)
        self.write_trace()
        self.status = dict(contract=codec.CONTRACT, epoch=1, failure="", schema=1, scope=STATUS_SCOPE, status="finalized")
        self.write_status()

    def write_trace(self, *, failure=None):
        out = io.BytesIO(); writer = codec.Encoder(out, self.identity)
        writer.append(dict(type="N", order=0, native=0, cycles=10, sim_tick=None, frame=20,
                           caller=0x80012220, pads=[[0, 0, 0], [0, 0, 0]]))
        writer.finish(failure=failure)
        (self.recording / "inputs.jsonl").write_bytes(out.getvalue())

    def write_status(self):
        (self.recording / "status.json").write_bytes(codec.canonical(self.status))

    def run_prepare(self):
        return prepare(self.recording, self.candidate, self.output)

    def test_stages_owned_initial_cards_and_preserves_configuration_sources(self):
        receipt = self.run_prepare()
        self.assertFalse(receipt["runtime_qualified"])
        self.assertEqual((self.output / "saves/card1.mcd").read_bytes(), self.card)
        self.assertEqual((self.recording / "card1.initial.mcd").read_bytes(), self.card)
        self.assertFalse((self.output / "saves/card2.mcd").exists())
        self.assertEqual((self.output / "settings.toml").read_bytes(), (self.candidate / "settings.toml").read_bytes())
        self.assertEqual((self.output / "keybinds.ini").read_bytes(), (self.candidate / "keybinds.ini").read_bytes())
        self.assertIn("--seal-interpreted-overlays", receipt["arguments"])
        self.assertEqual(receipt["arguments"][-1], "--no-launcher")
        self.assertEqual((self.output / "replay-profile.txt").read_bytes(),
                         ("mmx6-native-replay-private-v1\n" + receipt["image_sha256"] + "\n" +
                          receipt["trace_sha256"] + "\n").encode("ascii"))
        for path in receipt["environment"].values():
            if path != "dummy":
                self.assertTrue(Path(path).is_relative_to(self.output))

    def test_changed_image_refused(self):
        (self.candidate / "mmx6-runtime.exe").write_bytes(self.exe + b"changed")
        with self.assertRaises(ValueError): self.run_prepare()
        self.assertFalse(self.output.exists())

    def test_changed_bundle_card_and_absence_refused(self):
        for name in ("settings.json", "content.json", "simulation-contract.json", "card1.initial.mcd", "card2.initial.mcd"):
            path = self.recording / name
            old = path.read_bytes() if path.exists() else None
            path.write_bytes(b"changed")
            with self.assertRaises(ValueError, msg=name): self.run_prepare()
            if old is None: path.unlink()
            else: path.write_bytes(old)

    def test_truncated_and_poisoned_trace_refused(self):
        self.write_trace(failure="fixture input")
        with self.assertRaises(ValueError): self.run_prepare()
        self.write_trace(); path = self.recording / "inputs.jsonl"; path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaises(ValueError): self.run_prepare()

    def test_network_and_restored_state_refused(self):
        self.identity["mode"] = "netplay"
        self.identity["profile"] = dict(id="fixture", revision=1, selected_sha256="4" * 64)
        # Fixture writer requires network ticks, so retain canonical zero ticks.
        out = io.BytesIO(); writer = codec.Encoder(out, self.identity)
        writer.append(dict(type="N", order=0, native=0, cycles=10, sim_tick=0, frame=20,
                           caller=0x80012220, pads=[[0, 0, 0], [0, 0, 0]])); writer.finish()
        (self.recording / "inputs.jsonl").write_bytes(out.getvalue())
        with self.assertRaises(ValueError): self.run_prepare()
        self.identity["mode"] = "offline"; self.identity["profile"] = None
        self.identity["baseline"] = dict(sha256="5" * 64, bytes=1024); self.write_trace()
        with self.assertRaises(ValueError): self.run_prepare()

    def test_failed_malformed_status_refused(self):
        for key, value in (("schema", True), ("epoch", True), ("status", "running"), ("failure", "tainted")):
            original = self.status[key]; self.status[key] = value; self.write_status()
            with self.assertRaises(ValueError): self.run_prepare()
            self.status[key] = original
        self.write_status()
        path = self.recording / "status.json"; path.write_bytes(path.read_bytes().replace(b'"schema":1', b'"schema":1,"schema":1'))
        with self.assertRaises(ValueError): self.run_prepare()

    def test_existing_output_preserved(self):
        self.output.mkdir(); sentinel = self.output / "keep"; sentinel.write_bytes(b"preserve")
        with self.assertRaises(ValueError): self.run_prepare()
        self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_missing_original_preferences_refused(self):
        (self.candidate / "settings.toml").unlink()
        with self.assertRaises(ValueError): self.run_prepare()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
