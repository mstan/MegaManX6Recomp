"""Freeze all 234 X4 comparisons and maintain X6's evidence-gated ledger.

Read-only source access uses git objects at the pinned X5 commit, never its
possibly dirty worktree. No game files, network calls, or runtime are needed.
--initialize creates the initial ledger; --render updates its Markdown view;
--check validates committed provenance and the existing ledger without writing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import ntpath
from collections import Counter
from pathlib import Path

X4_COMMIT = "50593bca772b600de6911cbfecd40b0f08721147"
X5_COMMIT = "9ed460e7b7e60769fa12bcab74e228ae19796214"
X6_COMMIT = "6cba3f8"
X5_REPO = Path("F:/Projects/psxrecomp/_wt-mmx5-x4-parity")
TABLE_PATH = "docs/COOP_X4_REFERENCE.md"
MANIFEST_PATH = "docs/COOP_X4_REFERENCE_SOURCES.json"
LEDGER_PATH = "docs/COOP_PARITY_LEDGER.json"
SOURCE_BLOBS = {
    TABLE_PATH: "5753e21749e35139497ae931b62fb01b97ac37dc",
    MANIFEST_PATH: "ac18787b46c6bb93b6282317cc89ffcfeff76969",
}
EXPECTED_IDS = [f"R{i}" for i in range(1, 27)] + [f"F{i}" for i in range(1, 209)]

# Anchors describe inspected baseline code, not proof of a gameplay behavior.
# An absent X6 content analogue must stay unknown until native content research.
ANCHORS = {
    "input": ["src/mods/mmx6_coop_plugin.c:p2_input", "src/mods/mmx6_coop_plugin.c:controller"],
    "lifecycle": ["src/mods/mmx6_coop_lifecycle.c:mmx6_coop_fatal", "src/mods/mmx6_coop_plugin.c:begin_join"],
    "scene": ["src/mods/mmx6_coop_plugin.c:scene_begin", "src/mods/mmx6_coop_plugin.c:scene_tick", "src/mods/mmx6_coop_plugin.c:door_begin"],
    "menu": ["src/mods/mmx6_coop_plugin.c:stage_tick", "src/mods/mmx6_coop_plugin.c:menu_vram"],
    "render": ["src/mods/mmx6_coop_plugin.c:render_actor", "src/mods/mmx6_coop_plugin.c:draw_coop_hud"],
    "camera": ["src/mods/mmx6_coop_plugin.c:shared_camera", "src/mods/mmx6_coop_plugin.c:camera_target"],
    "combat": ["src/mods/mmx6_coop_plugin.c:enemy_hit", "src/mods/mmx6_coop_plugin.c:player_contact"],
    "solid": ["src/mods/mmx6_coop_plugin.c:solid_player_collision", "src/mods/mmx6_coop_plugin.c:solid_as_zero"],
    "pickup": ["src/mods/mmx6_coop_plugin.c:pickup_as_seat", "src/mods/mmx6_coop_plugin.c:pickup_tick", "src/mods/mmx6_coop_plugin.c:nightmare_soul"],
    "assets": ["src/mods/mmx6_coop_plugin.c:enter_zero", "src/mods/mmx6_coop_plugin.c:leave_zero_context", "src/mods/mmx6_coop_plugin.c:load_assets"],
    "diagnostics": ["src/mods/mmx6_coop_plugin.c:diagnostics", "src/mods/mmx6_coop_plugin.c:diagnostic_setup"],
    "netplay": ["src/mods/mmx6_coop_plugin.c:netplay_profile", "tools/test_coop_netplay_runtime.py:main"],
    "enhancements": ["src/mods/mmx6_general_foundations_armor.inc", "src/mods/mmx6_zero_techniques_resolver.cpp"],
}

# Explicit native mapping: ID|workstream|mapping state|X6 counterpart|bounded check.
# U means the original mechanic's exact X6 analogue is unidentified; C means a
# candidate location/feature requiring native-content confirmation; I means the
# baseline code identifies the subsystem, not that its behavior has passed.
MAPPINGS = """
R1|netplay|I|DualShock controller and lobby admission|Select two distinct pads; launch native X6 through Host/Join and verify independent accepted inputs on both peers, then repeat Windows/Linux.
R2|combat|I|Zero incoming contact after personal pause|Accept the same native enemy contact before and after Zero's own menu; compare only Zero HP/reaction and retained X resources.
R3|render|I|X/Zero native death effects|Kill each seat at a distinct position; retain composed native burst colors, origin, expiry and surviving partner control.
R4|assets|I|X/Zero voice sample identity|Capture native X and Zero jump, attack, hurt and death tones; compare each with a co-op-off character reference.
R5|render|I|Stacked X6 life-meter anchoring|Change each actor's HP and inspect actual final-window meter anchors at several drawable aspects.
R6|render|C|Stacked default and optional side-by-side meters|Baseline stacks Zero at P2_HUD_Y=104; implement the elective alternate layout and inspect portrait/HP/ammo ownership in both.
R7|menu|I|X6 native Quit confirmation drawing|Enter each reachable native Quit confirmation; inspect whether world bodies, meters and attack effects hide at the native UI boundary.
R8|menu|I|Zero-owned pause resource restoration|Pause and resume Zero; reject X resume input, then independently move and attack with retained personal equipment and artwork.
R9|assets|C|X-owned charge, projectile and dash effects|First enable X in either seat; charge/release and dash after each owned menu, retaining allocation owner, native lifetime and composed art.
R10|scene|U|Authored X6 water-entry effect analogue unidentified|Locate a native surface-crossing callback before testing a leading partner splash/ripple; another particle or underwater room does not satisfy the trigger.
R11|scene|C|D-1000 intro admission|Reach the authored intro boss trigger with the guest first; observe original encounter activation, passenger landing and both controls.
R12|assets|C|Simultaneous X/Zero voice channels|Overlap actual jump/hurt and attack events; retain tone identity and natural channel lifetimes so one actor cannot steal the other's voice.
R13|camera|U|Native enemy placement admission for a leading partner|Map an authored X6 scanner/record, leave the primary outside its window and require guest-triggered initialization plus actual enemy interaction.
R14|camera|C|Nightmare alternate-route camera admission|Enter a genuine alternate-route trigger with the partner first while the primary remains outside; verify room limits, collision, controls and native return.
R15|menu|I|Guest Quit and campaign identity|Try guest Quit, then primary Quit/Continue and character selection; verify shared progression, roster and subsequent guest menu ownership.
R16|scene|U|Native vehicle READY sequence analogue unidentified|Inventory X6 vehicle entrances before selecting a counterpart; verify one shared READY controller if such an entrance exists.
R17|scene|U|Vehicle-to-boss arena handoff analogue unidentified|Identify an X6 vehicle/boss transition or document a content-specific absence; ordinary boss entry cannot close this vehicle handoff comparison.
R18|lifecycle|U|Vehicle section continuation with a fallen rider unidentified|Establish an authored vehicle/foot boundary first; then compare survivor, retry budget and roster after native continuation.
R19|scene|C|Investigator defeat and departure cleanup|Land a native final hit with either actor; follow both victory/departure states through selector return without a second guest victory cycle.
R20|scene|C|Investigator completion and stage-selector portrait|Defeat an Investigator, perform native save/selector return, re-enter and cold-load; compare clear bits, portrait and persisted progress.
R21|scene|C|X6 fortress refight portal destination loading|Enter an authored refight portal with the partner distant; require actual destination load before safe passenger return and release.
R22|scene|I|Door passenger landing geometry|Cross a real X6 boss door with a distant partner; inspect both full foot boxes, native floor collision and independent movement after release.
R23|combat|U|Native homing enemy attack analogue unidentified|Map an original homing producer and eligible-target predicate; make only the guest eligible and retain trajectory plus native contact.
R24|combat|U|Native capture/stun attack analogue unidentified|Identify an original restraining attack, let it hit the guest and observe native release without Select or lifecycle-result writes.
R25|lifecycle|I|Safe stage/rejoin/refight landing|Exercise native arrivals beside authored edges using actual collision boxes; preserve resources and avoid checkpoint reload on voluntary rejoin.
R26|diagnostics|I|Default accepted-input recording and replay|The baseline RAM mailbox is not a recorder; qualify default-on files containing both accepted pads, starting settings/cards and exact-build replay.
F1|netplay|I|Host/Join X6 startup|Retain both launcher states, committed mod plan and first world frames; distinguish native white loading frames from a stalled or unstarted peer.
F2|scene|C|Guest-first D-1000 trigger|Approach the intro boss normally from a safe prior checkpoint with guest leading; require native boss release and independent controls.
F3|scene|U|Scripted falling boss entrance analogue unidentified|Locate an authored X6 drop admission; let the guest lead and compare native descent, full foot boxes and both health values.
F4|render|I|Death emission during scene admission|Kill the actual scene owner once before release; count native effect creation/expiry and world cadence while the passenger recovers.
F5|scene|I|Either-seat boss initialization|Trigger a genuine X6 arena using each leader separately; require complete native boss activation and guest return, not only an allocated actor.
F6|lifecycle|I|Moving leader during guest arrival|Move the leader through controller input during the partner's native beam-in; verify one finite arrival and retained HP/equipment.
F7|scene|C|Fortress portal arrival above a real platform|Use an authored refight destination with an edge; observe both feet and original collision without directly setting landing or scene-success flags.
F8|scene|I|Partner visibility after boss conversation|Complete an actual boss conversation with a distant living partner; inspect both returned bodies and separately accepted inputs.
F9|assets|I|X6 Alia/boss dialogue shared palettes|Let Zero own a native dialogue scene; compare textbox/font colors with original references and verify subsequent gameplay palette restoration.
F10|menu|I|Native pause texture restoration|Open/resume each character menu in a live room; inspect final composed bodies, shared scenery, palettes and subsequent native attacks.
F11|lifecycle|U|Vehicle death beam cleanup analogue unidentified|Find a native X6 mounted entrance/death sequence first; require finite beam retirement and surviving or retried rider control.
F12|assets|I|Zero dash-trail color ownership|Dash Zero while X is still; compare trail native assembly/palette and retirement before and after a menu.
F13|assets|C|Dash resources following boss victory|Perform a native Investigator clear and selector return; dash the partner again and inspect fresh owned trail allocation and art.
F14|render|I|Guest dash after guest-owned door|Complete a guest-led door/event, then dash the guest with primary visible; retain both body packets and distinct effect ownership.
F15|render|U|Ride Chaser dash pose analogue unidentified|Inventory X6 mounted actors before claiming a Chaser counterpart; inspect native pose and acceleration separately if one exists.
F16|render|U|Two-rider vehicle layering analogue unidentified|Find an authored compatible vehicle counterpart; overlap riders and inspect body/vehicle/exhaust priority in the final image.
F17|scene|C|Defeated Investigator portraits after another stage|Earn a real clear, return through native save, enter and leave another stage; retain portrait and campaign-clear consistency.
F18|menu|I|Menu fade body/meter visibility|Capture opening and closing fades for both owners; require both actors whenever the native world draws and proper suppression on frontend pages.
F19|assets|I|Owned dash-exhaust deferred origin|Dash Zero with X stationary, including a reused effect slot; inspect native origin, facing, palette and natural expiry.
F20|lifecycle|I|Paired X6 native arrivals|Observe new-stage, checkpoint and supported portal arrivals; validate native beam animations, safe spacing and ground collision before control.
F21|lifecycle|C|X6 forward-boundary healing policy|Derive the native heal rule per actual stage/route boundary; cross with distinct damaged actors and compare each without imposing X4's refill amount.
F22|solid|U|Partner support on an owned X6 weapon unidentified|Audit native weapon solids before selecting a test; require a real other-character support/jump interaction and native expiry, or documented content absence.
F23|render|I|Primary dash after guest-led door|Use a real guest-led door, dash the primary and inspect both actors/effects while native world time advances once per world update.
F24|scene|U|Shared terrain-toggle controller analogue unidentified|Map an authored X6 switch that changes shared geometry; activate with each leader and observe one native transition plus safe visible partner return.
F25|scene|C|Leading partner at genuine forward section exit|Enumerate an authored stage/route boundary, let the guest cross while primary trails and require original loader continuation with retained roster.
F26|combat|C|Investigator weakness attribution|Use the native guest-owned weakness against an actual Investigator; retain accepted HP change and native reaction with primary weapon context unchanged.
F27|assets|C|Zero elemental techniques and children|Use X6-native elemental techniques with X idle; inspect original child animation/palette, natural expiry and one real target interaction per family.
F28|camera|U|Animated arena scenery controller unidentified|Locate original animated X6 arena scenery; observe its shared phase over stationary-actor world ticks and publication to each eventual view.
F29|solid|I|Moving-solid crush and retry histories|Ride an authored lift with both actors, wipe and retry natively; compare per-seat carry/side contact and genuine ceiling clearance.
F30|netplay|I|Lobby sign-in failure observability|During an actual service failure, retain startup log and exact sign-in error; local delay-peer success cannot qualify external service availability.
F31|menu|C|X6 weapon cycling and private meters|Cycle X through a native special weapon and back to buster; inspect both bodies/meters and an actual subsequent owned shot.
F32|netplay|I|Lobby-to-X6 game handoff|Start one real same-build Host/Join session; retain both readiness/handshake states and first matching gameplay admission.
F33|diagnostics|I|Current-build co-op save/load and rewind|Use actual mapped hotkeys to save/load and rewind both actors, resources, private effects and input ownership; reject malformed states without migrating old builds.
F34|scene|U|Moving-surface transfer analogue unidentified|Find a native transfer whose destination is a moving surface; inspect transient body/camera/solid histories instead of testing an ordinary fixed door.
F35|solid|U|Closing shaft gate analogue unidentified|Map native X6 gate geometry; place one living partner below/inside and verify no closure until their actual collision box clears.
F36|solid|I|Actor and pickup feet on moving supports|Place each actor and a native pickup on the same authored support; compare surface position, per-seat contact and pickup carry during motion.
F37|enhancements|C|X6 Ultimate/Black and native armor options|Qualify simultaneous elective X and Zero forms using X6's native art/abilities, unlocks, menu resources and death/retry/current-state restoration.
F38|diagnostics|I|Discoverable recordings across sessions|Record several separate sessions under redirected non-C storage; show the real output location and verify each contains finalized accepted-input data.
F39|assets|I|Launcher rematch allocation lifetime|Repeat activation/rematch using owned runners; track guest memory, texture/packet registrations and readiness without exhausting or retaining stale resources.
F40|netplay|I|Full mod capability-plan serialization|Populate the actual X6 mod/options plan beyond a small sample; require both peers retain every selected capability without truncated START payloads.
F41|scene|C|Intro death before D-1000 exists|Die during genuine pre-boss warning/admission, retry and require one native boss introduction rather than repeated WARNING or missing allocation.
F42|camera|C|Independent-view refusal behavior|After implementing independent views, stress a private render refusal; retain the correct player's camera/meter and explicitly recorded effective mode.
F43|camera|C|Independent-view performance cadence|Measure native world/VBlank cadence and render cost with two actual views; distinguish repeated simulation from presentation overhead on the same route.
F44|scene|C|Alternate-route transition safe floor and bounds|Lead an authored route transition with guest while primary trails; verify camera-bound commit, full-body floor collision and live control after loading.
F45|solid|I|Per-seat solid history after native team retry|Wipe while using a real platform, retry through original code and land both actors again; retain independent contact histories and collision.
F46|solid|C|Guest-led lift admission and follow|Find an authored X6 lift and use guest-only approach; observe its actual activation, carry motion and appropriate camera follow.
F47|scene|C|Alternate-route portal initial Y|Enter an authored Nightmare route portal with guest; inspect its first destination frames, native floor resolution and safe control release.
F48|diagnostics|I|Pre-game logging|Force an isolated invalid lobby setup and retain its visible startup log before native recording exists; preserve the exact initial failure.
F49|assets|C|Charged X projectile while standing on moving terrain|Charge/release on an authored moving solid; retain actual shot travel, hit and retirement without moving the projectile directly.
F50|assets|C|X6 special-weapon art ownership|Exercise every acquired native special-weapon art family; compare original textures/palettes and retirement while the other hero remains visible.
F51|solid|C|Actor mobility on a moving-support upper edge|Jump/move the guest near a native support's top/edge; observe original motion state and carry release without teleporting free.
F52|scene|C|Partner visibility in intro, capsule and route scripts|Exercise separate native intro, Dr Light and alternate-route scripts; retain both living partners through each distinct controller's native release.
F53|scene|C|Guest-owned intro entry crash regression|Cross the original D-1000 admission with the guest first from a qualified intro route; retain crash/watchdog logs and original completion.
F54|scene|C|Opposite-character intro final hit|With each supported roster, let the counterpart deliver the actual D-1000 final hit; require original cleanup and campaign continuation.
F55|enhancements|C|Capsule armor artwork under counterpart control|Acquire a native Blade/Shadow capsule with X in the counterpart seat; verify granted part, body art and actual ability after native reload.
F56|solid|U|Owned weapon repeated-contact analogue unidentified|Locate an actual support-capable X6 weapon before testing guest touch/top contact; require finite native reaction and free movement afterward.
F57|solid|U|Closing-gate eligibility with primary fallen|Identify a real closing gate, kill primary before guest passes and verify the corpse does not keep the native closure permanently open.
F58|camera|I|Second death after survivor play|Kill primary, advance guest safely, then kill guest; retain camera ownership through actual team wipe instead of chasing the old primary corpse.
F59|assets|C|Weapon-effect scanline artifacts|Capture actual native special-effect frames at original scale and final fit; inspect texture upload, UV boundaries and palette independently of position.
F60|lifecycle|U|Enrollment during native mounted entrance unidentified|Identify a genuine X6 mounted entrance, then require the partner to execute its original arrival sequence rather than enrolling after it.
F61|scene|C|Elective Both-player X6 boss doors|Add explicit Either/Both policy; a living present partner must cross the actual admission region, while absent/fallen actors are excluded.
F62|scene|U|X6 elective multi-encounter story analogue unspecified|Inventory Nightmare Zero, High Max and Dynamo story/route prerequisites; define the X6-native elective contract before implementing any replacement encounter sequence.
F63|combat|C|Elective boss HP and cooldown scaling|Map X6 boss HP, phase and weakness contracts first; qualify accepted/rejected mixed hits and fractional carry with default scaling off.
F64|camera|C|Independent-view moving-solid animation|With actual independent peer views, ride a native moving solid and prove both see the same original-once platform animation phase.
F65|camera|C|Private arrival meters and X6 armor movement|After private views exist, inspect arrival mode/meters and native special armor movement without switching another actor's camera ownership.
F66|camera|C|Distant boss and owned attack draw eligibility|Separate actual views around a native boss; compare boss draw eligibility and its shots in world space rather than screen-space wrapping.
F67|diagnostics|C|Player-facing X6 co-op documentation|Document actual controls, supported modes and limitations with fresh final-build captures and the repository's applicable license.
F68|render|C|Distant world actor wrapping|After split/private rendering exists, separate actors well beyond one pane and verify a distant hero never wraps into the other's composed image.
F69|scene|C|Guest final hit and native frontend owner|Let guest defeat an Investigator and continue through original rewards/save/selector; primary retains frontend authority without losing native progression.
F70|diagnostics|I|Disabled recorder after state load|Disable diagnostics, load a valid current-build state and verify no recording folder or incomplete stream is created by the observer.
F71|assets|C|X6 armor palette under guest ownership|Equip genuine X armor with X in the guest seat; compare body and effect colors with original character references across stage changes.
F72|combat|U|Capture ownership during target change unidentified|Locate an original X6 hold/capture attack; capture one hero, change the boss's eligible target and verify damage/release stays on the captured actor.
F73|lifecycle|I|Living primary departure while guest keeps world|Complete the primary's native outgoing transport while guest remains active; require unchanged checkpoint/world progress and eventual independent controls without team reload.
F74|scene|C|Distant guest-led next-section paired arrival|Use a real authored forward boundary with primary outside the trigger; require both appropriate native arrivals and retained personal resources.
F75|lifecycle|U|Network mounted entrance analogue unidentified|Locate a native X6 vehicle arrival first; both peers must execute the partner's original mounted animation, not a copied idle pose.
F76|menu|C|Discoverable co-op options in recomp-ui|Expose elective door/balance/forms options under clear X6 co-op labels; verify real frontend controls and effective values after launcher start.
F77|scene|U|Breakable midboss admission gate unidentified|Find an authored destructible admission gate; break it with guest leading and require original controller/camera commitment before traversal.
F78|camera|C|Scenery publication after guest-led route change|Enter a real alternate route with guest progressing; compare original scenery animation and renderer state before and after section loading.
F79|scene|C|Both-door traversal without passenger transport|With Both policy enabled, walk both living actors through a real door; neither is withdrawn/rejoined after their actual clearance.
F80|camera|U|Late-fortress native placement eligibility|Map a genuine late Gate-laboratory enemy record; guest advances beyond primary visibility and must cause native spawn plus actual combat.
F81|assets|U|Survivor boss flash-effect analogue unidentified|Locate a shared boss palette-flash initializer; admit it after primary death and compare intended native colors without screen-wide corruption.
F82|combat|C|Zero techniques versus route-specific bosses|Against actual Nightmare Zero/High Max/Dynamo where native rules permit, prove Zero's attacks retain native damage/reaction admission and prerequisites.
F83|scene|C|Consecutive X6 fortress door ownership|Cross two original fortress doors in one run using alternating leaders; inspect retained camera bounds, safe partner return and controls in Unified mode.
F84|assets|C|Route-specific boss native asset identity|Admit Nightmare Zero/High Max/Dynamo under each supported roster; compare their original actor resources, not campaign-character art.
F85|scene|C|Complete alternate-route boss initialization|Trigger the native route boss after real prerequisites; require original state/HP/art/dialogue and a playable fight rather than allocation alone.
F86|lifecycle|C|Fresh Gate-laboratory entry roster reset|Enter a genuine next fortress level after one actor previously fell; verify native fresh-stage roster policy rather than carrying a stale corpse.
F87|assets|C|Alternate-route opponent art under reversed roster|Reverse X/Zero seats, then initialize an original route-specific boss; compare resource identity and visible art against its native solo reference.
F88|solid|U|Guest-survivor scripted shaft analogue unidentified|Locate an authored shaft trigger with hazards/solids; traverse as guest survivor and verify no singleton carry lock or false immobilization.
F89|camera|C|Boss-room terrain after original door|After a native Investigator door, traverse the intended arena width; inspect collision and camera bounds to detect artificial terrain walls.
F90|scene|C|Shared living-actor victory poses|Land the final hit with each character in turn; both living actors perform their native victory once before original departure/return.
F91|scene|C|Both-door commit before following story scene|Use a door immediately followed by dialogue; require both-player crossing/camera commitment before native scene admission, without early passenger transport.
F92|solid|C|X6 Ride Armor ownership and dismount|Mount each eligible character using native X6 rules; exercise manual dismount while comparing partner pose/resources and safe original feet.
F93|lifecycle|U|Mounted entrance timing analogue unidentified|Identify a native X6 vehicle entrance and measure authored travel/world ticks against a co-op-off reference; retain independent animation identity.
F94|camera|C|Independent network background restoration|After private views exist, separate peers in a native animated arena and compare shared layer/atlas state before and after each render.
F95|camera|C|X6 shared scenery atlas and origin|Exercise an authored scrolling or wrapping scene; inspect native layer origins, texture ownership and composed backgrounds while both actors remain visible.
F96|solid|U|Shared terrain-switch partner safety unidentified|Map a native geometry-toggle region; keep partner inside it while primary activates and require native safe collision or deferred transition.
F97|scene|C|Both-player midboss handoff|Cross a native midboss entrance together under Both policy; after actual clearance its scene handoff must not rewarp either actor.
F98|render|C|Ride Armor rider priority|Mount in genuine X6 Ride Armor and overlap terrain/partner; inspect final body/vehicle layering separately from correct coordinates.
F99|combat|C|Shared versus per-seat boss cooldown options|Implement the elective X6 cooldown policy with exact effective values; qualify simultaneous and alternating accepted attacks without cross-seat immunity leakage.
F100|solid|C|Forced Ride Armor dismount near tight geometry|Trigger original forced ejection with partner returning nearby; verify full collision boxes and native landing avoid walls/ceilings without relocating the result.
F101|scene|C|Second Both-door presence in independent netplay|Use two original doors in one peer session; both placements render/admit under private windows and retain the selected Both policy.
F102|camera|I|Guest-led Unified scenery controller|Advance guest while primary lags in baseline midpoint view; verify original shared scenery clocks/uploads remain active and correctly positioned.
F103|scene|I|Owner death while passenger is already arriving|Kill actual scene owner during partner beam-in; require native passenger completion, released controls and survivor ownership without resetting the checkpoint.
F104|solid|C|Native slippery surface physics|Locate an original X6 slippery surface and compare acceleration/friction for both heroes under identical native contact conditions.
F105|camera|C|Lift-specific private vertical camera commands|After private views exist, ride a genuine lift with guest progressing; inspect authored vertical current/target limits and follow through native lift motion.
F106|lifecycle|C|Fallen teammate at actual forward section boundary|Cross an authored forward boundary with one actor fallen; derive X6 native recovery policy and verify its correct application to both seats.
F107|camera|U|Special placement-subtype admission unidentified|Inventory a native X6 special enemy subtype/placement and require guest-only approach to admit its real initialized actor and interaction.
F108|camera|U|Breakable exit scenery cleanup analogue unidentified|Locate an actual breakable forward exit, traverse with guest and compare destination scenery/camera state after original cleanup.
F109|camera|U|Delayed or script-emitted enemy producer unidentified|Trace an original X6 emitter separately from static placement; guest-first progression must produce the native delayed child and interaction.
F110|pickup|I|Delayed health pickup camera ownership|Collect large health with guest while primary is stationary; retain collector HP and actual camera ownership throughout native delayed healing.
F111|solid|U|Temporary platform admission analogue unidentified|Map a native temporary support's placement predicate, then make only guest eligible and require actual spawn/contact without seeding its state.
F112|solid|U|Temporary support expiry after primary death unidentified|Find the same native support's real lifetime driver; kill primary after spawn and require native expiry while guest remains active.
F113|camera|U|Shared weather atlas publication analogue unidentified|Identify original X6 weather sprites/refresh metadata; compare both future views with both alive and after primary death.
F114|scene|C|Both-door auto-walk and camera commitment|Walk one actor left/right while a real Both door waits; verify admission, camera limits and terrain handling without trapping either participant.
F115|scene|U|Distant-partner water ripple analogue unidentified|Identify native X6 water-entry/ripple producer and make primary distant; require guest's genuine surface crossing to emit visible correctly owned effects.
F116|camera|C|Private cameras while Both doors wait|At each of two real Both doors, leave one actor outside and inspect independent views throughout native opening, waiting and final traversal.
F117|combat|C|Counterpart-specific route boss reaction|Map an original route boss reaction that differs by valid attack family; confirm X attacks cause native knockback/reaction when X6 rules allow.
F118|combat|U|Secondary boss weak-point analogue unidentified|Locate an X6 secondary damageable child/weak point; prove guest attacks reach its native lookup and accepted damage independently of main-body hits.
F119|camera|U|Enemy initial facing with nearby off-camera primary|Map an actual spawn initializer; approach with guest while primary is nearby but ineligible/off-camera and inspect initial facing plus native interaction.
F120|assets|C|Survivor scenery palette publication|After primary death, continue through an original palette-animated background; compare advancing native controller and actual upload to the displayed view.
F121|camera|C|Survivor scrolling background publication|Continue as guest through original scrolling scenery after primary falls; retain layer motion/wrap and safe camera control through real world updates.
F122|scene|C|Guest admission of fortress refight portals|Approach an actual Gate-laboratory refight portal with guest only; require native destination and released controls with correct shared progress.
F123|scene|C|Elective Both-player refight portals|Apply the explicit Both policy to genuine fortress refight portals; wait for both eligible living actors and ignore absent/fallen partners.
F124|scene|C|Refight native arrival trigger position|Enter an authored X6 refight portal and observe arena admission without a corrective step/teleport; compare intended original feet and trigger bounds.
F125|combat|C|P2 weakness reaction family A|Select a source-qualified Investigator weakness with distinct reaction A; retain native accepted damage, owner identity, reaction and recovery.
F126|combat|U|Native boss grab release analogue unidentified|Locate an original X6 grabbing attack; capture primary, make guest the next eligible target and require original release without guest death.
F127|combat|U|Vehicle-associated boss weakness analogue unidentified|Inventory X6 vehicle/boss content before mapping; a regular Investigator weakness cannot establish a vehicle-stage-specific ownership path.
F128|scene|C|Primary remains after guest final hit|Let guest land a native Investigator kill while primary remains alive; primary must not be withdrawn as a passenger before shared native victory.
F129|combat|C|Repeated native weakness contacts|Use a native X6 weakness with repeated contact opportunities; record accepted/rejected hit IDs, damage and natural reaction recovery separately.
F130|combat|C|Persistent projectile weakness tokens|Hit a real Investigator using a persistent native weapon; verify duplicate suppression per projectile/seat and fresh later contact without stale vetoes.
F131|combat|C|P2 weakness reaction family B|Select a second source-qualified X6 weakness family with distinct native reaction; prove guest damage and original recovery without borrowing family-A evidence.
F132|combat|C|Zero ground combo on an Investigator|Perform actual native consecutive Zero slashes on a source-qualified boss; retain accepted hit timing and native immunity between combo stages.
F133|render|I|Full death animation and effect retirement|Kill both characters separately during native motion; inspect fatal body art and all effects until their original finite retirement, with survivor control.
F134|scene|U|Vehicle-boss victory passenger analogue unidentified|Identify a genuine X6 vehicle-associated boss cleanup or retain unknown; ordinary boss victory cannot close its mounted-state obligation.
F135|combat|U|Wall/phase-specific weakness analogue unidentified|Map an original X6 boss's valid attached/wall phase and weakness overlap; observe that exact native reaction before using general weakness evidence.
F136|scene|C|Final-room intro after death and Continue|Reach final encounter natively after actual team retry and literal Game Over/Continue; require necessary original intro, boss activation and both controls.
F137|menu|C|Pause while a Both boss door waits|Open a personal menu while one actor waits at a real Both door; preserve native admissibility, owning input and subsequent crossing.
F138|combat|C|First final-encounter weakness contract|Identify the native Sigma phase weakness/prerequisites, use the guest-owned valid attack and retain accepted damage/reaction without phase writes.
F139|combat|C|Zero combo timing in final encounter|Use native Zero multi-hit attacks against a qualified final phase; retain every accepted hit, combo stage, immunity and original recovery.
F140|combat|U|Final boss special-attack targeting analogue unidentified|Trace a native final-boss special targeting path separately from ordinary AI; make guest the sole eligible target and inspect its real trajectory/contact.
F141|scene|C|First final-phase native hold without rewarp|Defeat the first final body through an actual accepted hit; retain both actors across original death/intro holds without passenger beam cycles.
F142|scene|C|Later final-phase roster and controls|Continue the genuine final transition into the later body; inspect native boss release, both hero visibility and independently accepted movement.
F143|diagnostics|I|Recording cost and stream completeness|Measure recorder overhead with both accepted pads during a real session; finalize and replay all rows without hidden drops or synchronous per-input stalls.
F144|render|I|Heavy-scene HUD/scenery integrity|Run an actual effect-heavy X6 encounter and owned pause; inspect life bars, unrelated scenery and render restoration in final composed images.
F145|solid|U|Gate clearance with transient missing foot box unidentified|Find a closing gate and cross with one living actor temporarily lacking a contact box; keep the gate safe until actual partner clearance.
F146|solid|C|Lift operation with guest sole survivor|Kill primary before an authored lift activates; guest must trigger and ride its native controller with valid contact/camera behavior.
F147|scene|I|Portal admission during voluntary departure|Start an actual withdrawal as the partner enters a genuine portal; require finite native arrival/lifecycle settlement and retained controls.
F148|scene|C|Ride Armor admission into a boss arena|Enter an eligible native boss scene mounted; preserve vehicle/rider ownership and visible partner after original scene release without destroying armor as a workaround.
F149|enhancements|C|X6 armor movement child effects|Use genuine Falcon/Blade/Shadow movement effects with X in each seat; compare native flame/trail art, palette, allocation and expiry.
F150|menu|C|Native X6 weapon icon palettes|Open X's actual weapon menu in each seat after stage changes; compare selected/unselected icon palettes and subsequent native weapon use.
F151|scene|U|Elective paired X6 story staging unspecified|Inventory original Alia/Gate/Zero scene identities and eligibility; define per-scene paired staging without changing native story prerequisites or claiming generic dialogue coverage.
F152|combat|C|Zero aerial attacks with private cooldowns|Under elective per-seat balance, compare native accepted aerial follow-ups and exact immunity against shared-policy timing.
F153|combat|C|Zero finisher followed by fresh combo|Use an original grounded combo finisher then a genuine fresh slash under per-seat cooldowns; retain native owner/timing and accepted boss damage.
F154|scene|C|Dr Light capsule dialogue identity|Enter a native Blade/Shadow capsule under each X seat; require original Dr Light text/resources and native part grant rather than unrelated route/story dialogue.
F155|combat|C|Simultaneous elemental weakness children|Have both eligible heroes attack during a source-qualified weakness window; retain child ownership, accepted hits and stable native control flow through recovery.
F156|scene|C|Refight return anchor against real collision|Complete a native fortress refight/return with separated partners; inspect full collision boxes and both feet against authored walls before control release.
F157|combat|C|Fresh Zero slash after prior hit token|Finish one actual Zero attack, begin a distinct native follow-up and require proper accepted/rejected result without stale pose/duplicate suppression.
F158|assets|C|Distant-view local explosion flash isolation|With actual private views, trigger an original local explosion near one hero; retain palette effects only where native proximity/visibility qualifies.
F159|solid|U|Later temporary-platform subtype unidentified|Inventory a distinct later native temporary-support subtype and make only guest eligible; require its own original admission rather than reusing the first subtype.
F160|solid|U|Contact-driven temporary support collapse unidentified|Locate a native contact-triggered collapse and touch it with guest only; require its original collapse timing, not an invented lifetime timer.
F161|assets|U|Later-section enemy asset admission analogue unidentified|Map a genuine later-area X6 spawn with guest progressing; compare native sprite/texture identity after section load and actual enemy interaction.
F162|camera|U|Native field-freeze camera effect unidentified|Find an original global field effect with finite freeze; while views are separated retain each camera and proper original shared timing.
F163|camera|U|Native enemy retirement/re-entry policy unidentified|Source-map one enemy's spawn/retire/respawn eligibility; admit by guest, retire natively and bring primary later without forcing a respawn not promised by X6.
F164|scene|C|Second Both door without retired passenger state|Cross consecutive real boss doors under Both policy; verify second traversal does not restart the first door's old passenger phase.
F165|scene|C|Guest Nightmare-route portal eligibility|Use an actual alternate-route portal with guest first; retain native eligibility and one finite arrival rather than changing scene flags to complete it.
F166|scene|C|Midboss cleanup and forward commitment|Defeat an actual X6 midboss through native combat, then walk both actors across its real forward door/collision boundary with original progress.
F167|scene|C|Capsule-owner death and living partner landing|During a genuine capsule sequence, kill the owning hero at an admissible point; require surviving partner release onto real safe terrain.
F168|solid|U|Native falling-object admission unidentified|Map an authored X6 falling controller and its real trigger; guest crosses while primary stays out, observing native fall/collision and retirement.
F169|camera|C|Vertical lift survivor limits|Continue a native vertical lift route as guest after primary death; inspect authored camera landing/current/target bounds through native motion.
F170|camera|I|First-death private render-state recovery|Capture native first death/retry and subsequent movement at distinct terrain; compare restored camera/map/texture state and final composed scenery.
F171|combat|U|Finite environmental freeze retirement unidentified|Locate an original X6 freeze-field controller and observe its real end; prove guest targeting does not retain timer/work after the effect retires.
F172|render|U|Shared character-assessment targeting visual unidentified|Find a native X6 targeting/assessment visual if present; derive whether one or both eligible heroes should be represented before testing art/ownership.
F173|camera|C|Optional local side-by-side 4:3 panes|Implement elective independent local 4:3 views in an 8:3 window; verify actual pane aspect, separate follow and original world-once updates.
F174|assets|C|X6 deferred targeting/beam weapon update|Choose a source-qualified native beam/targeting weapon; allocate with X in guest seat and retain actual travel/animation, owner context and native expiry.
F175|camera|C|Native-once scroll/atlas publication|Choose distinct native scrolling and atlas-animated X6 scenes; prove both eventual private views retain advancing shared updates rather than render snapshots freezing them.
F176|scene|C|Intro rescue/gate effect sequence ending|Follow an actual intro gate/rescue producer from native admission to retirement; require one finite explosion/event cycle and released scene state.
F177|camera|C|Local 8:3 canvas during shared-frame fallback|With local split selected, enter a native shared scene and induce a supported fallback; retain the chosen output canvas and correct effective mode.
F178|camera|C|Distant X6 terrain beyond retail ring|After private views exist, separate actors across actual authored terrain and move only one; inspect stable independent map rendering beyond the singleton tile ring.
F179|menu|I|Character-owned X6 native menus in both rosters|Support X/Zero in either seat; open each own menu, inspect native equipment/art, reject other-seat resume and exercise the selected native ability.
F180|pickup|C|Elective private Sub Tank energy|Keep native shared acquisition/card progression; with optional separate energy, heal each seat independently then validate native reload and current-build snapshots.
F181|combat|C|Elective character-specific fractional boss damage|Adapt X6's actual damage contract before optional Zero reduction; qualify mixed accepted/rejected hits, fractional carry and unchanged native weakness identity.
F182|render|U|Native laser geometry view isolation unidentified|Locate an authored X6 beam/laser encounter and separate views; inspect correct world-space geometry/collision without projection into the distant partner's pane.
F183|solid|U|Gate closure with partner inside shaft unidentified|Identify an original closing hatch, hold one living actor inside and move the other beyond; require clearance before native closure.
F184|scene|C|Guest-led midboss initial camera|Approach an actual X6 midboss with primary distant; inspect first arena/camera state and initial native combat separately from eventual defeat/exit.
F185|camera|C|Lift vertical bounds during one actor's jump|On an authored lift, jump one hero while the other rides; retain each view's native vertical bounds and valid feet through actual lift motion.
F186|solid|U|Survivor destructible-platform controller unidentified|Find an original destructible moving-support mechanism, kill primary first and require guest's native attack/trigger to change world collision and permit traversal.
F187|scene|C|Post-midboss collision/checkpoint continuation|Defeat a genuine X6 midboss and walk guest across its original forward boundary; distinguish in-area checkpoint progression from a separate section loader.
F188|solid|U|Independent vehicle acceleration analogue unidentified|Inventory native X6 two-rider vehicle eligibility first; dash guest with primary neutral and compare each owned velocity/position over identical world ticks.
F189|camera|C|Scrolling backgrounds and native wrap|Observe actual X6 native panorama wrap with both actors healthy and separated; compare phase/origins and composed motion without rolling back shared writes.
F190|scene|U|Scripted bomb-event producer unidentified|Find an authored X6 bomb/script controller and its real threshold; guest admits it with primary behind and one original event ending must occur.
F191|scene|C|Guest-only native midboss initialization|Map a real X6 midboss placement/admission, approach only with guest and require complete playable initialization plus a real native interaction.
F192|solid|U|Shared vehicle/platform stop command unidentified|Map an original X6 moving controller with a native stop phase; guest triggers it and both observe one world stop with correct cameras/carry.
F193|solid|U|Distinct stationary platform start command unidentified|Find a separate native stationary support/start trigger; guest admits original motion with primary behind, retaining owner and actual carry.
F194|scene|U|Camera-relative fireball/shake emitter unidentified|Identify an original X6 camera-relative environmental emitter and its start/end rules; guest leads while primary stays behind without seeding emission state.
F195|scene|U|Separate platform-hazard emitter unidentified|Map a different authored X6 platform hazard, then observe guest-triggered original spawn, actual collision and native retirement independently of F194.
F196|camera|C|Intro geometry handoff on different floors|Let guest trigger a native intro geometry event while primary remains on another safe slope/floor; inspect each appropriate camera Y after completion.
F197|render|C|Nearby original explosion in both views|With two actual views nearby, trigger one native explosion and inspect shared world effect/damage plus each view's local shake and visibility.
F198|camera|C|Nearby camera shake from native explosion|Retain camera offsets through an original nearby explosion for each view; visible particles alone cannot establish correct native screen shake.
F199|solid|U|Subtype-specific breakable/falling trigger unidentified|Inventory actual X6 falling/breakable subtypes, then guest crosses one specific native predicate; retain original state transition without forcing its trigger.
F200|scene|U|Environmental script-emitted enemy group unidentified|Trace a genuine X6 environmental event that emits an enemy group; guest-first progression must preserve original group timing and interaction, distinct from static placements.
F201|solid|I|Native signed solid-contact release|Find an actual X6 support release producer before asserting it; preserve signed per-seat carry commands and observe original airborne/landing state without teleporting free.
F202|solid|U|Height-triggered closing-wall controller unidentified|Map an authored X6 Y/camera predicate and resulting real wall collision; guest descends while primary stays above and both retain native control.
F203|assets|C|Boss shared effect colors initialized after primary death|Kill primary before a source-qualified boss color/effect initializer; admit with guest and compare original source colors, working palettes and actual upload.
F204|solid|C|Moving-support world cadence with two actors|Measure native world/VBlank advancement on a real moving-platform stretch with both actors and normal presentation; retain route and timing evidence.
F205|diagnostics|I|Effective build/play/camera mode in recordings|Record exact release/build and effective initial co-op/view/settings plus transitions; saved preferences cannot stand in for actual runtime mode.
F206|camera|C|Refight camera follow after native intro release|Enter an original fortress refight, then move both actors after release; inspect authored current/target bounds and actual follow, not arrival positions alone.
F207|combat|C|Native weakness reaction must eventually recover|During a real X6 weakness encounter keep firing through its reaction; record accepted/rejected damage, finite native stun and resumed boss motion.
F208|menu|I|Pause ownership after Quit and re-entry|Perform native primary Quit confirmations and real New Game/Continue; guest opens/resumes its own menu, rejects other-seat resume and moves independently afterward.
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=30).stdout


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def parse_table(data: bytes) -> list[dict]:
    """Read only the eight-column detailed comparison table, not milestones."""
    rows = []
    in_table = False
    for line in data.decode("utf-8").splitlines():
        if line.startswith("| Source / report | X4 state | Original symptom |"):
            if in_table:
                raise ValueError("duplicate detailed comparison table")
            in_table = True
            continue
        if not in_table or line.startswith("| ---"):
            continue
        if not line.startswith("| COOP_"):
            if rows and line.strip():
                # Additional prose is fine; subsequent report rows still match.
                continue
            continue
        cells = [part.strip() for part in re.split(r"(?<!\\)\|", line)[1:-1]]
        if len(cells) != 8:
            raise ValueError(f"expected eight columns: {line[:100]}")
        match = re.fullmatch(r"(COOP_PLAYTEST_REGRESSIONS\.md|COOP_PLAYTEST_FEEDBACK_20261010\.md):(\d+) #(\d+)", cells[0])
        if not match:
            raise ValueError(f"unexpected source/report {cells[0]}")
        report, number = match.group(1), int(match.group(3))
        row_id = ("R" if report == "COOP_PLAYTEST_REGRESSIONS.md" else "F") + str(number)
        rows.append({
            "id": row_id,
            "x4": dict(zip(("source_report", "state", "original_symptom", "failure_class"), cells[:4])),
            "x5_snapshot": dict(zip(("counterpart_check", "burndown", "status", "evidence_limits"), cells[4:])),
            "frozen_row_sha256": sha256(line.encode("utf-8")),
        })
    ids = [row["id"] for row in rows]
    if ids != EXPECTED_IDS:
        raise ValueError(f"inventory must contain exactly R1–R26 then F1–F208; got {len(ids)} rows")
    return rows


