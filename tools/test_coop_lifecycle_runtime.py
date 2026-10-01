"""Destructive lifecycle fixture for a PRIVATE, freshly booted co-op intro.

Run after clearing the opening Alia conversation, with both players idle and
at least two lives. This spends two lives and changes Zero's HP/ammo using
the development plugin's fixture mailbox. It does not use savestates. Native
enemy damage, death art, camera/pits and campaign transitions require separate
gameplay validation. Never run against a user's normal gameplay session.
"""
import argparse
import json
import socket
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--diagnostic', type=lambda v: int(v, 0), default=0x9F080000)
    args = parser.parse_args()
    diag = args.diagnostic

    def request(command, **fields):
        with socket.create_connection(('127.0.0.1', args.port), timeout=5) as conn:
            conn.sendall((json.dumps(dict(id=1, cmd=command, **fields))+'\n').encode())
            result = json.loads(conn.makefile('r').readline())
        if not result.get('ok'):
            raise RuntimeError(result)
        return result

    def read(address, count):
        return bytes.fromhex(request('read_ram', addr=hex(address), len=count)['hex'])

    def write(address, value):
        request('write_ram', addr=hex(address), val=hex(value))

    def p2(buttons):
        write(diag+0x34, buttons & 255)
        write(diag+0x35, buttons >> 8)
        write(diag+0x30, 1)

    def fixture(command, value):
        payload = 0x51 if command == 1 else 0x52
        write(diag+payload, value & 255)
        if command == 2:
            write(diag+payload+1, value >> 8)
        write(diag+0x50, command)

    def state():
        d = read(diag, 64)
        if d[:4] != b'POOC':
            raise RuntimeError('Co-op diagnostic block is not active')
        b = read(diag+0x100, 0x158)
        p = read(0x800CCED0, 64)
        return dict(status=list(d[0x38:0x3C]), hp=b[0x5C],
                    ammo=b[0xA8:0xBA].hex(), weapon=b[0x93],
                    stage=p[0], lives=p[0x39])

    def wait(predicate, seconds=12):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            s = state()
            if predicate(s):
                return s
            time.sleep(.03)
        raise AssertionError(state())

    def check(condition, message):
        if not condition:
            raise AssertionError(message)

    initial = state()
    check(initial['stage'] == 10 and initial['status'][:2] == [0, 0],
          'Start in a controllable intro with both actors alive')
    check(initial['lives'] >= 2, 'This private test needs at least two lives')
    lives = initial['lives']
    try:
        p2(0xFFFF)
        fixture(1, 11)
        wait(lambda s: s['hp'] == 11)
        fixture(2, 0x90)  # Half the native 0x120 capacity.
        before = wait(lambda s: s['ammo'] == '9000'*9)
        p2(0xFFFE)
        wait(lambda s: s['status'][1] == 1)
        wait(lambda s: s['status'][1] == 2)
        time.sleep(.2)
        check(state()['status'][1] == 2, 'Held Select rejoined immediately')
        p2(0xFFFF)
        time.sleep(.1)
        p2(0xFFFE)
        wait(lambda s: s['status'][1] == 3)
        p2(0xFFFF)
        after = wait(lambda s: s['status'][1] == 0)
        for field in ('hp', 'ammo', 'weapon'):
            check(before[field] == after[field], f'Rejoin changed {field}')
        print('PASS leave/rejoin retains damaged HP, spent ammo and weapon', flush=True)

        # Pending-fatal HP flag enters the original game death controller.
        write(0x800970FC, 0x80)
        fallen = wait(lambda s: s['status'][0] == 5)
        check(fallen['stage'] == 10 and fallen['lives'] == lives,
              'X death restarted the stage or spent a life')
        p2(0xFFFE)
        time.sleep(2)
        check(state()['status'][1] == 0, 'Sole surviving Zero left')
        p2(0xFFFF)
        fixture(1, 0x80)
        wait(lambda s: s['status'][3] == 2)
        wait(lambda s: s['lives'] == lives-1, 20)
        ready = wait(lambda s: s['stage'] == 10 and s['status'][:2] == [0, 0]
                     and s['hp'] > 0, 60)
        check(ready['lives'] == lives-1, 'Team wipe spent more than one life')
        print('PASS X dies first; Zero survives; one life spent on team wipe', flush=True)

        fixture(1, 0x80)
        dead = wait(lambda s: s['status'][1] == 5)
        check(dead['stage'] == 10 and dead['lives'] == lives-1,
              'Zero death restarted the stage or spent a life')
        p2(0xFFFE)
        time.sleep(2)
        check(state()['status'][1] == 5, 'Select revived fallen Zero')
        p2(0xFFFF)
        write(0x800970FC, 0x80)
        wait(lambda s: s['status'][3] == 1)
        wait(lambda s: s['lives'] == lives-2, 20)
        ready = wait(lambda s: s['stage'] == 10 and s['status'][:2] == [0, 0]
                     and s['hp'] > 0, 60)
        check(ready['lives'] == lives-2, 'Reverse-order wipe life count wrong')
        print('PASS Zero dies first; no dead rejoin; both respawn after second wipe', flush=True)
    finally:
        p2(0xFFFF)
        write(diag+0x30, 0)
        request('clear_input')


if __name__ == '__main__':
    main()
