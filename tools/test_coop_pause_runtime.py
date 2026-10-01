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
            write(0x800970FC, 13 if seat else 11)
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
