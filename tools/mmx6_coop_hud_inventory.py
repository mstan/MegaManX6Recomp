"""Offline native ammo-HUD observations with an explicit inventory bypass.

Only inventory.prepare writes its audited earned-weapon mailbox. Selection and
energy change through ordinary published input. This is separate from the
untainted HUD observer: the prerequisite invalidates ordered replay evidence.
"""
import hashlib
from pathlib import Path
import struct
import time

import coop_debug as debug
import mmx6_coop_hud_presentation as hud
import mmx6_coop_inventory_state as inventory

require = hud.require
SUCCESS = 'native_ammo_hud_captured_artwork_and_ledger_pending'
AMMO_ADDRESS = 0x800249D4
AMMO_BYTES = 0x2EC
AMMO_SHA = '3797c5955432124e9620ebb9109b91c9fb1ca65d40447d5ff15f12c85ae55bad'
ASPECTS = hud.SIZES[:3]


def load_source(path, original_disc=None):
    source = inventory.load_source(path)
    data = Path(path).read_bytes()
    exe = inventory.content.Executable(data)
    code = data[exe.offset(AMMO_ADDRESS, AMMO_BYTES):exe.offset(AMMO_ADDRESS, AMMO_BYTES)+AMMO_BYTES]
    require(hashlib.sha256(code).hexdigest() == AMMO_SHA, 'Original native ammo-HUD function changed')
    source['ammo_hud'] = dict(address=AMMO_ADDRESS, bytes=AMMO_BYTES, sha256=AMMO_SHA,
        selected_offset=0x93, signed_energy_offset=0xA8, energy_stride=2, capacity_offset=0x14A,
        native_bar=dict(x0=31, x1=34, bottom=80),
        source_instructions={hex(pc): hex(struct.unpack_from('<I', data, exe.offset(pc, 4))[0])
            for pc in (0x800249F8, 0x80024B6C, 0x80024B80, 0x80024B90, 0x80024BA4,
                       0x80024BA8, 0x80024BDC, 0x80024BEC)})
    if original_disc is not None:
        zero = hud.resources.zero_contact.load_zero_overlay(original_disc)
        code = zero[0x254:0x34C]
        require(hashlib.sha256(code).hexdigest() ==
            '3f060d450064603e7794052a2ae1cdbd9d88eb22bfb8661facea8bf8571d52cb',
            'Original Zero Yammar activation changed')
        source['zero_yammar'] = dict(address=0x801EA254, bytes=len(code),
            sha256=hashlib.sha256(code).hexdigest(), selected_weapon=3,
            native_input='held Up and fresh Triangle edge (native held4/edge20h)', option_offset=0xA6,
            limits='Original activation candidate; native selection, spending and presentation must be observed')
    return source


def spend_for_hud(ctx, case):
    """Use separate native selections that can remain visible after spending.

    X weapon1 creates a persistent option; Zero R2 uses a temporary Giga
    selection and fullscreen effect. Neither is a repeatable steady bar probe.
    This route instead observes X weapon2 and Zero's Up+Triangle option; it
    requires their actual results rather than assigning either selection.
    """
    before = case.sample('Before native ammo HUD actions')
    require([p[1] for p in hud.state.private_resources(before)] == [0, 0],
            'Ammo HUD route needs fresh native base selections')
    route = dict(before=before, attempts=[], checks={})
    case.evidence.setdefault('native_inventory_spending', []).append(route)

    def accepted(seat, bits, predicate, label, selection_only=False):
        case.adapter.native_advance(3, label+' consumed neutral before edge')
        anchor = case.sample(label+' input bracket')
        try:
            receipt = ctx['set_input'](seat, bits)
            row = case.wait(lambda r: hud.state.forward(anchor['observation']['tick'], r['observation']['tick']) and
                            predicate(r), label+' actual native result')
        finally:
            ctx['set_input'](seat, 0)
        case.adapter.native_advance(3, label+' consumed neutral after edge')
        after = case.sample(label+' released')
        checks = ownership_checks(anchor, after, seat, selection_only=selection_only)
        route['attempts'].append(dict(seat=seat, pressed=bits, selection_only=selection_only,
            before=anchor, accepted=row, after=after, acknowledgment=receipt, checks=checks, label=label))
        require(all(checks.values()), 'Native ammo HUD action violated private resource ownership')

    accepted(0, 0x800, lambda r:r['observation']['players'][0]['weapon'] == 1,
             'Original X first R1', True)
    accepted(0, 0x800, lambda r:r['observation']['players'][0]['weapon'] == 2,
             'Original X second R1', True)
    accepted(0, 0x1000, lambda r:r['observation']['players'][0]['ammo'][2] < 288,
             'Original X weapon2 Triangle')
    accepted(1, 0x1010, lambda r:r['observation']['players'][1]['weapon'] == 3 and
        r['observation']['players'][1]['ammo'][3] < 288 and bytes.fromhex(r['p2_body_hex'])[0xA6] == 1,
        'Original Zero Up plus Triangle Yammar')
    after = case.sample('After both native selected ammo actions')
    route.update(after=after, checks=inventory.changed_resources(before, after))
    require(all(route['checks'].values()), 'Native HUD ammo actions did not change both actors')
    return after