def mappings() -> dict:
    result = {}
    states = {"I": "identified_subsystem", "C": "candidate_native_scenario", "U": "unknown_native_analogue"}
    for line in MAPPINGS.strip().splitlines():
        row_id, group, state, analogue, check = line.split("|", 4)
        if row_id in result:
            raise ValueError(f"duplicate mapping {row_id}")
        result[row_id] = {
            "workstream": group, "mapping_state": states[state],
            "analogue": analogue, "bounded_check": check,
            "baseline_anchors": ANCHORS[group],
        }
    if set(result) != set(EXPECTED_IDS):
        raise ValueError("mapping omission or invented ID")
    return result


def frozen_sources(source_repo: Path, root: Path) -> tuple[dict, list[dict]]:
    files = []
    contents = {}
    for path, expected_blob in SOURCE_BLOBS.items():
        data = git(source_repo, "show", f"{X5_COMMIT}:{path}")
        blob = git(source_repo, "rev-parse", f"{X5_COMMIT}:{path}").decode().strip()
        if blob != expected_blob:
            raise ValueError(f"frozen X5 blob drift: {path}")
        contents[path] = data
        files.append({"path": path, "git_blob": blob, "bytes": len(data), "sha256": sha256(data)})
    x4 = json.loads(contents[MANIFEST_PATH])
    if x4["commit"] != X4_COMMIT or len(x4["files"]) != 15:
        raise ValueError("unexpected frozen X4 reference identity")
    x6_commit = git(root, "rev-parse", X6_COMMIT).decode().strip()
    baseline = []
    for path in ("src/mods/mmx6_coop_plugin.c", "src/mods/mmx6_coop_lifecycle.c",
                 "src/mods/mmx6_general_foundations_armor.inc", "src/mods/mmx6_zero_techniques_resolver.cpp",
                 "tools/test_coop_netplay_runtime.py"):
        data = git(root, "show", f"{x6_commit}:{path}")
        baseline.append({"path": path, "git_blob": git(root, "rev-parse", f"{x6_commit}:{path}").decode().strip(),
                         "bytes": len(data), "sha256": sha256(data)})
    source_manifest = {
        "schema_version": 1,
        "policy": "Committed source objects only; local source paths are discovery hints, not evidence. No X4/X5 pass transfers to X6.",
        "x4": x4,
        "x5": {"commit": X5_COMMIT, "repository_hint": str(X5_REPO), "files": files},
        "x6_baseline": {"commit": x6_commit, "files": baseline},
    }
    return source_manifest, parse_table(contents[TABLE_PATH])


