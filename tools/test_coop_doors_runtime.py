"""Private Yammark boss-door playtest, starting at native checkpoint 2.

Drive the selected player through the real door and chained boss dialogue.
Requires both players alive outside the door; does not set up the checkpoint.
"""
import argparse
import json
import socket
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--seat', type=int, choices=(1, 2), required=True)
    parser.add_argument('--screenshot', help='Save the first frame after both players return')
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

    def buttons(raw):
        if args.seat == 1:
            if raw == 0xFFFF:
                request('clear_input')
            else:
                request('press', buttons=raw, frames=8)
        else:
            write(diag+0x34, raw & 255)
            write(diag+0x35, raw >> 8)
            write(diag+0x30, 1)

    assert read(diag+0x38, 2) == b'\0\0', 'Both players must be alive'
    assert read(0x800CCEDC, 2) == b'\x01\0', 'Requires Yammark'
    lives = read(0x800CCF09)
    seen = set()
    dialogue_seen = False
    deadline = time.monotonic()+60
    try:
        while time.monotonic() < deadline:
            state = read(diag+0x3E, 2)
            if state[0]:
                assert state[0] == args.seat, f'Wrong scene owner {state[0]}'
                seen.add(state[1])
                buttons(0xFFFF)
                if read(0x8008EAFC)[0]:
                    dialogue_seen = True
                    buttons(0xBFFF)
                    time.sleep(.08)
                    buttons(0xFFFF)
            elif seen:
                assert 3 in seen and 4 in seen, f'Missing out/wait/in phases: {seen}'
                assert dialogue_seen, 'Chained boss dialogue was not exercised'
                assert read(diag+0x38, 2) == b'\0\0'
                assert read(0x800CCF09) == lives, 'Door spent a life'
                for offset in (0x100, 0x1800):
                    body = read(diag+offset, 0x158)
                    assert body[3] and body[4] == 1 and body[0x5C]
                if args.screenshot:
                    request('screenshot_file', path=args.screenshot)
                print(f'PASS P{args.seat} owns native door and boss dialogue; partner returns alive', flush=True)
                return
            else:
                buttons(0xFFDF)
            time.sleep(.05)
        raise AssertionError(f'Door timed out; phases {seen}, state {read(diag+0x38, 8).hex()}')
    finally:
        buttons(0xFFFF)
        write(diag+0x30, 0)
        request('clear_input')


if __name__ == '__main__':
    main()
