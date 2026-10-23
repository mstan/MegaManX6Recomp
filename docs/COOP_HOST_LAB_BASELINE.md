# Frozen development loopback baseline

Candidate `fbba0e3ae5e38174022fa7eb79ac81c3741ef391` built from clean game and
dependency inputs with Clang22.1.8. Executable SHA-256 is
`37cdc4876f7e852b97ef5f14210809b0af7d4a8adaa1759c9e096017170e1fa9`;
canonical declared manifest SHA-256 is
`5a1521fdf8682fbc8e28fee1fb3c4594d0b6a95844ea06ac3af61b998af28673`.
The manifest was independently recomputed, matched its compiled header and was
found in each staged executable. It covers declared inputs, not every external
binary or driver. Later QA/document commits do not change this frozen image.

The [complete compact receipt](evidence/mmx6-r13/manifest-bound-fbba0e3-summary.json)
retains clean source pins, raw report hashes, native checkpoints, all matching
CRC values/watermarks, completed image captures, startup identities and limits.
Private original reports remain under `G:/Temp/Codex/psxrecomp/x6-parity/`.

| Check | Actual result |
| --- | --- |
| Enabled developer build | 36/36 game CTests, including original content/audio reproduction and positive/negative catalog fixtures |
| `enemy-admission-r13-hostlab-fbba0e3` | 12 native local checks pass; P1 remains x144 across130 observations; original record25 initializes and takes native P2 attack damage |
| `netplay-hostlab-fbba0e3` | 16 checks pass, including original P2 input, native targeting/damage, held departure, blocked Select and healthy rejoin |
| Resolved core/mod checks | 46 equal common simulation-tick samples across six windows; every sample lies below both completed watermarks |
| Required host agreement | Both peers install actual image SHA, x64/features7f/backend2/FP2/interpreted overlays; identical profile/revision/selected SHA at cycles0/tick0 before guest execution |
| `netplay-hostlab-fbba0e3-restart` | Four startup checks pass using the same session ID202610239 and UDP ports; both peers settle a new matching selected identity before guest execution |

The initial selected identity is
`76fa1ee5aa70f0c2cc936259fe4296473e1d9e16fbb3727fe00cf3dc7a6fc94a`;
restart selects
`1fd199c5f927ba6051ec6880c3cb9dcb88f370f2a768de8853416c64ba6070c0`.
The confirmed profile remains `mmx6.win64-clang22.loopback`, revision1, with
semantic contract `b51aac8e2db53925b054688317c695ea21e3d940197947b1ce1fa1fe0286efe0`.
Final gameplay ticks are5529/5530, completed through5528/5529, with desync0.

Both native paused GL captures are byte-identical, SHA-256
`e6ffa554272645c3a9bc74752cf3055910ee970aabdd179763c97b7576751c94`.
The native X menu/portrait was inspected, together with local targeting/attack
and final gameplay captures. Final heroes overlap after rejoin; that image
does not establish separately visible bodies. The raw reports retain original
native initialization and HP transitions rather than inferring them from art.

All launches used private hidden/muted profiles, linked OpenBIOS, the default
resident loader, retained OpenGL/native4:3, delay3 and two numeric127.0.0.1
processes. No online SIO/mailbox/RAM mutation, state loading or original cards
were used. Owned PIDs49936/81412/46492/63476/77460 are gone. Positive runs needed
owned termination during bounded quit handling; valid graceful exit remains
unverified by those receipts. A [later native probe](COOP_DEBUG_QUIT_BASELINE.md)
found an acknowledgement race that can trigger termination before the wait;
the older records do not establish a timeout or hang.

This qualifies the bounded R13 mechanic and startup cell on this exact artifact.
The lab option remains OFF by default. Remote LAN/internet, other machines,
other compilers/CPU feature sets/OSes, launcher/lobby, physical controllers,
audible identity, rollback, rewind and the remaining campaign remain separate.
Existing helper linkage blocks and SPU ADSR failures remain recorded. No full
parity or broad production qualification follows.
