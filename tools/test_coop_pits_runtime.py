"""Destructive private intro-pit regression using native movement and gravity.

Starts in a fresh controllable co-op intro with two lives. Places the team on
the ledge beside the reported pit, then walks each player off it. Checks both
death orders, survivor control, no dead rejoin, and one life per joint wipe.
Never use against the owner's active session or shared memory cards.
"""
import argparse
import json
import socket
import struct
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--expect-bug', action='store_true', help='Prove baseline P2 falls past the death boundary')
    parser.add_argument('--first', choices=('both', 'p1', 'p2'), default='both')
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

    def write(addr, value):
        request('write_ram', addr=hex(addr), val=hex(value))

    def state():
        data = read(diag, 0x1958)
        bodies = [data[0x1800:0x1958], data[0x100:0x258]]
        return dict(tick=int.from_bytes(data[4:8], 'little'), life=list(data[0x38:0x3A]),
                    xy=[tuple(v / 65536 for v in struct.unpack_from('<ii', b, 8)) for b in bodies],
                    hp=[b[0x5C] for b in bodies], mode=[list(b[4:7]) for b in bodies],
                    lives=read(0x800CCF09)[0], scene=data[0x3E])

    def wait(predicate, seconds=15):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            value = state()
            if predicate(value):
                return value
            time.sleep(.03)
        raise AssertionError(state())

    def frames(count):
        tick = state()['tick']
        return wait(lambda s: s['tick']-tick >= count)

    def warp(seat, x, y):
        for offset, value in ((0x54, x), (0x58, y)):
            for i, byte in enumerate(struct.pack('<i', value << 16)):
                write(diag+offset+i, byte)
        write(diag+0x52, seat)  # 2 places both at the same safe boundary.
        write(diag+0x50, 4)
        wait(lambda _: read(diag+0x50) == b'\0')

    def buttons(seat, raw, count=90):
        if seat:
            write(diag+0x34, raw & 255)
            write(diag+0x35, raw >> 8)
            write(diag+0x30, 1)
        elif raw == 0xFFFF:
            request('press', buttons=raw, frames=60000)
        else:
            request('press', buttons=raw, frames=count)

    def prepare():
        buttons(0, 0xFFFF)
        buttons(1, 0xFFFF)
        warp(2, 5020, 874)
        # A long fixture warp skips the approach's camera-region triggers.
        # Seed this ledge's native target bounds, captured from the owner's
        # normal playthrough; the native camera still performs the transition.
        for i, value in enumerate((5120, 0, 704, 376)):
            for j, byte in enumerate(struct.pack('<h', value)):
                write(0x800971F8+0x24+i*2+j, byte)
        frames(180)
        wait(lambda _: int.from_bytes(read(0x80097218, 2), 'little', signed=True) == 704)
        # Isolate pit handling from the nearby enemy's knockback. Leave
        # terrain/solids, the player update, and native gravity untouched.
        for base, stride, count in ((0x8008EF48, 0x9C, 48), (0x80093C98, 0xA0, 32)):
            actors = read(base, stride*count)
            for i in range(count):
                if actors[i*stride]:
                    write(base+i*stride, 0)
                    write(base+i*stride+3, 0)
        frames(60)
        current = state()
        assert current['life'] == [0, 0] and not current['scene'], current
        assert all(860 < y < 900 for _, y in current['xy']), current
        return current

    def fall(seat, last=False):
        buttons(seat, 0xFF7F, 60000)  # Walk into the pit; no HP/fatal injection.
        wait(lambda s: s['xy'][seat][0] <= 4970 or s['life'][seat] != 0)
        buttons(seat, 0xFFFF)
        if args.expect_bug:
            result = wait(lambda s: s['xy'][1][1] > 1400)
            assert result['life'][1] == 0 and result['hp'][1] > 0, result
            print('BASELINE reproduced: Zero is alive below native pit boundary', result, flush=True)
        else:
            result = wait(lambda s: s['life'][seat] in ((4, 5) if last else (5,)))
            assert (result['hp'][seat] & 0x7F) == 0, result
            assert result['xy'][seat][1] >= 968, 'Death happened before crossing the pit boundary'
            print(f'PASS P{seat+1} native pit death', result, flush=True)
        buttons(seat, 0xFFFF)
        return result

    assert read(0x800CCEDC, 2) == b'\0\0', 'Requires intro stage'
    initial = state()
    order = (1,) if args.expect_bug or args.first == 'p2' else (0,) if args.first == 'p1' else (1, 0)
    assert initial['life'] == [0, 0] and initial['lives'] >= len(order), initial
    lives = initial['lives']
    try:
        for first in order:
            prepare()
            dead = fall(first)
            if args.expect_bug:
                return
            assert dead['life'][first ^ 1] == 0 and dead['lives'] == lives, dead
            assert dead['hp'][first ^ 1] > 0, dead
            # Continue long enough to expose repeated death/respawn or drift.
            buttons(1, 0xFFFE)
            stable = frames(120)
            buttons(1, 0xFFFF)
            assert stable['life'] == dead['life'] and stable['lives'] == lives, stable
            assert stable['xy'][first] == dead['xy'][first], stable
            camera_y = int.from_bytes(read(0x80097206, 2), 'little', signed=True)
            survivor_y = stable['xy'][first ^ 1][1]
            assert camera_y <= survivor_y <= camera_y+240, (camera_y, stable)
            print('PASS survivor stays in; fallen player stays out; no life spent', flush=True)
            print(f'PASS camera contains survivor: top={camera_y}, player={survivor_y}', flush=True)
            fall(first ^ 1, last=True)
            wait(lambda s: s['lives'] == lives-1, 25)
            alive = wait(lambda s: s['life'] == [0, 0] and all(h > 0 for h in s['hp']) and
                         all(m[:2] == [1, 2] for m in s['mode']), 60)
            lives -= 1
            assert alive['lives'] == lives, alive
            print('PASS both respawn after joint pit wipe; exactly one shared life spent', flush=True)
    finally:
        buttons(0, 0xFFFF)
        buttons(1, 0xFFFF)
        write(diag+0x30, 0)


if __name__ == '__main__':
    main()