def initial_ledger(manifest: dict, rows: list[dict]) -> dict:
    mapping = mappings()
    return {
        "schema_version": 1,
        "title": "X6 complete X4 comparison inventory",
        "reference": {"x4_commit": X4_COMMIT, "x5_commit": X5_COMMIT,
                      "x6_baseline_commit": manifest["x6_baseline"]["commit"], "comparison_count": 234},
        "policy": {
            "status_values": ["unverified", "failed", "passed", "inapplicable"],
            "initial_status": "unverified",
            "modes": ["local", "netplay"],
            "qualification": "Each required mode needs its own passed evidence on the exact candidate. Source review, screenshots alone, baseline tests and inherited X5 passes cannot close a gameplay row.",
            "inapplicable": "Requires documented native X6 content evidence; unidentified analogues remain unverified.",
            "evidence": "Record candidate commit/build/settings, native action/outcome, artifact path and SHA256, limitations and disclosed bypasses. Keep failed attempts.",
            "save_states": "Build-specific disposable snapshots; qualify current-build save/load/rewind. Preserve native card progress; no old-state conversion required.",
        },
        "comparisons": [dict(row, x6=dict(mapping[row["id"]], status="unverified",
                            required_modes=["local", "netplay"], mode_status={"local": "unverified", "netplay": "unverified"},
                            evidence=[], limitations="No X6 runtime qualification performed by this inventory import.")) for row in rows],
    }


