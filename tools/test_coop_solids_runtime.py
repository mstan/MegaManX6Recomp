"""Private intro-block regression; requires a fresh controllable co-op stage.

Places both players at the real intro hallway block and exercises its native
collision with controller input. Uses development mailbox placement, never a
savestate. Do not run against someone's active play session.
"""
import argparse
import json
from pathlib import Path
import socket
import struct
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    diag = 0x9F080000

    def request(cmd, **fields):
        with socket.create_connection(('127.0.0.1', args.port), timeout=10) as conn:
            conn.sendall((json.dumps(dict(id=1, cmd=cmd, **fields))+'\n').encode())
            result = json.loads(conn.makefile('r').readline())
        if not result.get('ok'):
            raise RuntimeError(result)
        return result

    def read(addr, size=1):
        return bytes.fromhex(request('read_ram', addr=hex(addr), len=size)['hex'])

    def write(addr, value):
        request('write_ram', addr=hex(addr), val=hex(value))

    def wait(predicate, seconds=8):
        deadline = time.monotonic()+seconds
        while not predicate():
            if time.monotonic() >= deadline:
                raise AssertionError('Timed out waiting for native stage/fixture')
            time.sleep(.03)

    def frames(count):
        first = int.from_bytes(read(diag+4, 4), 'little')
        wait(lambda: int.from_bytes(read(diag+4, 4), 'little')-first >= count)

    def command(cmd, seat=0, value=0):
        write(diag+0x51, value)
        write(diag+0x52, seat)
        write(diag+0x50, cmd)
        wait(lambda: read(diag+0x50) == b'\0')

    def warp(seat, x, y):
        for offset, data in ((0x54, struct.pack('<i', x << 16)),
                             (0x58, struct.pack('<i', y << 16))):
            for i, value in enumerate(data):
                write(diag+offset+i, value)
        command(4, seat)

    def p2(buttons):
        write(diag+0x34, buttons & 255)
        write(diag+0x35, buttons >> 8)
        write(diag+0x30, 1)

    def body(seat):
        return read(diag+(0x100 if seat else 0x1800), 0x158)

    def xy(seat):
        return tuple(v / 65536 for v in struct.unpack_from('<ii', body(seat), 8))

    def drive(seat, buttons, count=70):
        if seat:
            p2(buttons)
        else:
            request('press', buttons=buttons, frames=count+3)
        frames(count)
        if seat:
            p2(0xFFFF)
        else:
            request('clear_input')
        frames(3)

    def screenshot(name):
        if args.screenshots:
            args.screenshots.mkdir(parents=True, exist_ok=True)
            request('screenshot_file', path=str((args.screenshots / (name+'.png')).resolve()))

    assert read(0x800CCEDC, 2) == b'\0\0', 'Requires intro stage'
    assert read(diag+0x38, 2) == b'\0\0', 'Requires both players alive'
    lives = read(0x800CCF09)
    try:
        p2(0xFFFF)
        request('clear_input')
        warp(2, 3010, 1115)
        frames(90)
        def find_block():
            solids = read(0x800C1220, 80*0xA4)
            return next((0x800C1220+i for i in range(0, len(solids), 0xA4)
                         if solids[i] and solids[i+1] == 2 and
                         struct.unpack_from('<h', solids, i+10)[0] == 3104), None)
        # Camera catch-up drives native object spawning after a long warp.
        wait(find_block)
        block = find_block()
        assert int.from_bytes(read(block+14, 2), 'little') == 1104
        for seat in (0, 1):
            for start, buttons, side in ((3020, 0xFFDF, 'left'), (3180, 0xFF7F, 'right')):
                warp(seat, start, 1115)
                frames(4)
                drive(seat, buttons)
                x, y = xy(seat)
                assert (3040 < x < 3072) if side == 'left' else (3135 < x < 3165), (seat, side, x, y)
                assert y > 1072, 'Side test accidentally passed by jumping onto block'
                print(f'PASS P{seat+1} blocked from {side}: {x:.2f}, {y:.2f}', flush=True)
            warp(seat, 3020, 1115)
            frames(3)
            drive(seat, 0xDFDF)  # Right + dash.
            x, y = xy(seat)
            assert 3040 < x < 3072 and y > 1072, (seat, 'dash', x, y)
            print(f'PASS P{seat+1} dash blocked: {x:.2f}', flush=True)
        # This block sits under a low ceiling. A normal jump against it must
        # return outside, like P1, rather than putting Zero inside the block.
        for seat in (0, 1):
            warp(seat, 3060, 1115)
            frames(10)
            drive(seat, 0xBFDF, 16)  # Jump right against the block/ceiling.
            frames(55)
        frames(90)
        for seat in (0, 1):
            x, y = xy(seat)
            assert 3040 < x < 3072 and 1110 < y < 1120, (seat, 'jump', x, y)
        print(f'PASS both players land outside block under low ceiling: {xy(0)}, {xy(1)}', flush=True)
        screenshot('solid-both-at-block')
        assert read(diag+0x38, 2) == b'\0\0' and read(0x800CCF09) == lives

        # Native HUD rendering with each selection independently. These are
        # visual fixtures, not a claim that intro progression unlocks weapons.
        for first, second, label in ((0, 0, 'base'), (1, 0, 'p1-ammo'),
                                     (0, 1, 'p2-ammo'), (1, 1, 'both-ammo'),
                                     (0, 0, 'base-restored')):
            command(7, 0, first)
            command(7, 1, second)
            frames(8)
            assert body(0)[0x93] == first and body(1)[0x93] == second
            screenshot('hud-'+label)
        print('Captured independent native ammo-bar visibility fixtures', flush=True)
    finally:
        p2(0xFFFF)
        write(diag+0x30, 0)
        request('clear_input')


if __name__ == '__main__':
    main()
