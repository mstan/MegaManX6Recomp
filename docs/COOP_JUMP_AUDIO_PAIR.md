# Same-machine private ground-jump audio qualification

`qualify_mmx6_coop_pair.py --jump-audio-smoke` runs one jump order on two
owned, hidden and muted processes. It uses the existing AudioObserver separately
on each peer; one peer cannot supply the other's sample, event or DSP evidence.
This route alone does not qualify full R4/R12, audible output, PCM fidelity,
music continuity, other sound families or another physical host.

Before launch it requires the exact expected executable and compiled manifest,
rehashes the declared game/generated inputs at the actual CMake source root,
and reproduces the original EXE/raw-disc audio contract and private bank bodies.
The runtime CUE must select that exact single MODE2/2352 raw BIN at index zero.
Both private profiles require the default loader, native aspect, no rewind,
and two persistent digital keyboard slots. Card paths are checked in the actual
`[runtime].memcard_dir` table by the shared profile validator.

Each logical seat publishes through its own peer's local host port1 with neutral
axes. Every control retains process/listener ownership and host acknowledgments;
the coordinator also waits for actual native action6 ascent on both peers before
releasing Cross. A requested one-tick window is insufficient proof of native
input consumption. Native ground/HP/form/speech and forward simulation clocks
remain separate checks. No RAM, SIO, mailbox, success flag or event-reset command
is used, and no RNG result is forced.

Each peer must identify both actual event-time bank/sample byte ranges, routing,
pitch and ADSR, an overlap, original end conditions and final DSP state. Original
immutable banks are fingerprinted before/after. Landing does not substitute for
voice completion: selected voices are drained through observed terminal events
before final DSP snapshots. The whole audio case has a fixed120-second deadline
and at most32 native attempts. Missing vocals or no common overlap remains an
explicit inconclusive result.

The [reviewed v18 receipt](evidence/mmx6-jump-audio/manifest-bound-348a52c-paired-orders-reviewed.json)
covers X first and Zero first on fresh same-machine pairs. Both peers pass all
19 bounded audio checks independently in each order; the earlier inconclusive
eight-trial run is retained. Other sound families and full R4/R12 qualification
remain open.

The pair uses different numeric127.0.0.1 UDP endpoints, delay3, and the same
fixed profile/revision/selection before guest frame0. Resolved core/mod checks
are required before and after the audio case. Both peers must then release their
host slots, acknowledge owned Quit, exit0 and preserve private cards. Cleanup,
card or final profile failures revoke any earlier observer success.

Run each order in a separate fresh output directory. Example for the preserved
v18 image (the source must still match its declared inputs):

```powershell
. 'G:/Temp/Codex/psxrecomp/x6-parity/main-environment.ps1'
& 'C:/Users/Matthew/AppData/Local/Programs/Python/Python312/python.exe' tools/qualify_mmx6_coop_pair.py `
  --tools-root 'F:/Projects/psxrecomp/_wt-mmx6-x4-parity/tools' `
  --source 'F:/Projects/psxrecomp/_wt-mmx6-x4-parity' `
  --build 'G:/Temp/Codex/psxrecomp/x6-parity/frozen-build-v18-348a52c' `
  --disc 'G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).cue' `
  --original-disc 'G:/Temp/Codex/psxrecomp/x6-parity/disc/Mega Man X6 (USA) (v1.1).bin' `
  --original-exe 'G:/Temp/Codex/psxrecomp/x6-parity/disc/SLUS_013.95' `
  --out 'G:/Temp/Codex/psxrecomp/x6-parity/paired-jump-audio-FRESH' `
  --expected-exe-sha256 8198893ef9f023b59be1a9eb768977f55e7f2feae40f0ce581e322870ab4f229 `
  --expected-manifest-sha256 3198d0285ac8dde9636c9aac5dd79399621d820a38f7561907fe4fa2b90af68b `
  --jump-audio-smoke --audio-first-seat 0 --audio-max-attempts 32 `
  --require-state-crc --require-host-profile `
  --expected-host-profile mmx6.win64-clang22.loopback --expected-host-profile-revision 2
```

Use `--audio-first-seat 1` with another fresh directory for Zero first. Other
optional behavioral routes are mutually exclusive. Pure protocol tests exercise
independent peer event/sample attribution, actual held-ascent/clock gates,
missing RNG overlap, late voice terminals, source refusal before Popen and
cleanup revocation. They launch no game and establish no native audio pass.