def validate_ledger(ledger: dict, expected: dict, artifact_root: Path | None = None) -> None:
    if ledger.get("schema_version") != 1 or ledger.get("reference") != expected["reference"]:
        raise ValueError("ledger reference/schema drift")
    rows = ledger.get("comparisons", [])
    ids = [row.get("id") for row in rows]
    if ids != EXPECTED_IDS:
        raise ValueError("ledger omission, duplicate, order change or invented comparison")
    statuses = {"unverified", "passed", "failed", "inapplicable"}
    artifact_hashes = {}
    for row, original in zip(rows, expected["comparisons"]):
        row_id = row["id"]
        for key in ("x4", "x5_snapshot", "frozen_row_sha256"):
            if row.get(key) != original[key]:
                raise ValueError(f"{row_id}: frozen {key} source drift")
        x6 = row.get("x6", {})
        for key in ("workstream", "mapping_state", "analogue", "bounded_check", "baseline_anchors"):
            if not x6.get(key):
                raise ValueError(f"{row_id}: missing individual X6 {key}")
        if x6["mapping_state"] not in {"identified_subsystem", "candidate_native_scenario", "unknown_native_analogue"}:
            raise ValueError(f"{row_id}: unknown mapping state")
        status = x6.get("status")
        if status not in statuses or x6.get("required_modes") != ["local", "netplay"]:
            raise ValueError(f"{row_id}: invalid status/mode contract")
        mode_status = x6.get("mode_status", {})
        if set(mode_status) != {"local", "netplay"} or any(value not in statuses for value in mode_status.values()):
            raise ValueError(f"{row_id}: invalid per-mode status")
        evidence = x6.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValueError(f"{row_id}: evidence must be a list")
        for item in evidence:
            required = ("mode", "result", "candidate", "build_identity", "settings", "action", "outcome", "artifacts", "limits", "bypasses")
            if not isinstance(item, dict) or any(key not in item for key in required):
                raise ValueError(f"{row_id}: incomplete evidence receipt")
            if item["mode"] not in mode_status or item["result"] not in statuses:
                raise ValueError(f"{row_id}: invalid evidence mode/result")
            if not re.fullmatch(r"[0-9a-f]{40}", item["candidate"]):
                raise ValueError(f"{row_id}: evidence needs exact 40-character candidate commit")
            if any(not item[key] for key in ("build_identity", "settings", "action", "outcome", "artifacts")):
                raise ValueError(f"{row_id}: evidence lacks native result/build/settings/artifact")
            if not isinstance(item["artifacts"], list) or any(
                not isinstance(a, dict) or not a.get("path") or not re.fullmatch(r"[0-9a-f]{64}", a.get("sha256", ""))
                for a in item["artifacts"]
            ):
                raise ValueError(f"{row_id}: invalid artifact identity")
            if artifact_root is not None:
                for artifact in item["artifacts"]:
                    path = Path(artifact["path"])
                    if ntpath.splitdrive(str(path))[0].lower() == "c:":
                        raise ValueError(f"{row_id}: generated evidence must not live on C:")
                    if not path.is_absolute():
                        path = artifact_root / path
                    path = path.resolve()
                    if not path.is_file():
                        raise ValueError(f"{row_id}: evidence artifact does not exist: {path}")
                    if path not in artifact_hashes:
                        digest = hashlib.sha256()
                        with path.open("rb") as stream:
                            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                                digest.update(chunk)
                        artifact_hashes[path] = digest.hexdigest()
                    if artifact_hashes[path] != artifact["sha256"]:
                        raise ValueError(f"{row_id}: evidence artifact SHA256 mismatch: {path}")
        for mode, result in mode_status.items():
            if result in {"passed", "failed"} and not any(item["mode"] == mode and item["result"] == result for item in evidence):
                raise ValueError(f"{row_id}: {mode} {result} without individual evidence")
        if status == "passed":
            if any(value != "passed" for value in mode_status.values()):
                raise ValueError(f"{row_id}: pass requires independent local and netplay qualification")
            receipts = [item for item in evidence if item["result"] == "passed"]
            candidates = [{item["candidate"] for item in receipts if item["mode"] == mode} for mode in mode_status]
            if not set.intersection(*candidates):
                raise ValueError(f"{row_id}: passed modes need the same exact candidate")
        elif status == "failed" and "failed" not in mode_status.values():
            raise ValueError(f"{row_id}: failed aggregate needs a failed mode")
        elif status == "inapplicable":
            if not x6.get("inapplicability_reason") or not x6.get("native_content_evidence"):
                raise ValueError(f"{row_id}: inapplicable needs a native-content reason and evidence")
            if x6["mapping_state"] == "unknown_native_analogue":
                raise ValueError(f"{row_id}: an unknown analogue cannot be inapplicable")
        if status != "inapplicable" and "inapplicable" in mode_status.values():
            raise ValueError(f"{row_id}: mode inapplicability requires explicit row disposition")


