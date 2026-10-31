"""Pause/Sub Tank fixture for a PRIVATE co-op intro after Alia's conversation.

Grants a shared Sub Tank and adjusts each actor's health in the development
build. Requires both actors alive and standing safely. Verifies native menu
input ownership, frozen world time and collector-only healing for both seats.
Artwork still needs screenshot inspection.
"""
import argparse
import json
import socket
import time


def exercise_independent(request, client, output, report, *, reload_checkpoint=False):
    """F180 LOCAL prerequisite grants only; native inputs spend the energy.

    Raw RAM grants are confined to the disposable offline profile. This is
    never a NET fixture or evidence of naturally earned tank acquisition.
    """
    from qualify_mmx6_coop_state import snapshot_operation
    diag = 0x9F080000
    report['checks'] = {}
    report['steps'] = []
    report['setup_bypass'] = 'Offline native RAM tank/energy grants and existing typed damaged-HP mailbox; all healing uses original menu input'

    def read(address, count=1):
        return client.read(address, count)

    def write(address, value):
        request('write_ram', addr=hex(address), val=hex(value))

    def wait(predicate, message, seconds=8):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.03)
        raise AssertionError(message)

    def banks():
        row = read(diag+0x1FF0, 6)
        if row[:2] != b'\1\1':
            raise AssertionError('Independent native energy policy was not active and seeded')
        return list(row[2:])

    def hp():
        return [read(diag+0x1800+0x5C)[0], read(diag+0x100+0x5C)[0]]

    def press(seat, buttons):
        request('press', port=seat+1, buttons=buttons, frames=6)
        time.sleep(.18)
        request('clear_input', port=seat+1)
        time.sleep(.1)

    def menu(seat):
        press(seat, 0xFFF7)
        wait(lambda: read(0x800CCED1) == b'\2' and read(0x800CF814, 2) == b'\1\0', 'Native owned menu did not open')
        if read(diag+0x3C)[0] != seat+1:
            raise AssertionError('Wrong native pause owner')

    def close(seat):
        wait(lambda: read(0x800CF814, 2) in (b'\1\0', b'\1\1'), 'Native heal animation did not complete')
        press(seat, 0xFFF7)
        wait(lambda: read(0x800CCED1) == b'\0', 'Native menu did not close')

    def use(seat, expected_hp):
        cursor = read(0x800CF824)
        press(seat ^ 1, 0xFFDF)
        if read(0x800CF824) != cursor:
            raise AssertionError('Other seat changed the owned menu cursor')
        press(seat, 0xFFDF)
        wait(lambda: read(0x800CF824) == b'\x0a', 'Native Sub Tank cursor was not selected')
        press(seat, 0xBFFF)
        wait(lambda: hp()[seat] == expected_hp, 'Native tank did not heal its owner')
        close(seat)

    def damage():
        deadline = time.monotonic()+5
        while hp()[0] != 13:
            write(0x800970FC, 13)
            time.sleep(.05)
            if time.monotonic() > deadline:
                raise AssertionError('P1 damaged-health prerequisite failed')
        write(diag+0x51, 11);write(diag+0x50, 1)
        wait(lambda: read(diag+0x50) == b'\0' and hp()[1] == 11, 'P2 damaged-health prerequisite failed')

    banks()
    try:
        # Existing fixture health setup, verified at published body boundaries.
        damage()
        write(0x800CCF3B, read(0x800CCF3B)[0] | 0x10)
        menu(1)
        # The debug service can run inside the native Zero projection. Verify
        # the actual private bank receives the disclosed eight-unit grant.
        deadline = time.monotonic()+5
        while banks()[2] != 0x88:
            write(0x800CCF33, 0x88)
            time.sleep(.03)
            if time.monotonic() > deadline:
                raise AssertionError('P2 private energy prerequisite failed')
        if reload_checkpoint:
            import mmx6_coop_checkpoint as checkpoint
            from pathlib import Path
            close(1)
            before_reload = banks()
            found = read(0x800CCF3B)[0]
            source = Path(__file__).resolve().parents[1]
            original = checkpoint.original_executable(source/'mmx6/SLUS_013.95')
            _, rows, sections = checkpoint.verified_inventory(source/'docs/COOP_X6_CONTENT.json', original)
            target = checkpoint.select(rows, sections, 0, 0, 0)
            report['checkpoint_reload'] = {}
            checkpoint.enter_checkpoint(request, client, target, report['checkpoint_reload'], timeout=120, nonce=180)
            wait(lambda: banks() == before_reload, 'Private supplies changed across original checkpoint initialization')
            if read(0x800CCF3B)[0] != found:
                raise AssertionError('Shared native tank acquisition changed at checkpoint')
            report['checks']['private_energy_and_shared_acquisition_survive_native_checkpoint'] = True
            report['steps'].append(dict(label='after_native_checkpoint', banks=banks(), hp=hp()))
            damage()
            menu(1)
        report['snapshot_operations'] = []
        saved = dict(banks=banks(), hp=hp())
        snapshot_operation(request, 'save', 8, report['snapshot_operations'])
        report['steps'].append(dict(label='before_p2_native_heal', **saved))
        use(1, 19)
        after_p2 = dict(banks=banks(), hp=hp())
        report['steps'].append(dict(label='after_p2_native_heal', **after_p2))
        if after_p2['hp'] != [13, 19] or after_p2['banks'][2] != 0x80:
            raise AssertionError('P2 private native heal/isolation failed')
        # Give the native card-authoritative P1 bank sixteen units separately.
        deadline = time.monotonic()+5
        while banks()[0] != 0x90:
            write(0x800CCF33, 0x90)
            time.sleep(.03)
            if time.monotonic() > deadline:
                raise AssertionError('P1 private energy prerequisite failed')
        menu(0)
        use(0, 29)
        after_p1 = dict(banks=banks(), hp=hp())
        report['steps'].append(dict(label='after_p1_native_heal', **after_p1))
        if after_p1['hp'] != [29, 19] or after_p1['banks'][0] != 0x80 or after_p1['banks'][2] != 0x80:
            raise AssertionError('P1 private native heal/isolation failed')
        report['checks']['both_native_private_heals_and_health_isolation'] = True
        snapshot_operation(request, 'load', 8, report['snapshot_operations'])
        wait(lambda: banks() == saved['banks'] and hp() == saved['hp'], 'Current-build private energy/health restore failed')
        report['steps'].append(dict(label='restored_private_supplies', banks=banks(), hp=hp()))
        report['checks']['current_build_private_energy_and_health_restore'] = True
        request('present_shot', path=str(output/'private-tank-restored.png'))
        close(1)
    finally:
        request('clear_input', port=1);request('clear_input', port=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    diag = 0x9F080000

    def request(command, **fields):
        with socket.create_connection(('127.0.0.1', args.port), timeout=10) as conn:
            conn.sendall((json.dumps(dict(id=1, cmd=command, **fields))+'\n').encode())
            result = json.loads(conn.makefile('r').readline())
        if not result.get('ok'):
            raise RuntimeError(result)
        return result

    def read(address, count=1):
        return bytes.fromhex(request('read_ram', addr=hex(address), len=count)['hex'])

    def write(address, value):
        request('write_ram', addr=hex(address), val=hex(value))

    def p2(buttons):
        write(diag+0x34, buttons & 255)
        write(diag+0x35, buttons >> 8)
        write(diag+0x30, 1)

    def press(seat, buttons):
        if seat:
            p2(buttons)
            time.sleep(.1)
            p2(0xFFFF)
        else:
            request('press', buttons=buttons, frames=6)
            time.sleep(.12)
        time.sleep(.1)

    def wait(predicate, seconds=5):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.03)
        raise AssertionError('Native menu did not reach the expected state')

    def check(condition, message):
        if not condition:
            raise AssertionError(message)

    check(read(diag+0x38, 2) == b'\0\0', 'Both players must be alive')
    try:
        p2(0xFFFF)
        for seat in (1, 0):
            # The debug server may service a RAM write during Zero's native
            # projection (including solid-object collision). Verify the
            # published P1 body received setup before testing tank healing.
            target_hp = 13 if seat else 11
            deadline = time.monotonic()+3
            while True:
                write(0x800970FC, target_hp)
                time.sleep(.05)
                if read(diag+0x1800+0x5C)[0] == target_hp:
                    break
                check(time.monotonic() < deadline, 'Could not set up P1 health')
            write(diag+0x51, 11 if seat else 13)
            write(diag+0x50, 1)
            wait(lambda: read(diag+0x50) == b'\0')
            write(0x800CCF3B, read(0x800CCF3B)[0] | 0x10)
            write(0x800CCF33, 0x8A)  # Owned, partially filled, ten healing units.
            press(seat, 0xFFF7)
            wait(lambda: read(0x800CCED1) == b'\2' and
                 read(0x800CF814, 2) == b'\1\0')
            check(read(diag+0x3C)[0] == seat+1, 'Wrong pause owner')
            timer = read(0x800CCF60, 4)
            time.sleep(.3)
            check(read(0x800CCF60, 4) == timer, 'World timer advanced while paused')
            cursor = read(0x800CF824)
            press(seat ^ 1, 0xFFDF)
            check(read(0x800CF824) == cursor, 'Other player moved menu cursor')
            press(seat, 0xFFDF)
            wait(lambda: read(0x800CF824) == b'\x0a')
            press(seat, 0xBFFF)
            wait(lambda: read(0x800CCF33) == b'\x80')
            # The fill byte drains before the native healing animation ends.
            # Start is ignored until the menu returns to its input state.
            wait(lambda: read(0x800CF814, 2) == b'\1\1')
            press(seat, 0xFFF7)
            wait(lambda: read(0x800CCED1) == b'\0')
            time.sleep(.15)
            hp = [read(diag+0x1800+0x5C)[0], read(diag+0x100+0x5C)[0]]
            check(hp[seat] == 21, f'P{seat+1} tank healing was not retained: {hp}')
            check(hp[seat ^ 1] == 13, f'Tank healed the other player: {hp}')
            print(f'PASS P{seat+1} pause ownership, frozen time and shared tank healing', flush=True)
    finally:
        p2(0xFFFF)
        write(diag+0x30, 0)
        request('clear_input')


if __name__ == '__main__':
    main()
