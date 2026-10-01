"""Two PRIVATE peers: inject local pads through netplay, never the co-op mailbox.

Boots a new game, checks both peers see each seat's movement, and exercises
P2 leave/rejoin over the transport. Host/client ports are mandatory.
"""
import argparse
import json
import socket
import struct
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-port', type=int, required=True)
    parser.add_argument('--guest-port', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--in-game', action='store_true', help='Start in already-idle intro gameplay')
    parser.add_argument('--expected-width', type=int, default=320)
    parser.add_argument('--enhanced', action='store_true', help='Check enhanced intro rendering and actor visibility')
    args = parser.parse_args()
    ports = [args.host_port, args.guest_port]
    args.output.mkdir(parents=True, exist_ok=True)

    def request(peer, cmd, **fields):
        with socket.create_connection(('127.0.0.1', ports[peer]), timeout=10) as conn:
            conn.sendall((json.dumps(dict(id=1, cmd=cmd, **fields))+'\n').encode())
            result = json.loads(conn.makefile('r').readline())
        assert result.get('ok'), result
        return result

    def read(peer, addr, size=1):
        return bytes.fromhex(request(peer, 'read_ram', addr=hex(addr), len=size)['hex'])

    def press(peer, buttons, frames):
        request(peer, 'press', buttons=buttons, frames=frames)

    def snapshot(peer):
        raw = read(peer, 0x9F080000, 0x1958)
        return dict(tick=int.from_bytes(raw[4:8], 'little'),
                    life=list(raw[0x38:0x3A]),
                    xy=[list(struct.unpack_from('<ii', raw, off+8))
                        for off in (0x1800, 0x100)],
                    hp=[raw[off+0x5C] for off in (0x1800, 0x100)],
                    actions=[raw[off+5] for off in (0x1800, 0x100)],
                    mailbox=raw[0x30])

    def wait(predicate, seconds=20):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.05)
        raise AssertionError('Timed out: '+json.dumps([snapshot(p) for p in (0, 1)]))

    def frames(count):
        start = snapshot(0)['tick']
        wait(lambda: snapshot(0)['tick']-start >= count)

    results = []
    try:
        for peer in (0, 1):
            press(peer, 0xFFFF, 60000)
        deadline = time.monotonic()+200
        step = 0
        while not args.in_game and time.monotonic() < deadline:
            state = read(0, 0x800CCED0, 2)
            if state[0] == 10:
                action = read(0, 0x800970A5)[0]
                if action == 2:
                    break
                if action == 20:
                    press(0, 0xBFFF, 6)
            else:
                press(0, 0xFFF7 if step % 3 == 0 else 0xBFFF, 6)
            if step % 15 == 0:
                print('Boot through synchronized host input:', state.hex(), flush=True)
            step += 1
            time.sleep(1)
        if not args.in_game and time.monotonic() >= deadline:
            raise AssertionError('Network boot did not reach intro gameplay')
        wait(lambda: all(snapshot(p)['life'] == [0, 0] for p in (0, 1)))
        frames(90)
        assert all(snapshot(p)['mailbox'] == 0 for p in (0, 1))
        results.append({'initial': [snapshot(p) for p in (0, 1)]})
        for seat in (1, 0):
            before = [snapshot(p) for p in (0, 1)]
            press(seat, 0xFFDF, 20)
            frames(40)
            after = [snapshot(p) for p in (0, 1)]
            print(json.dumps({'seat': seat, 'before': before, 'after': after}), flush=True)
            for peer in (0, 1):
                assert after[peer]['xy'][seat][0] > before[peer]['xy'][seat][0]+(15 << 16)
                # The intro floor has slopes: idle vertical settling is native.
                assert after[peer]['xy'][seat ^ 1][0] == before[peer]['xy'][seat ^ 1][0]
            assert after[0]['xy'] == after[1]['xy'], after
            print(f'PASS seat {seat+1}: remote movement reaches both peers; partner stays put', flush=True)
            results.append({'seat': seat, 'before': before, 'after': after})

        hp = snapshot(0)['hp']
        press(1, 0xFFFE, 100)
        wait(lambda: all(snapshot(p)['life'][1] == 2 for p in (0, 1)))
        frames(20)
        press(1, 0xFFFF, 10)
        frames(15)
        press(1, 0xFFFE, 5)
        wait(lambda: all(snapshot(p)['life'][1] == 0 for p in (0, 1)))
        frames(20)
        assert all(snapshot(p)['hp'] == hp for p in (0, 1))
        print('PASS remote P2 voluntary leave/rejoin preserves health on both peers', flush=True)
        results.append({'rejoined': [snapshot(p) for p in (0, 1)]})
        for peer in (0, 1):
            path = (args.output/f'peer{peer}.png').resolve()
            shot = request(peer, 'screenshot', path=str(path))
            assert shot['width'] == args.expected_width, shot
            if args.enhanced:
                from PIL import Image
                ws = request(peer, 'gpu_state')['ws']
                assert ws['view_anchor'] and ws['bg2d_generations'] > 0, ws
                pixels = Image.open(path).convert('RGB')
                for x in (23, 49):
                    greens = sum(g > r+32 and g > b+32 for r, g, b in
                                 (pixels.getpixel((x, y)) for y in range(24, 100)))
                    assert greens >= 8, ('native player HUD missing or misplaced', peer, x, greens)
                camera = struct.unpack('<h', read(peer, 0x80097202, 2))[0]
                actors = read(peer, 0x8008EF48, 0x1D40)
                revealed = []
                for offset in range(0, len(actors), 0x9C):
                    actor = actors[offset:offset+0x9C]
                    x = struct.unpack_from('<h', actor, 10)[0]
                    if actor[0] and actor[1] == 1 and actor[3] and \
                            camera+320 < x < camera+320+ws['view_right']:
                        revealed.append(x)
                assert revealed, ('intro robot should draw in the right reveal', camera, ws)
                results.append({'peer': peer, 'enhanced': ws, 'revealed_robots': revealed})
        if args.enhanced:
            print('PASS enhanced background, both native HUDs, and intro robot outside the native view', flush=True)
        (args.output/'result.json').write_text(json.dumps(results, indent=2))
    finally:
        for peer in (0, 1):
            try:
                request(peer, 'clear_input')
            except OSError:
                pass  # Preserve the original failure if a peer exited.


if __name__ == '__main__':
    main()