def selected_resources(row):
    """Read the actual published actor bodies, cross-checking the public fields."""
    result = []
    for seat, name in enumerate(('p1_body_hex', 'p2_body_hex')):
        body = bytes.fromhex(row[name])
        require(len(body) == debug.BODY_BYTES, 'Ammo HUD requires a complete published actor body')
        weapon = body[0x93]
        require(0 <= weapon <= 8, 'Native ammo HUD selected an unsupported weapon')
        ammo = struct.unpack_from('<9h', body, 0xA8)
        capacity = struct.unpack_from('<H', body, 0x14A)[0]
        player = row['observation']['players'][seat]
        require(player['weapon'] == weapon and tuple(player['ammo']) == ammo,
                'Published native actor body and diagnostic ammo disagree')
        require(0 < capacity <= 0x7FFF and all(0 <= value <= capacity for value in ammo[1:]),
                'Selected ammo/capacity outside the native positive energy range')
        result.append(dict(seat=seat, character=player['character'], weapon=weapon,
                           energy=ammo[weapon], capacity=capacity, all_energy=list(ammo)))
    return result


def ownership_checks(before, after, seat, *, selection_only=False):
    old, new = hud.state.private_resources(before), hud.state.private_resources(after)
    checks = dict(other_actor_resources_unchanged=old[seat ^ 1] == new[seat ^ 1],
                  own_hp_unchanged=old[seat][0] == new[seat][0])
    if selection_only:
        checks.update(original_selection_changed=old[seat][1] != new[seat][1],
                      selection_did_not_spend_energy=old[seat][2] == new[seat][2])
    else:
        checks['native_energy_decreased_without_refill'] = (
            all(0 <= b <= a for a, b in zip(old[seat][2], new[seat][2])) and
            any(b < a for a, b in zip(old[seat][2], new[seat][2])))
    return checks


def ammo_regions(path, row, layout):
    """Retain exact native ammo ROIs; presence/difference is not a fill-length pass.

    The original bar is at x31..34 with bottom80. A one-pixel border and the
    full native 64-pixel meter height retain its frame and any empty section.
    Nearest-pixel normalization is only a comparison aid; the PNG stays exact.
    """
    from PIL import Image
    require(layout in ('stacked', 'side_by_side'), 'Unknown ammo HUD layout')
    values = selected_resources(row)
    with Image.open(path) as source:
        image = source.convert('RGB')
    width, height = image.size
    scale = min(width/320, height/240)
    ox, oy = (width-320*scale)/2, (height-240*scale)/2
    result = []
    for seat in (0, 1):
        dx, dy = (0, 0) if not seat else ((0, 104) if layout == 'stacked' else (56, 0))
        native = [30+dx, 15+dy, 35+dx, 81+dy]
        box = [round(ox+native[0]*scale), round(oy+native[1]*scale),
               round(ox+native[2]*scale), round(oy+native[3]*scale)]
        require(0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height,
                'Source-derived ammo ROI is outside the composed drawable')
        pixels = image.crop(box).resize((5, 66), Image.Resampling.NEAREST).tobytes()
        result.append(dict(**values[seat], native_roi=native, drawable_roi=box,
                           native_anchor=[31+dx, 80+dy],
                           normalized_rgb_sha256=hashlib.sha256(pixels).hexdigest(),
                           normalized_rgb_hex=pixels.hex()))
    return dict(image_size=[width, height], viewport=dict(x=ox, y=oy, scale=scale), regions=result,
                measurement_scope='Exact source-derived ammo regions only; native artwork/fill ownership review pending')


