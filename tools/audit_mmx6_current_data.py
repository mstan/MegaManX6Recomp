"""Reproduce original X6 CURRENT producers; source only, never runtime QA."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import inventory_mmx6_coop_content as content

PACK, UNPACK, CURRENT, PLAY = 0x8001BD40, 0x8001BA1C, 0x80070CC4, 0x800CCED0
MEMBERS = {
    2: 'd8bcf3aea6caf1dd4098b681ad912692835d726dfe16fddca779e82d894de607',
    18: '3ae703ad03b2bbc4b71fc09e5f418e1e87ffd49a4a6a4240e69172fb87036166',
    20: '353abfee70d0d12cbdc32d620c5482e15ff26a603e4af58b5d341071ca78a956',
}
SPANS = (
    ('exe', 'native_current_pack', PACK, 0x8001C024,
     '0cd0b74b27b104d034399664381d334dafa5b077061c6eb1ced6484a4daba681'),
    ('exe', 'native_current_unpack', UNPACK, PACK,
     '1ab0bad5c14c9da324c5a3ec480a60e707beb65a118506e82e02ebb9cb8bde73'),
    ('exe', 'native_exit_consumer', 0x8001E32C, 0x8001E6E4,
     'c532803823d419cf6804de1052208f0e5c9f8fb580ceb203b12de4d4157a6cbb'),
    ('exe', 'positive_stage0_exit', 0x8001E394, 0x8001E3B4,
     '94ed65bf87ab94947f6807cfc9d15b8e00b0d623d85e5fa33f602ea90fa9a8ba'),
    ('exe', 'native_report_loader', 0x8001E81C, 0x8001E880,
     'a8311628e312626c49438b39722841abba8d26e51b66dd65750571c3c5c693bb'),
    ('bin2', 'intro_finale_exit_producer', 0x800F65A4, 0x800F65DC,
     '892a71b78f5ee9007907fd493fa83eb8e035432b220b75e99973b0097920a59d'),
    ('bin20', 'report_export_step', 0x800EAC28, 0x800EAD70,
     '5d6660ec91bc61ca59a83572b6bbe51ba3235126bc396472338cde70425c3b7e'),
    ('bin20', 'report_export_dispatch', 0x800EF638, 0x800EF674,
     'ae4a11150a62036e69c1bb98fb9ce8b046cc05fec03f98492f5b9a40eed675e6'),
    ('bin20', 'report_export_dispatch_table', 0x800F3970, 0x800F397C,
     '90f08a9fcf475a75ca1923a6496693c2f06045bdc8f2bbc2fe30ff085e0daf7e'),
)
EXPECTED_CALLERS = (
    ('bin18', 0x800ED15C, 'JAL'),
    ('bin20', 0x800EACB0, 'JAL'),
)
# Persistent slices checked by the existing native current-data reentry case.
# This list describes import semantics; it is not a native preservation result.
IMPORTS = ((0x04,0x70,4),(0x08,0x74,8),(0x10,0x6C,4),(0x14,0x6A,2),
    (0x36,0x5B,2),(0x38,0x61,2),(0x3A,0x60,1),(0x3B,0x5F,1),(0x3C,0x69,1),
    (0x3D,0x8D,2),(0x40,0xCC,4),(0x44,0xD8,0x40),(0x84,0x9E,0x2A),
    (0xB8,0xD2,4),(0xBC,0x168,0x10),(0xCC,0xC9,1),(0xCD,0x438,1),
    (0xCE,0x178,0x2C0),(0x390,0x43C,0x24),(0x3B4,0x465,3))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def window(payload, base, start, end):
    require(all(type(v) is int for v in (base, start, end)) and
            not start & 3 and not end & 3 and base <= start < end <= base+len(payload),
            'Original source span escaped its bounded image')
    return payload[start-base:end-base]


def checked_span(payload, base, name, start, end, expected):
    data = window(payload, base, start, end)
    require(sha(data) == expected, 'Original source span changed: '+name)
    return dict(id=name, address=f'{start:08X}', end_exclusive=f'{end:08X}', bytes=len(data), sha256=expected)


def word(payload, base, address):
    return struct.unpack('<I', window(payload, base, address, address+4))[0]


def direct_calls(payload, base, target):
    """Scan aligned original bytes, including data; no indirect-call closure."""
    require(type(base) is int and not base & 3 and 0 <= base <= 0xFFFFFFFF and
            type(target) is int and not target & 3 and 0 <= target <= 0xFFFFFFFF,
            'Direct-call scan requires aligned 32-bit addresses')
    result = []
    for offset in range(0, len(payload)-3, 4):
        instruction = struct.unpack_from('<I', payload, offset)[0]
        opcode = instruction >> 26
        pc = base+offset
        if opcode in (2, 3) and (((pc+4)&0xF0000000)|((instruction&0x3FFFFFF)<<2)) == target:
            result.append((pc, 'J' if opcode == 2 else 'JAL'))
    return result


def check_callers(found):
    require(tuple(sorted(found)) == EXPECTED_CALLERS,
            'Native CURRENT pack direct caller set changed; require exactly title/card import and mission report')


def load_sources(executable, disc_path):
    original = Path(executable).read_bytes()
    require(sha(original) == content.EXE_SHA256, 'Require the pinned complete original X6 EXE')
    disc = content.RawDisc(Path(disc_path))
    try:
        files = disc.inventory_files()
    finally:
        disc.stream.close()
    require(files['SLUS_013.95'] == original, 'Raw disc EXE differs from the supplied pinned original')
    return original, files['ROCK_X6.BIN']


def audit(executable, archive):
    require(sha(executable) == content.EXE_SHA256, 'Require the pinned complete original X6 EXE')
    require(sha(archive) == content.BIN_SHA256, 'Require the pinned original ROCK_X6.BIN')
    exe = content.Executable(executable)
    members = content.archive_members(archive)
    payloads = {'exe': (executable[2048:2048+exe.size], exe.base)}
    found = [('exe', pc, kind) for pc, kind in direct_calls(*payloads['exe'], PACK)]
    for entry in members:
        begin = entry['sector']*2048
        payload = archive[begin:begin+entry['size']]
        name = 'bin'+str(entry['index'])
        found.extend((name, pc, kind) for pc, kind in direct_calls(payload, content.OVERLAY_BASE, PACK))
        if entry['index'] in MEMBERS:
            require(entry['sha256'] == MEMBERS[entry['index']], 'Original CURRENT-related BIN member changed')
            payloads[name] = payload, content.OVERLAY_BASE
    check_callers(found)
    spans = [dict(region=region, **checked_span(*payloads[region], name, start, end, expected))
             for region, name, start, end, expected in SPANS]
    main, base = payloads['exe']
    # Decode guards supplement full source hashes; no instruction bytes are emitted.
    require(word(main, base, 0x8001BD48) == 0x3C078007 and
            word(main, base, 0x8001BD4C) == 0x24EF0CC4 and
            word(main, base, 0x8001BD74) == 0x24020001 and
            word(main, base, 0x8001BD9C) == 0xA0E20CC4,
            'Pack fixed CURRENT pointer/header1 contract changed')
    require(word(main, base, 0x8001BA24) == 0x00805021,
            'Unpack no longer takes its payload pointer from original a0')
    zero, overlay_base = payloads['bin2']
    require(word(zero, overlay_base, 0x800F65A8) == 0x9043EAFC and
            word(zero, overlay_base, 0x800F65B0) == 0x14600006 and
            word(zero, overlay_base, 0x800F65BC) == 0x24020040 and
            word(zero, overlay_base, 0x800F65C0) == 0xA062CEDF,
            'Original intro dialogue-inactive/positive-exit producer changed')
    intro_table = struct.unpack('<6I', window(zero, overlay_base, 0x800FB938, 0x800FB950))
    require(intro_table == (0x800F2BE4,0x800F2D08,0x800F2EBC,0x800F64FC,0x800F6548,0x800F65A4),
            'Original intro finale state dispatch changed')
    report, overlay_base = payloads['bin20']
    table = struct.unpack('<3I', window(report, overlay_base, 0x800F3970, 0x800F397C))
    require(table == (0x800EAC28,0x800EAD70,0x800EAE98) and
            word(report, overlay_base, 0x800EF644) == 0x80820002 and
            word(report, overlay_base, 0x800EF648) == 0x24633970,
            'Original report-context+2 dispatch/entry0 changed')
    require(all(struct.unpack_from('<H', executable, exe.offset(content.OVERLAY_SELECTOR+stage*4, 2))[0] == member
                for stage, member in ((0,2),(14,18),(15,20))), 'Original stage/overlay selectors changed')
    return dict(schema=1, kind='original_native_current_data_producers_source_audit',
        source_only=True, status='source_mapped_runtime_unverified',
        original=dict(exe_sha256=content.EXE_SHA256, archive_sha256=content.BIN_SHA256,
            members=[members[index] for index in MEMBERS]), source_spans=spans,
        direct_pack_callers=[dict(region=region, address=f'{pc:08X}', instruction=kind, target=f'{PACK:08X}')
                             for region, pc, kind in sorted(found)],
        scan_scope=dict(exe_payload_bytes=exe.size, bin_members=len(members),
            instruction_alignment=4, ops=['J','JAL'], indirect_calls='not proven absent'),
        pack_contract=dict(function=f'{PACK:08X}', arguments='Incoming argument registers ignored; fixed native globals',
            fixed_source=f'{PLAY:08X}', fixed_destination=f'{CURRENT:08X}', header_store='8001BD9C', header_value=1,
            completion='Header is stored before payload copies; require native return and stable observations',
            leaf=True, private_coop_projection='Source routine alone does not establish active campaign ownership'),
        intro_route=dict(stage=0, bin_member=2, finale_dispatch='800F64C0', dispatch_index='actor+6',
            dispatch_table='800FB938', entries=[f'{value:08X}' for value in intro_table],
            final_step='800F65A4', gate='Native dialogue active byte8008EAFC==0',
            positive_exit_store='800F65C0', positive_exit_value=0x40,
            consumer='8001E32C', stage0_branch='8001E394..8001E3B4',
            intermediate=dict(major=0x0B, phase=0, phase2=0, phase3=0, play66=1),
            loader='8001E81C', destination=dict(major=0x0C, stage=15, section=0, checkpoint=0)),
        report_route=dict(bin_member=20, stage=15, dispatcher='800EF638', dispatch_index='signed report-context+2',
            table='800F3970', entries=[f'{value:08X}' for value in table],
            entry0='800EAC28', pack_call='800EACB0',
            sequencing='After native report finalization helper800EE6F4; before later report pages/card-save choice'),
        unpack_contract=dict(function=f'{UNPACK:08X}', argument='a0 points to native payload',
            persistent_imports=[dict(current_offset=hex(saved), play_offset=hex(play), bytes=size)
                                for saved, play, size in IMPORTS],
            exceptions=['Native import does not restore campaign characterPLAY+38 or armorPLAY+5E.',
                        'Native lives are initialized2 or4 from the original parts policy.']),
        important_exports=[dict(name=name, play_offset=hex(play), current_offset=hex(saved), bytes=size)
            for name, play, saved, size in (
                ('shared parts',0x70,0x04,4),('upgrade once mask',0x6C,0x10,4),
                ('per-character maximum HP',0x5B,0x36,2),('per-character maximum energy',0x61,0x38,2),
                ('earned weapon mask',0x60,0x3A,1),('found Reploid states',0xD8,0x44,0x40),
                ('nightmare soul totals',0xD2,0xB8,4),('nightmare consumed matrix',0x178,0xCE,0x2C0))],
        bypass_policy=dict(native_route='Actual intro finale, accepted native dialogue, positive exit, report and stable CURRENT observations',
            fixture='Calling pack or authoring CURRENT would bypass eligibility/earned progress; it cannot qualify boss, exit, acquisition or card I/O.',
            earned_inventory_mailbox='Prerequisite weapon flags only; mailbox9 does not export CURRENT'),
        limits=['Original-source reproduction only; no game was launched by this audit.',
            'No runtime, acquired-progress, boss/finale activation, card or current-import pass.',
            'Eligible header alone does not prove payload completion or independently earned primary-campaign data.',
            'Direct J/JAL scan is bounded source evidence; dynamic/indirect producers are not excluded.',
            'No original executable/archive bytes are emitted.'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-exe', type=Path, required=True)
    parser.add_argument('--disc', type=Path, required=True)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument('--out', type=Path)
    destination.add_argument('--check', type=Path)
    args = parser.parse_args(argv)
    rendered = json.dumps(audit(*load_sources(args.original_exe, args.disc)), indent=2)+'\n'
    if args.check:
        require(args.check.read_text(encoding='utf-8') == rendered, 'CURRENT source audit differs')
    else:
        with args.out.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
