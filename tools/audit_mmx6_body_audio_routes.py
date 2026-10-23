"""Pin original Zero body sound records and actor-bound STOP callers.

Source evidence only; this module never launches a title or changes native RAM.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import audit_mmx6_private_action_audio as original

STOPS = (
    (0x800385FC, 5, 0x80038594, 1), (0x800386EC, 5, 0x80038594, 1),
    (0x800387E4, 5, 0x80038788, 1), (0x800388F8, 5, 0x80038788, 1),
    (0x8003B234, 5, 0x8003B218, 1), (0x8003D8BC, 5, 0x8003D8A8, 2),
    (0x8003D8C8, 7, 0x8003D8A8, 2), (0x8003F494, 7, 0x8003F480, 1),
    (0x8003F60C, 7, 0x8003F58C, 1),
)


def expect(actual, expected, label):
    if actual != expected:
        raise ValueError(f"Original body-audio {label} differs")


def prove_routes(exe, zero, banks):
    rows = {(r['group'], r['record']): r for r in original.resolve_records(banks)}
    body = []
    for record, tone in enumerate((1, 3, 4, 5, 6, 7, 8, 9), 1):
        row = rows[1, record]
        voice = 23 if record >= 7 else 22
        expect((row['effective_bank_group'], row['program_high_bit'], row['routing'],
                row['priority'], row['voice_range']), (1, 0, 2, 0, [voice]), 'record routing')
        expect(len(row['tones']), 1, 'single body tone')
        expect((row['tones'][0]['program'], row['tones'][0]['tone']), (0, tone), 'record tone')
        body.append(row)
    stops = []
    for site, record, entry, phase in STOPS:
        expect(exe.word(site), 0x0C005D43, 'STOP call')
        expect(exe.word(site + 4), 0x24050000 | record, 'STOP delay argument')
        group_pc = site - 8 if site in (0x8003D8BC, 0x8003F494) else site - 4
        expect(exe.word(group_pc), 0x24040001, 'STOP group argument')
        if entry == 0x8003F58C:
            expect((exe.word(entry + 12), exe.word(entry + 20)),
                   (0x3C048009, 0x249070A0), 'fixed PLAYER in s0')
            binding = 's0 = 800970A0 (original fixed PLAYER)'
        else:
            expect((exe.word(entry + 4), exe.word(entry + 8)),
                   (0xAFB00010, 0x00808021), 'saved s0 from actor a0')
            binding = 's0 = actor a0; runtime requires exact PLAYER'
        span = b''.join(struct.pack('<I', exe.word(pc)) for pc in range(entry, site + 8, 4))
        stops.append(dict(site=f'{site:08X}', return_address=f'{site+8:08X}', group=1,
            record=record, native_voice=22 if record == 5 else 23, phase=phase,
            actor_binding=binding, source_span=dict(address=f'{entry:08X}', bytes=len(span),
                sha256=hashlib.sha256(span).hexdigest())))
    sounds = []
    for site, record, group_delta, record_delta, actor_delta in (
            (0x80035898, 5, -16, -12, -4), (0x800372B0, 5, -16, -8, -4),
            (0x801EA038, 7, -8, -4, 4), (0x801EA168, 8, -8, -4, 4)):
        word = exe.word if site < original.ZERO_BASE else lambda pc: struct.unpack_from('<I', zero, pc-original.ZERO_BASE)[0]
        expect(word(site), 0x0C005B12, 'SOUND call')
        expect(word(site+group_delta), 0x24040001, 'SOUND group')
        expect(word(site+record_delta), 0x24050000 | record, 'SOUND record')
        expect(word(site+actor_delta), 0x02003021, 'SOUND spatial actor a2=s0')
        sounds.append(dict(site=f'{site:08X}', return_address=f'{site+8:08X}', group=1,
            record=record, actor_argument='a2 = s0; runtime requires exact PLAYER'))
    return dict(schema=1, kind='original_body_audio_routes', source_only=True,
        original_exe_sha256=original.content.EXE_SHA256, original_zero_code_sha256=original.ZERO_CODE_SHA,
        body_records=body, stop_callers=stops, direct_sound_examples=sounds,
        runtime_contract=[
            'Living projected Zero, PLAY10, exact PLAYER spatial actor for body SOUND; child actors excluded.',
            'STOP lacks an actor argument: exact source return address AND s0=PLAYER required.',
            'Phase2 admits only original death-entry STOP5/7; other STOP sites require phase1.',
            'Native groupFF once plus title-owned private voices; foreign private voices preserved.'],
        limits=['Source records/callers do not prove native execution, DSP lifetime, PCM or campaign behavior.',
            'Other effective banks, programs, multivoice, vocal/child families and music remain separate.'])


def audit(exe_path, disc_path):
    return prove_routes(*original.original_sources(exe_path, disc_path))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original-exe', type=Path, required=True)
    p.add_argument('--original-disc', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--check', action='store_true')
    a = p.parse_args(); result = audit(a.original_exe, a.original_disc)
    if a.check:
        if json.loads(a.out.read_bytes()) != result: raise SystemExit('Body audio source audit differs')
    else:
        a.out.write_bytes((json.dumps(result, indent=2)+'\n').encode('utf-8'))
    print(json.dumps(dict(body_records=len(result['body_records']), stop_callers=len(result['stop_callers']), source_only=True)))


if __name__ == '__main__':
    main()