def render_markdown(ledger: dict) -> str:
    rows = ledger["comparisons"]
    counts = Counter(row["x6"]["status"] for row in rows)
    mapping_counts = Counter(row["x6"]["mapping_state"] for row in rows)
    lines = [
        "# X6 frozen X4 comparison inventory", "",
        f"Frozen X4 Playtest42: `{X4_COMMIT}`. Frozen X5 comparison definitions: `{X5_COMMIT}`.",
        "The machine-readable authority is [COOP_PARITY_LEDGER.json](COOP_PARITY_LEDGER.json); this page is its generated review view.",
        "R1–R26 preserve the regression-report IDs; F1–F208 preserve the numbered feedback-report IDs. They are separate namespaces, totaling **234 comparisons**.", "",
        f"X6: **{counts['passed']} passed, {counts['failed']} failed, {counts['unverified']} unverified, {counts['inapplicable']} inapplicable**.",
        f"Mappings: {mapping_counts['identified_subsystem']} inspected subsystems, {mapping_counts['candidate_native_scenario']} candidate native scenarios, {mapping_counts['unknown_native_analogue']} unidentified native analogues.",
        "Identified subsystem means only that the named baseline code exists; candidate scenarios need authored-content confirmation. Neither is a gameplay pass.", "",
        "## Baseline and qualification rules", "",
        "The inspected X6 prototype projects a host-owned Zero context into singleton guest addresses, restores X, and advances the native world once. It has lifecycle, scene/passenger, native menu, pickup/Reploid/Soul, solid-contact and stacked-HUD hooks.",
        "It uses a shared midpoint/tethered view, fixed X-primary/Zero-partner enrollment and a delay-sync profile; opposite seats, independent/split views and full recording/snapshot qualification are work items. No X4/X5 stage IDs, addresses, boss tables or story rules are imported as X6 facts.",
        "Every row starts unverified. Required local and netplay results remain independent and must share an exact candidate before aggregate pass. Baseline smoke scripts and historical X5 passes are investigation leads only.",
        "Unknown mechanics remain unverified; inapplicability requires documented native X6 content evidence. Native card progress remains protected. Current-build state/load/rewind correctness matters; old state compatibility never requires migration.",
        "Each retained receipt identifies candidate/build/settings, native action/outcome, artifact paths and SHA256, limitations and bypasses. The checker verifies receipt structure, candidate/mode coverage and artifact hashes; a reviewer must still establish that the artifacts prove the native behavior. Teleports may position actors; they may not set the success being claimed.", "",
        "Regenerate: `python tools/build_mmx6_coop_reference.py --render`; validate without writing: `python tools/build_mmx6_coop_reference.py --check`. Source reads use committed git objects and make no remote requests.", "",
        "## Detailed comparisons", "",
        "| ID | Frozen X4 source/report | Original symptom | Failure class / risk | X6 counterpart / mapping | X6 bounded check | Local / netplay / aggregate |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    def cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")
    for row in rows:
        x4, x6 = row["x4"], row["x6"]
        values = [row["id"], x4["source_report"], x4["original_symptom"], x4["failure_class"],
                  f"{x6['analogue']} ({x6['mapping_state']})", x6["bounded_check"],
                  " / ".join([x6["mode_status"]["local"], x6["mode_status"]["netplay"], x6["status"]])]
        lines.append("| " + " | ".join(cell(value) for value in values) + " |")
    lines += ["", "The ledger retains all eight frozen X5 table fields verbatim, including original X4 checked/open state and historical X5 evidence/limits. Those historical fields never establish an X6 result.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, default=X5_REPO)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--initialize", action="store_true")
    mode.add_argument("--render", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    manifest, rows = frozen_sources(args.source_repo, args.root)
    expected = initial_ledger(manifest, rows)
    ledger_path = args.root / LEDGER_PATH
    manifest_path = args.root / MANIFEST_PATH
    markdown_path = args.root / TABLE_PATH
    if args.initialize:
        if any(path.exists() for path in (ledger_path, manifest_path, markdown_path)):
            raise ValueError("refusing to overwrite existing inventory; use --render to preserve evidence")
        ledger = expected
        manifest_path.write_bytes(json_bytes(manifest))
        ledger_path.write_bytes(json_bytes(ledger))
    else:
        if json.loads(manifest_path.read_bytes()) != manifest:
            raise ValueError("frozen source manifest drift")
        ledger = json.loads(ledger_path.read_bytes())
    validate_ledger(ledger, expected, artifact_root=args.root)
    markdown = render_markdown(ledger).encode("utf-8")
    if args.check:
        if markdown_path.read_bytes() != markdown:
            raise ValueError("Markdown view differs from authoritative ledger; run --render")
    else:
        markdown_path.write_bytes(markdown)
    print(json.dumps({"comparisons": len(rows), "x6_statuses": dict(Counter(row["x6"]["status"] for row in ledger["comparisons"])),
                      "x5_commit": X5_COMMIT, "source_files": len(manifest["x4"]["files"]), "mode": "check" if args.check else "write"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