def compare_regions(before, after):
    require(before['image_size'] == after['image_size'], 'Ammo image comparison needs the same drawable')
    result = []
    for old, new in zip(before['regions'], after['regions']):
        require(old['seat'] == new['seat'] and old['native_roi'] == new['native_roi'], 'Ammo ROI identity changed')
        a, b = bytes.fromhex(old['normalized_rgb_hex']), bytes.fromhex(new['normalized_rgb_hex'])
        changed = sum(a[i:i+3] != b[i:i+3] for i in range(0, len(a), 3))
        result.append(dict(seat=old['seat'], weapon_before=old['weapon'], weapon_after=new['weapon'],
            energy_before=old['energy'], energy_after=new['energy'], changed_of_330_pixels=changed,
            admission='Observation only; no color/fill extractor or rendered ownership pass'))
    return result


def settle_fixture_idle(ctx, case, timeout):
    """Require living stable actors and clear native script locks.

    Native contact before this fixture may already have changed HP. Keep
    those actual values; the fixture neither refills nor requires maximum HP.
    """
    for seat in (0, 1):
        ctx['set_input'](seat, 0)
    deadline, previous = time.monotonic()+timeout, None
    while time.monotonic() < deadline:
        row = case.sample('Settle living native inventory actors')
        o = row['observation']
        idle = (o['native_mode'] == 10 and o['native_phase'] == 0 and
            not (o['pause_owner'] or o['scene_owner'] or o['failed'] or o['mailbox']) and
            o['ready'] == o['enrolled'] == 1 and not any(o['lifecycle']) and
            all(p['active'] and p['state'] == 1 and p['action'] == 2 and 0 < p['hp'] < 128
                for p in o['players']) and
            all(bytes.fromhex(row[k])[0xCC] == bytes.fromhex(row[k])[0xE0] == 0
                for k in ('p1_body_hex', 'p2_body_hex')))
        if idle and previous is not None:
            delta = (o['tick']-previous['observation']['tick']) & 0xFFFFFFFF
            if 2 <= delta < 0x80000000 and all(
                (a['x_raw'], a['y_raw']) == (b['x_raw'], b['y_raw'])
                for a, b in zip(o['players'], previous['observation']['players'])):
                case.evidence['settled_living_idle'] = row
                return row
        previous = row if idle else None
        case.adapter.transport_window(2)
    raise debug.DebugError('Living native inventory actors did not settle with clear script locks')


