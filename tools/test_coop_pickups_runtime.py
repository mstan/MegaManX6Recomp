"""Private native-item fixture: run after the opening dialogue with both alive.

Uses the development mailbox to allocate real dropped items in the native
enemy pool. Changes HP/ammo/lives; never run against a normal play session.
"""
import argparse
import json
import socket
import struct
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--souls', action='store_true', help='Also spawn native Nightmare cores (stage resources required)')
    args = parser.parse_args()
    diag = 0x9F080000

    def request(cmd, **fields):
        with socket.create_connection(('127.0.0.1', args.port), timeout=10) as conn:
            conn.sendall((json.dumps(dict(id=1, cmd=cmd, **fields))+'\n').encode())
            result = json.loads(conn.makefile('r').readline())
        if not result.get('ok'):
            raise RuntimeError(result)
        return result

    def read(addr, count=1):
        return bytes.fromhex(request('read_ram', addr=hex(addr), len=count)['hex'])

    def write(addr, val):
        request('write_ram', addr=hex(addr), val=hex(val))

    def wait(predicate):
        end = time.monotonic()+5
        while time.monotonic() < end:
            if predicate():
                return
            time.sleep(.03)
        raise AssertionError('Native pickup fixture timed out')

    def p2(buttons):
        write(diag+0x34, buttons & 255)
        write(diag+0x35, buttons >> 8)
        write(diag+0x30, 1)

    def command(cmd):
        write(diag+0x50, cmd)
        wait(lambda: read(diag+0x50) == b'\0')

    def body(seat):
        return read(diag+(0x100 if seat else 0x1800), 0x158)

    def pickup(kind, seat):
        write(diag+0x64, 0)
        write(diag+0x51, kind)
        write(diag+0x52, seat)
        command(3)
        actor = struct.unpack('<I', read(diag+0x68, 4))[0]
        assert actor, 'Native item pool has no free slot'
        wait(lambda: read(diag+0x64)[0] == seat+1)
        wait(lambda: read(0x800CCEE0) == b'\0' and read(actor) == b'\0')
        time.sleep(.1)

    assert read(diag+0x38, 2) == b'\0\0', 'Both players must be alive'
    try:
        x = [struct.unpack_from('<i', body(s), 8)[0] >> 16 for s in (0, 1)]
        if abs(x[1]-x[0]) < 48:
            p2(0xFFDF)
            time.sleep(.5)
        p2(0xFFFF)
        time.sleep(.2)
        for seat in (1, 0):
            write(0x800970FC, 11)
            write(diag+0x51, 13)
            command(1)
            pickup(32, seat)  # Native small health: four units over time.
            expected = [11, 13]
            expected[seat] += 4
            assert [body(s)[0x5C] for s in (0, 1)] == expected
            print(f'PASS P{seat+1} delayed health remains collector-only', flush=True)

            for offset in range(0xA8, 0xBA):
                write(0x800970A0+offset, 0)
            write(diag+0x52, 0)
            write(diag+0x53, 0)
            command(2)
            before = [body(s)[0xA8:0xBA] for s in (0, 1)]
            pickup(35, seat)  # Native small weapon-energy item.
            after = [body(s)[0xA8:0xBA] for s in (0, 1)]
            assert after[seat] != before[seat], 'Collector got no ammo'
            assert after[seat ^ 1] == before[seat ^ 1], 'Partner got collector ammo'
            print(f'PASS P{seat+1} ammo remains collector-only', flush=True)

        # Distinct uncollected stage IDs for each fixture; native collection
        # flags remain shared, while the permanent increase is collector-only.
        for seat in (1, 0):
            for base, kind, label in ((0x800CCF2B, seat, 'Heart Tank'),
                                      (0x800CCF31, 16+seat, 'weapon capacity')):
                before = list(read(base, 2))
                # This is a disposable fixture, so make these IDs collectible.
                flags = 0x800CCF3C+(0 if kind < 16 else 2)
                write(flags, read(flags)[0] & ~(1 << seat))
                pickup(kind, seat)
                before[seat] += 2
                assert list(read(base, 2)) == before, f'{label} ownership changed'
                print(f'PASS P{seat+1} {label} stays character-specific', flush=True)

        if args.souls:
            for seat in (1, 0):
                before = list(struct.unpack('<HH', read(0x800CCFA2, 4)))
                write(diag+0x51, 0xF0)  # Native small Nightmare core, type 0x31.
                write(diag+0x52, seat)
                command(3)
                before[seat] += 4
                wait(lambda: list(struct.unpack('<HH', read(0x800CCFA2, 4))) == before)
                print(f'PASS P{seat+1} Nightmare Souls stay character-specific', flush=True)

        lives = read(0x800CCF09)[0]
        pickup(38, 1)
        assert read(0x800CCF09)[0] == min(lives+1, 9)
        print('PASS P2 life pickup increments the shared pool once', flush=True)
    finally:
        p2(0xFFFF)
        write(diag+0x30, 0)
        request('clear_input')


if __name__ == '__main__':
    main()
