"""Destructive unit-selection fixture for a PRIVATE, freshly booted runtime.

Start after the opening dialogue. This changes unlocks and enters stage select
through the native screen loader; it never saves. --single-player exercises
the same native menu with the co-op plugin disabled. No savestates are used.
"""
import argparse
import json
import socket
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--single-player', action='store_true')
    args = parser.parse_args()
    play = 0x800CCED0
    table, count_addr = 0x800F1CB0, 0x800F1CEB

    def request(cmd, **fields):
        with socket.create_connection(('127.0.0.1', args.port), timeout=5) as conn:
            conn.sendall((json.dumps(dict(id=1, cmd=cmd, **fields))+'\n').encode())
            result = json.loads(conn.makefile('r').readline())
        if not result.get('ok'):
            raise RuntimeError(result)
        return result

    def read(addr, size=1):
        return bytes.fromhex(request('read_ram', addr=hex(addr), len=size)['hex'])

    def write(addr, value):
        request('write_ram', addr=hex(addr), val=hex(value))

    def wait(predicate, seconds=20):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.05)
        raise AssertionError(f'Timed out; menu state {read(play, 4).hex()}')

    def tap(button):
        request('press', buttons=button, frames=6)
        time.sleep(.3)

    try:
        request('press', buttons=0xFFFF, frames=60000)
        for flags, armors in ((0, [0]), (0x11, [0, 1]), (0x3F, [0, 1, 2, 3, 4])):
            expected = armors[:]
            if args.single_player and flags & 0x10:
                expected.insert(2, 5)
            # Loading the map is a native screen transition, not an overlay or
            # menu-table injection. Poll the table only once that load completes.
            write(play+0x5F, flags)
            write(play+1, 0)
            write(play+2, 0)
            write(play, 2)
            wait(lambda: read(play)[0] == 4 and read(play+1)[0] in (3, 4, 11))
            briefing_deadline = time.monotonic()+30
            while read(play+1)[0] == 11:  # First post-intro Signas briefing.
                assert time.monotonic() < briefing_deadline, 'Signas briefing did not finish'
                tap(0xBFFF)
            wait(lambda: read(play, 3) == b'\x04\x04\x00')
            count = read(count_addr)[0]
            assert list(read(table, count)) == expected, (flags, read(table, count))
            assert read(play+0x5F)[0] == flags, 'Menu altered persistent unlock flags'
            tap(0xBFFF)  # Stage -> native player selector.
            wait(lambda: read(play, 3) == b'\x04\x04\x05')
            assert read(play+0x30)[0] < count, 'Invalid initial cursor'
            for button, delta in ((0xFFDF, 1), (0xFF7F, -1)):
                for _ in range(count+1):
                    before = read(play+0x30)[0]
                    tap(button)
                    after = read(play+0x30)[0]
                    assert after == (before+delta) % count, (before, after, delta)
                    assert read(table+after)[0] in expected
            print(f'PASS flags {flags:02X}: native choices {expected}, both wraps, unlocks intact',
                  flush=True)
            if flags != 0x3F:
                tap(0xEFFF)  # Back to stage select before rebuilding choices.
                wait(lambda: read(play, 3) == b'\x04\x04\x00')

        # Confirm X's Falcon form, then let the game load the stage normally.
        for _ in range(count):
            if read(table+read(play+0x30)[0])[0] == 1:
                break
            tap(0xFFDF)
        assert read(table+read(play+0x30)[0])[0] == 1, 'Falcon cannot be selected'
        tap(0xBFFF)
        wait(lambda: read(play)[0] == 10 and read(0x800970A4, 2) == b'\x01\x02', 60)
        assert read(play+0x38)[0] == 0 and read(play+0x5E)[0] == 1, 'P1 is not Falcon X'
        assert read(play+0x5F)[0] == 0x3F, 'Stage entry lost unlocks'
        if not args.single_player:
            wait(lambda: read(0x9F080039)[0] == 0 and read(0x9F080104, 2) == b'\x01\x02')
            assert read(0x9F08015C)[0] > 0, 'P2 Zero did not arrive alive'
            print('PASS native confirmation loads Falcon X with living P2 Zero', flush=True)
        else:
            print('PASS plugin-disabled native Zero choices and stage confirmation', flush=True)
    finally:
        request('clear_input')


if __name__ == '__main__':
    main()