def exercise(ctx, *, output, layout, source, timeout=18):
    require(ctx['mode'] == 'local' and ctx['input_path'] == 'published_host', 'Ammo HUD fixture is local only')
    require(layout in ('stacked', 'side_by_side'), 'Unknown ammo HUD layout')
    require('zero_yammar' in source, 'Ammo HUD needs source-bound original Zero option activation')
    output.mkdir(parents=True, exist_ok=False)
    evidence = {}; ctx['report']['ammo_hud_inventory'] = evidence
    adapter = hud.mapped.PublishedAdapter(ctx, evidence, timeout)
    case = hud.state.PrivateStateCase(ctx['request'], output, evidence, timeout=timeout,
                                      adapter=adapter, input_path='published_host')
    adapter.settle_idle = lambda: settle_fixture_idle(ctx, case, timeout)
    window = hud.OwnedWindow(ctx, evidence)
    evidence.update(layout=layout, source=source['ammo_hud'], native_resource_ownership=[],
        ammo_capture_sets=[], extra_attacks=[], limits=[
            'Earned weapons are a prerequisite bypass through the original initializer; acquisition is not qualified.',
            'No HP, ammo, selection, action or completion flags are directly written.',
            'Inventory mailbox taints the default ordered recording; finalized capture and replay are refused.',
            'Source-derived ammo regions and resource changes do not establish rendered fill or portrait ownership.',
            'Local exact-image Windows intro only; netplay, physical devices and other hosts remain separate.'])

    def settle(label):
        anchor = case.sample(label+' start')
        return case.wait(lambda r: hud.state.forward(anchor['observation']['tick'], r['observation']['tick']) and
            r['observation']['native_phase'] == 0 and not r['observation']['pause_owner'] and
            all(p['active'] and p['state'] == 1 and p['action'] == 2 and p['hp'] > 0
                for p in r['observation']['players']), label+' native idle')

    def captures(label):
        group = dict(label=label, captures=[]); evidence['ammo_capture_sets'].append(group)
        for width, height in ASPECTS:
            window.resize(width, height)
            before = case.sample(label+' before capture')
            receipt = debug.capture_present(ctx['clients'][0], output/f'{label}-{width}x{height}.png', request=ctx['request'])
            after = case.sample(label+' after capture')
            video = ctx['request']('video_info')
            measurement = ammo_regions(receipt['path'], after, layout)
            require([r['weapon'] for r in measurement['regions']] == [2, 3],
                    'Native selected ammo identities changed before composed capture')
            from PIL import Image
            with Image.open(receipt['path']) as image:
                require(image.convert('RGB').getbbox() is not None, 'Native composed ammo capture is entirely black')
            require(measurement['image_size'] == [video['drawable_w'], video['drawable_h']],
                    'Ammo capture does not match the actual final drawable')
            require(hud.state.private_resources(before) == hud.state.private_resources(after),
                    'Native resources changed during ammo capture')
            group['captures'].append(dict(**receipt, video=video, native_before=before, native_after=after,
                measurement=measurement, checks=dict(actual_final_drawable=True, capture_resources_stable=True)))
        return group

    try:
        inventory.prepare(ctx, case, source)
        after = spend_for_hud(ctx, case)
        route = evidence['native_inventory_spending'][-1]
        for index, attempt in enumerate(route['attempts']):
            checks = attempt['checks']
            evidence['native_resource_ownership'].append(dict(attempt=index, seat=attempt['seat'], checks=checks))
            require(all(checks.values()), 'Native inventory input changed another actor or did not produce its own resource effect')
        require(all(v['weapon'] > 0 for v in selected_resources(after)), 'Both native ammo meters need a selected earned weapon')
        settle('Initial native ammo use retired')
        initial = captures('both-selected-and-spent')
        # One actor changes again while the other stays untouched, providing a
        # resource-bracketed image comparison. Bounded attacks stop once native
        # energy has dropped by one eighth of capacity or eight accepted uses.
        start = case.sample('Before additional P1 native ammo use')
        initial_p1 = selected_resources(start)[0]
        target = max(1, initial_p1['capacity']//8)
        spending_deadline = time.monotonic()+60
        for index in range(8):
            before = case.sample('Additional P1 native attack bracket')
            current = selected_resources(before)
            value = current[0]
            distinct = value['energy']*current[1]['capacity'] != current[1]['energy']*value['capacity']
            if (initial_p1['energy']-value['energy'] >= target and distinct) or value['energy'] == 0:
                break
            require(time.monotonic() < spending_deadline, 'Additional native ammo-use budget expired')
            attempt = dict(seat=0, pressed=0x1000, before=before, label='additional-p1-'+str(index))
            evidence['extra_attacks'].append(attempt)
            try:
                attempt['acknowledgment'] = ctx['set_input'](0, 0x1000)
                used = case.wait(lambda r: hud.state.forward(before['observation']['tick'], r['observation']['tick']) and
                    selected_resources(r)[0]['energy'] < value['energy'], 'Additional original P1 Triangle consumes ammo')
                attempt['accepted'] = used
            finally:
                ctx['set_input'](0, 0)
            after = settle('Additional native attack retired')
            checks = ownership_checks(before, after, 0)
            checks['same_selected_weapon'] = selected_resources(before)[0]['weapon'] == selected_resources(after)[0]['weapon']
            attempt.update(after=after, checks=checks)
            require(all(checks.values()), 'Additional P1 attack did not preserve private native ownership')
        final = case.sample('Distinct final native ammo values')
        values = selected_resources(final)
        require(evidence['extra_attacks'], 'Additional native ammo use did not establish a changing selected meter')
        require(values[0]['energy']*values[1]['capacity'] != values[1]['energy']*values[0]['capacity'],
                'Selected ammo fractions are still identical; artwork ownership remains ambiguous')
        changed = captures('p1-extra-spent-p2-preserved')
        evidence['ammo_image_comparisons'] = [dict(drawable=a['measurement']['image_size'],
            observations=compare_regions(a['measurement'], b['measurement']))
            for a, b in zip(initial['captures'], changed['captures'])]
        evidence['checks'].update(both_native_heroes_selected_and_spent=all(route['checks'].values()),
            isolated_native_resource_changes=all(all(r['checks'].values()) for r in evidence['native_resource_ownership']),
            additional_p1_use_preserves_p2=all(all(r['checks'].values()) for r in evidence['extra_attacks']),
            selected_ammo_fractions_distinct=True, all_three_actual_drawable_aspects=len(changed['captures']) == 3)
        evidence['final_resources'] = values
        evidence['status'] = SUCCESS
        return evidence
    finally:
        for seat in (0, 1):
            try:
                ctx['set_input'](seat, 0)
            except Exception as error:
                evidence.setdefault('cleanup_errors', []).append(str(error))
