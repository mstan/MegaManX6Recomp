"""Offline inventory prerequisite bypass and native energy use for state QA.

Only prepare() writes the dedicated development mailbox. It grants earned
weapon flags through the original equipment initializer, without setting HP,
ammo, selection, action or any state-test completion result. spend() uses only
published host input and coherent actor observations.
"""
import hashlib
from pathlib import Path
import time

import coop_debug as debug
import inventory_mmx6_coop_content as content
import qualify_mmx6_coop_state as state

EQUIPMENT = 0x8003D718
EQUIPMENT_BYTES = 0x94
EQUIPMENT_SHA = 'd2cc0660040709245080d3e570746ce3247ec4b9064a251b0a08ce42112e0e8e'


def require(ok, message):
    if not ok:
        raise debug.DebugError(message)


def load_source(path):
    data = Path(path).read_bytes()
    require(hashlib.sha256(data).hexdigest() == content.EXE_SHA256, 'Inventory fixture original EXE changed')
    exe = content.Executable(data)
    start = exe.offset(EQUIPMENT, EQUIPMENT_BYTES)
    code = data[start:start+EQUIPMENT_BYTES]
    require(hashlib.sha256(code).hexdigest() == EQUIPMENT_SHA, 'Original equipment initializer changed')
    return dict(address=EQUIPMENT, bytes=EQUIPMENT_BYTES, sha256=EQUIPMENT_SHA,
                code_hex=code.hex(), shared_earned_flags=0x800CCED0+0x60,
                actor_earned_offset=0xC9, prerequisite='All eight earned-weapon bits; acquisition is bypassed, not qualified')


def earned(row):
    return [bytes.fromhex(row[name])[0xC9] for name in ('p1_body_hex', 'p2_body_hex')]


def prepare(ctx, case, source):
    require(ctx['mode'] == 'local' and ctx['input_path'] == 'published_host', 'Inventory prerequisite is offline only')
    require(ctx['clients'][0].read(source['address'], source['bytes']).hex() == source['code_hex'],
            'Live equipment initializer differs from pinned original code')
    case.adapter.settle_idle()
    before = case.sample('Before offline earned-weapon prerequisite bypass')
    require(earned(before) == [0, 0], 'Inventory prerequisite requires the fresh native intro inventory')
    record = dict(source=source, before=before, writes=[], bypasses=[source['prerequisite']],
                  scope='Prerequisite only; no HP/ammo/selection or state restoration values written')
    case.evidence['inventory_prerequisite'] = record
    for offset, value in ((0x51, 0xFF), (0x50, 9)):
        reply = ctx['request']('write_ram', addr=hex(debug.DIAGNOSTIC_ADDRESS+offset), val=hex(value))
        record['writes'].append(dict(address=debug.DIAGNOSTIC_ADDRESS+offset, value=value, response=reply))
    after = case.wait(lambda row: state.forward(before['observation']['tick'], row['observation']['tick']) and
                     earned(row) == [0xFF, 0xFF], 'Atomic original equipment initializer grants both inventories')
    require(ctx['clients'][0].read(debug.DIAGNOSTIC_ADDRESS+0x50, 1) == b'\0', 'Inventory fixture mailbox did not complete')
    require(state.private_resources(before) == state.private_resources(after), 'Inventory prerequisite changed current resources')
    record.update(after=after, checks=dict(both_native_earned_masks=True, current_resources_unchanged=True,
                                         completed_mailbox=True))
    return after


def changed_resources(saved, changed):
    old, new = state.private_resources(saved), state.private_resources(changed)
    return dict(
        genuine_native_ammo_spent_both_heroes=all(
            all(0 <= b <= a for a, b in zip(p[2], q[2])) and any(b < a for a, b in zip(p[2], q[2]))
            for p, q in zip(old, new)),
        genuine_native_weapon_changed_both_heroes=all(0 <= q[1] <= 8 and p[1] != q[1] for p, q in zip(old, new)),
    )


def spend(ctx, case, label, *, timeout=45):
    before = case.sample(label+' before native energy use')
    route = dict(label=label, before=before, attempts=[], checks={}, bypasses=[])
    case.evidence.setdefault('native_inventory_spending', []).append(route)
    deadline = time.monotonic()+timeout

    def hold(seat, bits, frames, why):
        require(time.monotonic() < deadline, 'Native inventory input deadline expired')
        try:
            receipt = ctx['set_input'](seat, bits)
            ctx['native_advance'](frames, why)
        finally:
            ctx['set_input'](seat, 0)
        ctx['native_advance'](3, why+' neutral')
        row = case.sample(why)
        route['attempts'].append(dict(seat=seat, pressed=bits, native_ticks=frames, acknowledgment=receipt, after=row))
        return row

    def idle(seat):
        for _ in range(60):
            row = case.sample(label+' native actor readiness')
            player = row['observation']['players'][seat]
            require(player['hp'] > 0 and row['observation']['native_phase'] == 0,
                    'Native energy input left living gameplay')
            if player['action'] == 2:
                return row
            ctx['native_advance'](3, label+' native action recovery')
        raise debug.DebugError('Native actor did not become ready for an energy input')

    try:
        for seat in (0, 1):
            idle(seat)
            old = state.private_resources(before)[seat]
            for _ in range(9):
                row = hold(seat, 0x800, 4, label+' native R1 weapon cycle')
                if state.private_resources(row)[seat][1] != old[1]:
                    break
            else:
                raise debug.DebugError('Native R1 did not change selected weapon for seat'+str(seat))
            for bits in (0x8000, 0x1000, 0x200, 0x240, 0x1040, 0x210, 0x1010):
                idle(seat)
                row = hold(seat, bits, 5, label+' native selected-weapon input '+hex(bits))
                if any(b < a for a, b in zip(old[2], state.private_resources(row)[seat][2])):
                    break
            else:
                raise debug.DebugError('Native inputs did not spend energy for seat'+str(seat))
        after = case.sample(label+' both actors after actual energy use')
        route.update(after=after, checks=changed_resources(before, after))
        require(all(route['checks'].values()), 'Native ammo and selection did not both diverge from saved resources')
        return after
    finally:
        for seat in (0, 1):
            ctx['set_input'](seat, 0)
