"""Pure runner/protocol/error ownership checks; no native process or socket."""
from dataclasses import replace
import io
import json
import os
import shutil
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import qualify_mmx6_input_replay as runner
from test_coop_debug_protocol import diagnostic


def host_status(seat=0, bits=0):
    pad = dict(connected=True, analog=False, type=0)
    return dict(host_input_slots=2, host_port=seat+1, host_layer=True, host_buttons=hex(0xFFFF ^ bits),
                slot0=pad, slot1=pad, override=-1, override_p2=-1, override_pad_type=-1, override_axes_valid=False)


class ProtocolTests(unittest.TestCase):
    def test_requires_real_port_capability_and_both_digital_slots(self):
        runner.verify_host_status(host_status(1, 0x20), 1, 0x20)
        for key, value in (("host_input_slots", None), ("host_port", 1), ("host_port", True),
                           ("host_layer", False), ("host_buttons", "ffff"), ("override_p2", 1),
                           ("override_axes_valid", True)):
            status = host_status(1, 0x20); status[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): runner.verify_host_status(status, 1, 0x20)
        for slot in (0, 1):
            for key, value in (("connected", False), ("analog", True), ("type", 1)):
                status = host_status(1); status[f"slot{slot}"] = dict(status[f"slot{slot}"], **{key:value})
                with self.assertRaises(ValueError): runner.verify_host_status(status, 1)

    def test_control_never_touches_another_listener_or_exited_process(self):
        process = Mock(pid=123); process.poll.return_value = None
        client, transcript = Mock(), io.StringIO()
        control = runner.control_for(process, 12345, client, transcript)
        with patch.object(runner.baseline, "owns_listener", return_value=False):
            with self.assertRaises(runner.debug.DebugError): control("quit")
        client.request.assert_not_called()
        process.poll.return_value = 0
        with patch.object(runner.baseline, "owns_listener") as ownership:
            with self.assertRaises(runner.debug.DebugError): control("quit")
            ownership.assert_not_called()
        process.poll.return_value = None; client.request.side_effect = runner.debug.DebugError("bad ACK")
        with patch.object(runner.baseline, "owns_listener", return_value=True):
            with self.assertRaises(runner.debug.DebugError): control("quit")
        self.assertIn("bad ACK", transcript.getvalue())

    def test_host_hold_releases_neutral_and_retains_original_failure(self):
        row = runner.debug.parse_diagnostic(diagnostic())
        report = {}; route = runner.HostRoute(Mock(), report, 1)
        route.sample = Mock(return_value=row); route.set = Mock()
        route.advance = Mock(side_effect=RuntimeError("native timeout"))
        with self.assertRaisesRegex(RuntimeError, "native timeout"): route.hold(1, 0x20, 12, "P2")
        self.assertEqual(route.set.call_args_list[-1].args, (1, 0))
        route.set.side_effect = [None, ValueError("neutral failed")]
        with self.assertRaisesRegex(RuntimeError, "native timeout"): route.hold(1, 0x20, 12, "P2")
        self.assertEqual(report["release_errors"][0]["original_error"], "native timeout")

    def test_route_uses_acknowledged_host_layer_without_direct_sio_or_guest_write(self):
        current = [0, 0]; commands = []
        def control(command, **fields):
            commands.append((command, fields))
            self.assertIn(command, ("set_input", "pad_status"))
            seat = fields["port"]-1
            if command == "set_input":
                self.assertEqual(fields["layer"], "host")
                current[seat] = int(fields["buttons"], 0) ^ 0xFFFF
                return dict(ok=True)
            return host_status(seat, current[seat])
        row = runner.debug.parse_diagnostic(diagnostic())
        start = replace(row, native_timer=10)
        moved = replace(start, native_timer=22, players=(start.players[0], replace(start.players[1], x_raw=start.players[1].x_raw+0x10000)))
        settled = replace(moved, native_timer=27)
        jumped = replace(settled, native_timer=32, players=(replace(settled.players[0], y_raw=settled.players[0].y_raw-0x10000), settled.players[1]))
        report = {}; route = runner.HostRoute(control, report, 1)
        with patch.object(runner.debug, "observe", side_effect=[start, start, moved, settled, settled, jumped]): route.exercise()
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(current, [0, 0])
        self.assertEqual([fields["port"] for command, fields in commands if command=="set_input"], [2, 2, 1, 1])

    def test_options_reject_unbounded_or_ambiguous_requests_before_launch(self):
        base = ["--build", "build", "--source", "source", "--disc", "disc", "--output", "output",
                "--expected-exe-sha256", "1"*64, "--expected-manifest-sha256", "2"*64]
        for extra in (["--boot-timeout", "nan"], ["--replay-timeout", "0"], ["--progress-timeout", "61"],
                      ["--record-port", "0"], ["--record-port", "24921"], ["--expected-exe-sha256", "bad"]):
            parser = runner.parser()
            with self.subTest(extra=extra), patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit):
                runner.options(parser, parser.parse_args(base+extra))


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mmx6-native-runner-", dir=os.environ["TEMP"])
        self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)

    def prepared(self):
        # Synthetic files only; Popen is always mocked in tests.
        recording, candidate, profile = (self.root / name for name in ("source", "candidate", "private"))
        recording.mkdir(); candidate.mkdir()
        exe = b"fixture image " + b"2"*64; (candidate / "mmx6-runtime.exe").write_bytes(exe)
        (candidate / "game.toml").write_text('[game]\nexe="original"\n')
        (candidate / "settings.toml").write_text('[controller]\np1_device="keyboard"\np2_device="keyboard"\n')
        settings = dict(declared_scope_available=1, input=dict(ports=[dict(seat=seat, device_kind=1, configured_mode=2, connected=1, type=0) for seat in (0, 1)]))
        implementation = dict(interpreted_overlays_sealed=1, oracle=0)
        artifacts = {"settings.json":runner.codec.canonical(settings), "content.json":b'{}\n',
                     "simulation-contract.json":runner.codec.canonical(implementation)}
        for name, data in artifacts.items(): (recording / name).write_bytes(data)
        identity = dict(image_sha256=runner.codec.sha256(exe), manifest_sha256="2"*64, execution_id="fixture",
                        settings_sha256=runner.codec.sha256(artifacts["settings.json"]),
                        content_sha256=runner.codec.sha256(artifacts["content.json"]),
                        simulation_contract_sha256=runner.codec.sha256(artifacts["simulation-contract.json"]),
                        mode="offline", profile=None, cards=[None, None], baseline=None)
        out=io.BytesIO(); writer=runner.codec.Encoder(out,identity)
        writer.append(dict(type="N",order=0,native=0,cycles=10,sim_tick=None,frame=20,caller=0x80012220,pads=[[0x40,0,0x40],[0,0,0]]))
        writer.append(dict(type="C",order=1,native=0,cycles=11,sim_tick=None,seat=1,consumer="stage",buttons=0x20));writer.finish()
        (recording / "inputs.jsonl").write_bytes(out.getvalue())
        (recording / "status.json").write_bytes(runner.codec.canonical(dict(contract=runner.codec.CONTRACT,epoch=1,failure="",schema=1,
                    scope=runner.replay_preparation.STATUS_SCOPE,status="finalized")))
        receipt = runner.replay_preparation.prepare(recording,candidate,profile)
        expected=dict(events=2,trace_sha256=runner.preparation.sha256(profile / "replay/inputs.jsonl"))
        result=dict(schema=1,epoch=1,contract=runner.codec.CONTRACT,trace_sha256=expected["trace_sha256"],events=2,consumed=2,status="consumed",failure="",
                    scope="ordered native/P2 consumption only; no full SIO or outcome qualification")
        return profile, receipt, expected, result

    def test_sanitized_child_environment_retains_only_owned_runtime_overrides(self):
        profile, receipt, _, _ = self.prepared()
        with patch.dict(os.environ, {"PSX_FORCE_INTERP":"1", "MMX6_INPUT_REPLAY":"old", "RNET_TEST":"x", "LNG_TEST":"x"}):
            environment = runner.replay_environment(profile,receipt)
        self.assertNotIn("PSX_FORCE_INTERP",environment);self.assertNotIn("RNET_TEST",environment);self.assertNotIn("LNG_TEST",environment)
        self.assertEqual(environment["MMX6_INPUT_REPLAY"],str(profile / "replay/inputs.jsonl"))
        self.assertEqual(environment["SDL_AUDIODRIVER"],"dummy")
        values = dict(receipt["environment"], TEMP=str(self.root / "outside"))
        (profile / "environment.json").write_text(json.dumps(values));receipt["environment"]=values
        with self.assertRaises(ValueError):runner.replay_environment(profile,receipt)

    def test_strict_consumed_result_rejects_missing_failed_stale_counts_and_boolean(self):
        profile, _, expected, result = self.prepared();runner.verify_replay_result(profile,result,expected)
        for key, value in (("status","failed"),("events",1),("consumed",1),("schema",True),("trace_sha256","f"*64),("failure","bad")):
            with self.subTest(key=key),self.assertRaises(ValueError):runner.verify_replay_result(profile,dict(result,**{key:value}),expected)
        changed=dict(result);changed.pop("scope")
        with self.assertRaises(ValueError):runner.verify_replay_result(profile,changed,expected)

    def test_capture_requires_exact_offline_identity_topology_and_both_consumed_inputs(self):
        _,receipt,_,_=self.prepared()
        candidate=self.root / "captured"
        recording=candidate / "saves/input-recordings/session-1"
        shutil.copytree(self.root / "source",recording)
        self.assertTrue(runner.native_capture_started(candidate))
        found,summary=runner.inspect_recording(candidate,receipt["image_sha256"],"2"*64)
        self.assertEqual(found,recording);self.assertEqual(summary["events"],2)
        for image,manifest in (("f"*64,"2"*64),(receipt["image_sha256"],"f"*64)):
            with self.assertRaises(ValueError):runner.inspect_recording(candidate,image,manifest)
        rows=[json.loads(line) for line in (recording / "inputs.jsonl").read_bytes().splitlines()]
        out=io.BytesIO();writer=runner.codec.Encoder(out,rows[0]["identity"])
        for event in rows[1:-1]:
            if event["type"]=="C":event["buttons"]=0
            writer.append(event)
        writer.finish();(recording / "inputs.jsonl").write_bytes(out.getvalue())
        with self.assertRaises(ValueError):runner.inspect_recording(candidate,receipt["image_sha256"],"2"*64)
        (recording / "inputs.jsonl").write_bytes((self.root / "source/inputs.jsonl").read_bytes())
        settings=runner.json_object(recording / "settings.json");settings["input"]["ports"][1]["connected"]=0
        (recording / "settings.json").write_bytes(runner.codec.canonical(settings))
        with self.assertRaises(ValueError):runner.inspect_recording(candidate,receipt["image_sha256"],"2"*64)
        shutil.copytree(self.root / "source",candidate / "saves/input-recordings/session-2")
        with self.assertRaises(ValueError):runner.inspect_recording(candidate,receipt["image_sha256"],"2"*64)

    def test_frontend_input_gate_waits_for_actual_complete_first_native_record(self):
        candidate=self.root / "record";candidate.mkdir()
        self.assertFalse(runner.native_capture_started(candidate))
        path=candidate / "saves/input-recordings/session-1/inputs.jsonl";path.parent.mkdir(parents=True)
        path.write_bytes(b'{"contract":')
        self.assertFalse(runner.native_capture_started(candidate))
        header=runner.codec.canonical(dict(type="header",schema=1,contract=runner.codec.CONTRACT,identity={}))
        path.write_bytes(header+b'{"caller":')
        self.assertFalse(runner.native_capture_started(candidate))
        first=dict(type="N",native=0,order=0,caller=0x80012220)
        path.write_bytes(header+runner.codec.canonical(first))
        self.assertTrue(runner.native_capture_started(candidate))
        first["type"]="C";path.write_bytes(header+runner.codec.canonical(first))
        with self.assertRaises(ValueError):runner.native_capture_started(candidate)

    def test_duplicate_json_fields_refuse(self):
        path=self.root / "ambiguous.json";path.write_bytes(b'{"schema":1,"schema":1}')
        with self.assertRaises(ValueError):runner.json_object(path)

    def test_stale_result_or_changed_command_refuses_before_popen(self):
        profile,receipt,expected,result=self.prepared();(profile / "replay-result.json").write_text(json.dumps(result))
        with patch.object(runner,"require_windows"),patch.object(runner,"reserve"),patch.object(runner.subprocess,"Popen") as launch:
            with self.assertRaises(ValueError):runner.run_replay(profile,receipt,12345,1,expected,{})
            launch.assert_not_called()
        (profile / "replay-result.json").unlink();receipt["arguments"].append("--headless")
        with patch.object(runner,"require_windows"),patch.object(runner,"reserve"),patch.object(runner.subprocess,"Popen") as launch:
            with self.assertRaises(ValueError):runner.run_replay(profile,receipt,12345,1,expected,{})
            launch.assert_not_called()

    def test_natural_consumed_exit_keeps_eof_limit_and_uses_owned_hidden_command(self):
        profile,receipt,expected,result=self.prepared()
        process=Mock(pid=123);process.poll.return_value=0
        def launched(*args,**kwargs):
            (profile / "replay-result.json").write_text(json.dumps(result));return process
        report={}
        with patch.object(runner,"require_windows"),patch.object(runner,"reserve"),patch.object(runner.subprocess,"Popen",side_effect=launched) as launch:
            runner.run_replay(profile,receipt,12345,1,expected,report)
        self.assertEqual(report["status"],"consumed");process.terminate.assert_not_called();process.kill.assert_not_called()
        self.assertIn("--hidden-window",launch.call_args.args[0]);self.assertEqual(launch.call_args.kwargs["cwd"],profile)
        self.assertNotIn("outcome",report)

    def test_replay_failure_requests_quit_only_its_listener_and_retains_failed_result(self):
        profile,receipt,expected,result=self.prepared();result.update(status="failed",consumed=0,failure="cycle diverged")
        process=Mock(pid=123);process.poll.return_value=None
        def launched(*args,**kwargs):
            (profile / "replay-result.json").write_text(json.dumps(result));return process
        def waited(timeout):process.poll.return_value=0
        process.wait.side_effect=waited;report={}
        with patch.object(runner,"require_windows"),patch.object(runner,"reserve"),patch.object(runner.subprocess,"Popen",side_effect=launched), \
                patch.object(runner.baseline,"owns_listener",return_value=False),patch.object(runner.debug,"DebugClient") as client:
            with self.assertRaises(runner.debug.DebugError):runner.run_replay(profile,receipt,12345,1,expected,report)
        client.return_value.request.assert_not_called();process.terminate.assert_not_called()
        self.assertEqual(report["runtime_result"]["failure"],"cycle diverged")
        self.assertIn("quit_protocol_error",report["cleanup"])

    def test_early_zero_exit_without_result_is_failure(self):
        profile,receipt,expected,_=self.prepared();process=Mock(pid=123);process.poll.return_value=0
        with patch.object(runner,"require_windows"),patch.object(runner,"reserve"),patch.object(runner.subprocess,"Popen",return_value=process):
            with self.assertRaises(OSError):runner.run_replay(profile,receipt,12345,1,expected,{})

    def test_replay_deadline_terminates_only_owned_popen_if_quit_listener_is_missing(self):
        profile,receipt,expected,_=self.prepared();process=Mock(pid=456);process.poll.return_value=None
        waits=[]
        def waited(timeout):
            waits.append(timeout)
            if len(waits)==1:raise runner.subprocess.TimeoutExpired("owned",5)
            process.poll.return_value=0
        process.wait.side_effect=waited;report={}
        with patch.object(runner,"require_windows"),patch.object(runner,"reserve"),patch.object(runner.subprocess,"Popen",return_value=process), \
                patch.object(runner.baseline,"owns_listener",return_value=False),patch.object(runner.debug,"DebugClient") as client, \
                patch.object(runner.time,"monotonic",side_effect=[0,2]):
            with self.assertRaisesRegex(runner.debug.DebugError,"deadline"):runner.run_replay(profile,receipt,12345,1,expected,report)
        client.return_value.request.assert_not_called()
        self.assertEqual(report["cleanup"]["shutdown"],"owned_popen_terminated")
        process.terminate.assert_called_once();process.kill.assert_not_called()

    def test_capture_reuses_owned_lifecycle_and_never_sends_direct_sio(self):
        candidate=self.root / "record";candidate.mkdir()
        (candidate / "preparation.json").write_text('{}')
        environment=dict(TEMP=str(candidate / "temp"))
        (candidate / "environment.json").write_text(json.dumps(environment))
        process=Mock(pid=123);process.poll.return_value=None
        row=runner.debug.parse_diagnostic(diagnostic());commands=[];held=[0,0]
        def request(command,**fields):
            commands.append(command)
            if command=="set_input":held[fields["port"]-1]=int(fields["buttons"],0)^0xFFFF
            if command=="pad_status":return host_status(fields["port"]-1,held[fields["port"]-1])
            if command=="read_ram":return dict(hex="0a00")
            if command=="quit":process.poll.return_value=0
            return dict(ok=True)
        report={}
        with patch.object(runner,"require_windows"),patch.object(runner,"reserve"),patch.object(runner.baseline,"candidate_environment",return_value=environment), \
                patch.object(runner.baseline,"owns_listener",return_value=True),patch.object(runner.subprocess,"Popen",return_value=process) as launch, \
                patch.object(runner.debug.DebugClient,"request",side_effect=request),patch.object(runner.HostRoute,"sample",return_value=row), \
                patch.object(runner.HostRoute,"exercise"),patch.object(runner,"native_capture_started",return_value=True):
            runner.run_capture(candidate,12345,1,1,report)
        self.assertEqual(report["cleanup"],dict(shutdown="graceful_owned_debug",exit_code=0))
        self.assertEqual(report["status"],"route_completed")
        self.assertEqual(set(commands),{"set_input","pad_status","read_ram","quit"})
        self.assertIn("--seal-interpreted-overlays",launch.call_args.args[0]);self.assertIn("--hidden-window",launch.call_args.args[0])
        self.assertEqual(launch.call_args.kwargs["env"]["SDL_AUDIODRIVER"],"dummy")
        self.assertEqual(held,[0,0]);process.terminate.assert_not_called()

    def test_image_failure_is_preserved_without_starting_capture(self):
        build=self.root / "build";build.mkdir();(build / "mmx6-runtime.exe").write_bytes(b"actual")
        args=SimpleNamespace(output=self.root / "report",build=build,expected_exe_sha256="0"*64)
        with patch.object(runner,"require_windows"),patch.object(runner.subprocess,"Popen") as launch:
            result=runner.run(args)
        self.assertEqual(result["status"],"failed_setup");self.assertEqual(result["r26"],"unverified");launch.assert_not_called()
        self.assertEqual(json.loads((args.output / "qualification.json").read_text())["error"]["type"],"ValueError")


if __name__ == "__main__": unittest.main()
