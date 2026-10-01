"""Input-only smoke check for an already running, private co-op development build.

Start a fresh game, clear the opening Alia conversation, and run this in the
clear area before the first enemy. The diagnostic address is printed by the
plugin. No savestate or actor/progression memory is written. Enemy damage and
visual correctness still need the separate gameplay/screenshot checks.
"""
import argparse
import json
import socket
import struct
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--diagnostic', type=lambda s: int(s, 0), default=0x9F080000)
    args = parser.parse_args()

    def request(command, **fields):
        with socket.create_connection(('127.0.0.1', args.port), timeout=5) as conn:
            conn.sendall((json.dumps(dict(id=1, cmd=command, **fields))+'\n').encode())
            result = json.loads(conn.makefile('r').readline())
        if not result.get('ok'):
            raise RuntimeError(result)
        return result

    def read(address, size):
        return bytes.fromhex(request('read_ram', addr=hex(address), len=size)['hex'])

    def write(address, value):
        request('write_ram', addr=hex(address), val=hex(value))

    def p2(buttons):
        write(args.diagnostic+0x34, buttons & 255)
        write(args.diagnostic+0x35, buttons >> 8)
        write(args.diagnostic+0x30, 1)

    def state():
        data = read(args.diagnostic, 44)
        if struct.unpack_from('<I', data)[0] != 0x434F4F50:
            raise RuntimeError('Active co-op diagnostic block not found')
        return dict(ticks=struct.unpack_from('<I', data, 4)[0],
                    xy=struct.unpack_from('<ii', data, 8), action=data[19],
                    timer=struct.unpack_from('<I', data, 36)[0])

    def check(condition, message):
        if not condition:
            raise AssertionError(message)

    # Zero finishes a short native landing animation after the script unlocks.
    deadline = time.monotonic()+3
    while read(0x800970A5, 1) != b'\x02' or state()['action'] != 2:
        check(time.monotonic() < deadline,
              'Both actors must be standing idle after the opening conversation')
        time.sleep(.05)
    try:
        p2(0xFFFF)
        x_start = read(0x800970A8, 8)
        a = state()
        time.sleep(.4)
        b = state()
        check(b['ticks']-a['ticks'] > 10, 'P2 simulation did not advance')
        check(b['ticks']-a['ticks'] == b['timer']-a['timer'],
              'Shared stage timer must advance once per P2 update')
        p2(0xFFDF)  # Right on P2, P1 neutral.
        time.sleep(.22)
        p2(0xFFFF)
        moved = state()
        check(moved['xy'][0] > b['xy'][0], 'Zero did not move right')
        check(read(0x800970A8, 8) == x_start, 'P2 movement moved X')
        p2(0xBFFF)  # Jump.
        time.sleep(.10)
        jumped = state()
        p2(0xFFFF)
        check(jumped['xy'][1] < moved['xy'][1], 'Zero did not jump')
        time.sleep(.8)
        p2(0xDFFF)  # Dash.
        time.sleep(.10)
        dashed = state()
        p2(0xFFFF)
        check(dashed['action'] == 12, 'Zero did not enter native dash')
        time.sleep(.6)
        p2(0x7FFF)  # Saber.
        time.sleep(.12)
        attacked = state()
        p2(0xFFFF)
        check(attacked['action'] == 48, 'Zero did not enter native ground saber')
        check(read(0x800970A8, 8) == x_start, 'P2 actions moved X')
        time.sleep(.7)
        zero_start = state()['xy']
        request('press', buttons=49151, frames=6)
        time.sleep(.12)
        check(struct.unpack('<i', read(0x800970AC, 4))[0] < struct.unpack('<i', x_start[4:])[0],
              'X did not jump from P1 input')
        check(state()['xy'] == zero_start, 'P1 input moved Zero')
        print(json.dumps(dict(result='PASS', idle_ticks=b['ticks']-a['ticks'],
                              p2_move=moved, p2_jump=jumped, p2_dash=dashed,
                              p2_saber=attacked, independent_p1_jump=True), indent=2))
    finally:
        p2(0xFFFF)
        write(args.diagnostic+0x30, 0)
        request('clear_input')


if __name__ == '__main__':
    main()
