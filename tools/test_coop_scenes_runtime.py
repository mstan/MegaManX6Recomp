"""Private native-script fixture; requires a controllable stage, both alive.

Exercises the original script lock/release and teleport animations. The final
case kills Zero; use a disposable session. Real doors need stage playtesting.
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

    def wait(predicate, seconds=10):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            if predicate():
                return
            time.sleep(.03)
        raise AssertionError(f'Scene timed out: {read(diag+0x38, 8).hex()}')

    def command(cmd, seat=0):
        write(diag+0x52, seat)
        write(diag+0x50, cmd)
        wait(lambda: read(diag+0x50) == b'\0')

    def p2(buttons):
        write(diag+0x34, buttons & 255)
        write(diag+0x35, buttons >> 8)
        write(diag+0x30, 1)

    def body(seat):
        return read(diag+(0x100 if seat else 0x1800), 0x158)

    def retained(seat):
        b = body(seat)
        return b[0x5C], b[0x93], b[0xA8:0xBA]

    assert read(diag+0x38, 2) == b'\0\0', 'Both players must be alive'
    lives = read(0x800CCF09)
    try:
        p2(0xFFFF)
        write(0x800970FC, 11)
        write(diag+0x51, 13)
        command(1)
        for seat in (0, 1):
            before = [retained(s) for s in (0, 1)]
            command(5, seat)
            wait(lambda: read(diag+0x3E, 2) == bytes((seat+1, 3)))
            assert body(seat^1)[3] == 0, 'Passenger still rendered after teleport out'
            time.sleep(.3)
            assert read(diag+0x3F) == b'\x03', 'Passenger returned during script lock'
            command(6)
            wait(lambda: read(diag+0x3E, 2) == b'\0\0')
            assert before == [retained(s) for s in (0, 1)], 'Scene changed HP/ammo/weapon'
            assert body(seat^1)[3] and body(seat^1)[4] == 1
            assert read(0x800CCF09) == lives, 'Scene spent a life'
            print(f'PASS P{seat+1} owns script; partner teleports out/back retaining resources', flush=True)

        p2(0xFFFE)
        wait(lambda: read(diag+0x39) == b'\x02')
        p2(0xFFFF)
        command(5)
        wait(lambda: read(diag+0x3E) == b'\x01')
        assert read(diag+0x3F) == b'\0'
        command(6)
        wait(lambda: read(diag+0x3E) == b'\0')
        assert read(diag+0x39) == b'\x02' and not body(1)[3]
        print('PASS voluntarily absent Zero stays absent across a scene', flush=True)
        p2(0xFFFE)
        wait(lambda: read(diag+0x39) == b'\x03')
        p2(0xFFFF)
        wait(lambda: read(diag+0x39) == b'\0')

        write(diag+0x51, 0x80)
        command(1)
        wait(lambda: read(diag+0x39) == b'\x05')
        command(5)
        wait(lambda: read(diag+0x3E) == b'\x01')
        command(6)
        wait(lambda: read(diag+0x3E) == b'\0')
        assert read(diag+0x39) == b'\x05', 'Scene revived fallen Zero'
        assert read(0x800CCF09) == lives
        print('PASS fallen Zero stays dead across a scene without spending a life', flush=True)
    finally:
        p2(0xFFFF)
        write(diag+0x30, 0)
        request('clear_input')


if __name__ == '__main__':
    main()
