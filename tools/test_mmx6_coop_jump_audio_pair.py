"""Pure two-process observation/control fixtures; never native audio evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import mmx6_coop_jump_audio_pair as adapter
import qualify_mmx6_coop_pair as runner
from test_mmx6_coop_jump_audio import CONTRACT, reply
from test_mmx6_coop_jump_audio_private import event, hardware, private_voices, tone
from test_mmx6_coop_native_reentry_pair import InputClient


class Fixture:
    def __init__(self, root, *, silent_peer=None, wrong_sample_peer=None, early_end_peer=None):
        self.root, self.silent, self.wrong, self.early = root, silent_peer, wrong_sample_peer, early_end_peer
        self.air, self.controls, self.observers, self.tick = set(), [], [], 100
        self.image = b"synthetic two-peer pure fixture, never executable"
        self.sha = hashlib.sha256(self.image).hexdigest()
        fixture = self
        class Client(InputClient):
            def __init__(self, peer): super().__init__(); self.peer = peer
            def host_input(self, bits=0):
                fixture.controls.append((self.peer, bits))
                result = super().host_input(bits)
                if bits:
                    fixture.air.add(self.peer)
                    for observer in fixture.observers:
                        if observer.peer != fixture.silent: observer.add(self.peer)
                elif fixture.early is not None and fixture.observers:
                    observer = fixture.observers[fixture.early]
                    if self.peer in observer.live: observer.end(self.peer)
                return result
            def request(self, command, **fields):
                if command in ("spu_voices", "spu_private_voices"):
                    value = hardware() if command == "spu_voices" else private_voices()
                    if fixture.observers:
                        for seat, keyon in fixture.observers[self.peer].latest.items():
                            if (seat == 0) == (command == "spu_voices"):
                                value["voices"][20].update(start=f"0x{keyon['addr']:05X}",
                                    sample_bank=keyon["sample_bank"], pitch=f"0x{keyon['pitch']:04X}",
                                    adsr_lo=f"0x{keyon['adsr_lo']:04X}", adsr_hi=f"0x{keyon['adsr_hi']:04X}")
                    return value
                return super().request(command, **fields)
        self.clients = [Client(i) for i in (0, 1)]
        self.peers = []
        for peer in (0, 1):
            directory = root/f"peer-{peer}"; (directory/"saves").mkdir(parents=True)
            (directory/"mmx6-runtime.exe").write_bytes(self.image)
            (directory/"preparation.json").write_text(json.dumps(dict(exe_sha256=self.sha)))
            self.peers.append(dict(directory=str(directory), preparation=dict(exe_sha256=self.sha)))
        checks = ("host_profile_settled_before_guest", "declared_build_manifest_bound_to_staged_images",
                  "default_resident_loader_committed", "jump_audio_original_source_bound", "jump_audio_declared_sources_match")
        self.report = dict(candidate_exe_sha256=self.sha, peers=self.peers, checks={k: True for k in checks},
            resolved_state_crc=["actual resolved sample fixture"], host_profile_startup={"fixed": True},
            host_profile_build_manifest={"declared_sha256": "b"*64}, jump_audio_prepared=[{}, {}])
        self.ctx = dict(clients=self.clients, report=self.report, output=root,
            both=lambda fn: [fn(0), fn(1)], network=self.network, native_advance=self.advance)
        self.source = dict(contract=CONTRACT, private_banks=adapter.audio.private_bank_contract(CONTRACT))
        class Observer:
            def __init__(self, client, request, contract, *, private_banks):
                self.peer, self.events, self.pending, self.live, self.latest = client.peer, [], [], {}, {}
                self.cursor = 1000*self.peer; self.next = self.cursor; self.count = 0
                self.private_banks = private_banks; fixture.observers.append(self)
            def add(self, seat):
                t = tone("X", 6) if seat == 0 else tone("Zero", 7)
                raw = event(self.next, 100+self.count, 20 if seat == 0 else 44, 0 if seat == 0 else 31,
                            address=338464 if seat == 0 else t["offset"])
                row = adapter.audio.parse_events(reply(raw, total=self.next+1), require_banks=True)[1][0]
                self.next += 1; self.pending.append(row); self.live[seat] = row; self.latest[seat] = row
            def end(self, seat):
                keyon = self.live.pop(seat)
                self.pending.append(dict(keyon, seq=self.next, frame=100+self.count, kind="END_STOP"))
                self.next += 1
            def poll(self):
                self.count += 1; rows = self.pending; self.pending = []; self.events.extend(rows); self.cursor = self.next
                players = [dict(character=c, form=f, state=1, action=6 if c in fixture.air else 2,
                    hp=32, speech_gate=0, airborne=1 if c in fixture.air else 0, ground=c not in fixture.air,
                    y=90 if c in fixture.air else 100, vy=1, x=100) for c, f in ((0, 1), (1, 5))]
                body = [dict(active=1, state=p["state"], character=p["character"], action=p["action"],
                             hp=p["hp"], y_raw=p["y"]) for p in players]
                return dict(observation=dict(ready=1, enrolled=1, failed=0, mailbox=0, native_mode=10,
                    native_phase=0, scene_owner=0, pause_owner=0, lifecycle=(0, 0), players=body,
                    native_timer=self.count, tick=self.count), players=players, event_total=self.cursor, new_events=rows)
            def driver(self): return dict(release_adjust=0, vab_status=[1]*16)
            def fingerprint_banks(self): return copy.deepcopy(self.private_banks["banks"])
            def identify(self, e, driver):
                return dict(tone=tone("X", 6) if e["v"] == 20 else tone("Zero", 7),
                    sample_bank=e["sample_bank"], sample_matches=self.peer != fixture.wrong,
                    observed_sha256=("a" if self.peer == 0 else "b")*64)
        self.Observer = Observer

    def network(self):
        self.tick += 1
        return [dict(tick=self.tick, resolved_through=self.tick-1) for _ in (0, 1)]

    def advance(self, frames, label):
        self.air.clear()
        for observer in self.observers:
            for seat in list(observer.live): observer.end(seat)

    def run(self, **options):
        with patch.object(adapter.audio, "AudioObserver", self.Observer):
            return adapter.exercise(self.ctx, expected_sha=self.sha, source=self.source, max_attempts=1, **options)


class PairObservationTests(unittest.TestCase):
    def test_landing_does_not_substitute_for_each_peers_voice_terminal(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture=Fixture(Path(temporary));drains=[]
            def advance(frames,label):
                fixture.air.clear()
                if label=="audio-vocal-lifetime-drain":
                    drains.append(frames)
                    for observer in fixture.observers:
                        for seat in list(observer.live):observer.end(seat)
            fixture.ctx["native_advance"]=advance
            for peer,client in enumerate(fixture.clients):
                original=client.request
                def request(command,_peer=peer,_original=original,**fields):
                    if command in ("spu_voices","spu_private_voices") and fixture.observers:
                        self.assertFalse(fixture.observers[_peer].live,
                            "Final DSP read happened before this peer's retained end event")
                    return _original(command,**fields)
                client.request=request
            case=fixture.run()
            self.assertEqual(case["status"],adapter.SUCCESS)
            self.assertTrue(drains)
            self.assertTrue(all(record["checks"]["p1_natural_end"] and record["checks"]["p2_natural_end"]
                                for record in case["peers"]))

    def test_both_orders_use_independent_events_identity_dsp_and_lifetime(self):
        for first in (0, 1):
            with self.subTest(first=first), tempfile.TemporaryDirectory() as temporary:
                fixture = Fixture(Path(temporary)); case = fixture.run(first_seat=first)
                self.assertEqual(case["status"], adapter.SUCCESS)
                self.assertEqual(len(case["checks"]), 38)
                self.assertTrue(all(case["checks"].values()), case["checks"])
                self.assertEqual([r["actors"][0]["seat"] for r in case["peers"]], [first, first])
                self.assertEqual([r["actors"][0]["keyon"]["seq"] for r in case["peers"]], [0, 1000])
                self.assertEqual([r["actors"][0]["identity"]["observed_sha256"] for r in case["peers"]], ["a"*64, "b"*64])
                self.assertEqual(fixture.controls[:4], [(first, 0x4000), (first, 0), (first ^ 1, 0x4000), (first ^ 1, 0)])
                self.assertEqual(fixture.controls[-2:], [(0, 0), (1, 0)])
                for held in case["inputs"]:
                    self.assertEqual(len(held["peers"]), 2)
                    self.assertTrue(all(r["acknowledgment"]["status"]["host_port"] == 1 for r in held["peers"]))

    def test_one_wrong_peer_cannot_borrow_other_peers_sample_proof(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary), wrong_sample_peer=1); case = fixture.run()
            self.assertEqual(case["status"], "comparison_failed")
            self.assertTrue(case["checks"]["peer0_p2_source_sample"])
            self.assertFalse(case["checks"]["peer1_p2_source_sample"])
            self.assertFalse(fixture.report["checks"]["jump_audio_both_peers_completed"])

    def test_rng_missing_on_one_peer_or_expired_window_stays_inconclusive(self):
        for options in (dict(silent_peer=1), dict(early_end_peer=1)):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as temporary:
                fixture = Fixture(Path(temporary), **options); case = fixture.run()
                self.assertEqual(case["status"], adapter.INCONCLUSIVE)
                self.assertEqual(case["checks"], {})
                self.assertFalse(fixture.report["checks"]["jump_audio_both_peers_completed"])
                self.assertIn("skip", case["attempts"][0])
                self.assertEqual(fixture.controls[-2:], [(0, 0), (1, 0)])

    def test_raw_prefix_and_original_failure_survive_a_neutral_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary)); poll = fixture.Observer.poll
            def fail_second(observer):
                if observer.peer == 1 and observer.count >= 3:
                    fixture.clients[0].fail_neutral = True
                    raise adapter.audio.AudioQualificationError("peer1 truncated independent audio stream")
                return poll(observer)
            with patch.object(fixture.Observer, "poll", fail_second), self.assertRaisesRegex(adapter.audio.AudioQualificationError, "truncated independent"):
                fixture.run()
            case = fixture.report["jump_audio_pair"]
            self.assertIn("truncated independent", case["error"]["message"])
            self.assertTrue(case["peers"][0]["events"])
            self.assertEqual(case["status"], "failed_cleanup")
            self.assertEqual(len(fixture.report["jump_audio_input_cleanup_errors"]), 1)
            self.assertEqual(fixture.clients[1].bits, 0)

    def test_missing_startup_or_image_or_published_route_refuses_before_input(self):
        for mutate in (lambda f:f.report["checks"].update(jump_audio_declared_sources_match=False),
                       lambda f:f.report.update(resolved_state_crc=[]),
                       lambda f:f.peers[1]["preparation"].update(exe_sha256="0"*64),
                       lambda f:(f.root/"peer-1/mmx6-runtime.exe").write_bytes(b"changed"),
                       lambda f:setattr(f.clients[1], "reentry_route", None)):
            with tempfile.TemporaryDirectory() as temporary:
                fixture = Fixture(Path(temporary)); mutate(fixture)
                with self.assertRaises(ValueError): fixture.run()
                self.assertFalse(fixture.controls)

    def test_native_jump_requires_actual_action6_ascent_and_separate_clock_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Fixture(Path(temporary)); case = fixture.run()
            receipt = case["inputs"][0]["peers"][0]
            before = case["observations"][1]["peers"][0]
            held = copy.deepcopy(before)
            held["observation"] = copy.deepcopy(receipt["end"])
            held["observation"]["native_timer"] = receipt["start"]["native_timer"]
            with self.assertRaisesRegex(adapter.audio.AudioQualificationError, "clock|evidence"):
                adapter.held_receipt(before, held, 0, {}, [], [], "bad clock")


class OwnedRouteAndCleanupTests(unittest.TestCase):
    def test_installation_retains_checks_and_separate_pid_listener_transcripts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); handles = []; clients = [InputClient(), InputClient()]
            for peer in (0, 1): (root/f"peer-{peer}/logs").mkdir(parents=True)
            report = dict(checks=dict(retained=True), resolved_state_crc=["retained"])
            try:
                adapter.install_routes(clients, [Mock(pid=111), Mock(pid=222)], [24001, 24002], report, root, handles)
                self.assertEqual([r["owned_pid"] for r in report["jump_audio_published_routes"]], [111, 222])
                self.assertEqual([r["debug_port"] for r in report["jump_audio_published_routes"]], [24001, 24002])
                self.assertEqual(report["checks"], dict(retained=True))
                self.assertEqual(report["resolved_state_crc"], ["retained"])
            finally:
                for handle in handles: handle.close()

    def test_only_both_owned_ack_exit_zero_and_unchanged_cards_preserve_success(self):
        for change in (None, "card", "exit", "ownership", "release"):
            report = dict(status="passed", default_intro_qualified=True, default_launch_qualified=True,
                checks={}, jump_audio_private_cards_before=[{}, {}],
                peers=[dict(shutdown="graceful_owned_debug", exit_code=0) for _ in (0, 1)])
            if change == "exit": report["peers"][1]["exit_code"] = 1
            if change == "release": report["peers"][1]["input_release_errors"] = ["rejected"]
            final = [{"private.mcd": "changed"}, {}] if change == "card" else [{}, {}]
            with patch.object(adapter.ownership, "cards", return_value=final):
                adapter.finalize(report, Path("owned"), runtime_ready=True, owned_processes=1 if change == "ownership" else 2)
            self.assertEqual(report["status"], "passed" if change is None else "failed")
            self.assertEqual(report["default_intro_qualified"], change is None)


class BeforeLaunchTests(unittest.TestCase):
    def test_bad_original_contract_refuses_before_staging_or_popen(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); build = root/"build"; build.mkdir(); (build/"mmx6-runtime.exe").write_bytes(b"fixture")
            args = runner.make_parser().parse_args(["--tools-root", str(Path(__file__).parent), "--source", str(root),
                "--build", str(build), "--disc", str(root/"runtime.cue"), "--out", str(root/"unused"), "--jump-audio-smoke"])
            with patch.object(adapter, "load_sources", side_effect=ValueError("source contract mismatch")), \
                    patch.object(adapter.ownership.preparation, "prepare") as prepare, patch.object(runner.subprocess, "Popen") as launch:
                with self.assertRaisesRegex(ValueError, "source contract mismatch"): runner.run(args)
            prepare.assert_not_called(); launch.assert_not_called()

    def test_wrong_manifest_or_declared_source_is_retained_without_launch(self):
        import coop_host_profile as profiles
        for failure in ("manifest", "source"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary); build=root/"build"; build.mkdir(); image=b"fixture"
                (build/"mmx6-runtime.exe").write_bytes(image)
                args=runner.make_parser().parse_args(["--tools-root",str(Path(__file__).parent),"--source",str(root),
                    "--build",str(build),"--disc",str(root/"runtime.cue"),"--out",str(root/"output"),
                    "--original-disc",str(root/"original.bin"),"--original-exe",str(root/"SLUS_013.95"),
                    "--jump-audio-smoke","--require-host-profile","--expected-host-profile","mmx6.win64-clang22.loopback",
                    "--expected-host-profile-revision","2","--require-state-crc","--expected-manifest-sha256","b"*64,
                    "--expected-exe-sha256",hashlib.sha256(image).hexdigest()])
                def prepare(_build,_source,directory,_disc,*,automated):
                    self.assertTrue(automated)
                    for name in ("logs","saves","mods"):(directory/name).mkdir(parents=True,exist_ok=True)
                    (directory/"mmx6-runtime.exe").write_bytes(image)
                    (directory/"environment.json").write_text(json.dumps(environment))
                    return dict(exe_sha256=args.expected_exe_sha256,source_card=None)
                environment={k:str(root/"private") for k in ("TEMP","TMP","LOCALAPPDATA","APPDATA","PSX_RESIDENT_CACHE","PSX_OVERLAY_CACHE_DIR")}
                environment["PSX_OVERLAY_AUTOCOMPILE_OFF"]="1"
                source=dict(disc=dict(cue="fixed"),contract=CONTRACT,private_banks=adapter.audio.private_bank_contract(CONTRACT))
                with patch.object(adapter,"load_sources",return_value=source), \
                        patch.object(adapter.ownership,"bind_original_disc",return_value=source["disc"]), \
                        patch.object(adapter.ownership.preparation,"prepare",side_effect=prepare), \
                        patch.object(adapter.ownership,"prepare_profile",return_value={}), \
                        patch.object(adapter.sources,"verify_prepared_originals",return_value={}), \
                        patch.object(adapter.ownership.host.baseline,"candidate_environment",return_value=environment), \
                        patch.object(profiles,"validate_build_manifest",return_value=dict(declared_sha256=("c" if failure=="manifest" else "b")*64)), \
                        patch.object(adapter.sources,"validate_sources",side_effect=ValueError("source refused")) as verify_source, \
                        patch.object(runner.socket,"socket",return_value=Mock()), patch.object(runner.subprocess,"Popen") as launch:
                    report=runner.run(args)
                launch.assert_not_called()
                if failure=="manifest":verify_source.assert_not_called()
                else:verify_source.assert_called_once()
                self.assertEqual(report["status"],"failed_setup")
                self.assertIn("manifest" if failure=="manifest" else "source refused",report["error"])
                self.assertTrue((root/"output/qualification.json").is_file())


if __name__ == "__main__": unittest.main()
