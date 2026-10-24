"""Native keyboard/controller state UI and rewind; no direct load requests.

Gameplay input uses the owned host sampler. Probe saves only inspect the actual
provider after user-path operations; they never stand in for mapped UI input.
"""
import hashlib
import math
from pathlib import Path
import shutil
import struct
import time
import zlib

import coop_debug as debug
import qualify_mmx6_coop_personal_menu as menus
import qualify_mmx6_coop_state as state
import mmx6_owned_keyboard as keyboard_input
import mmx6_coop_state_resources as resource_input
import mmx6_coop_inventory_state as inventory_input


SUCCESS='bounded_mapped_state_controls_observed'


def require(ok,message):
    if not ok:raise debug.DebugError(message)


class PublishedAdapter(menus.OfflineMenuAdapter):
    """Keep the existing native observation windows, replace only transport."""
    def __init__(self,ctx,evidence,timeout=12):
        def control(command,**fields):
            if command=='press':
                require(fields.get('frames')==0 and fields.get('port') in (1,2),
                    'Published state adapter requires a persistent ordinary host hold')
                return ctx['set_input'](fields['port']-1,0xffff^fields['buttons'])
            if command=='clear_input' and 'layer' not in fields:
                require(fields.get('port') in (1,2),'Published state adapter cannot clear another seat')
                return ctx['set_input'](fields['port']-1,0)
            return ctx['request'](command,**fields)
        super().__init__(control,evidence,timeout=timeout)


def operation_result(before,after,operation,slot,expected_ok):
    require(type(before.get('generation')) is int and before.get('pending')==0,
        'Mapped operation needs an idle native completion counter')
    if type(after.get('generation')) is not int or not state.forward(before['generation'],after['generation']):
        return False
    if after.get('pending')!=0:return False
    require((after.get('last_op'),after.get('last_slot'),after.get('last_ok'))==(operation,slot,int(expected_ok)),
        'Mapped operation completed with the wrong operation, slot or disposition')
    return True


def malformed_current_wire(original):
    """Keep current build/framing; forge the next unsupported provider wire."""
    state.parse_state_image(original)  # Bounded, valid current image first.
    header=original[:36];count=struct.unpack_from('<I',original,28)[0]
    at=36;parts=[header];mutated=False
    for _ in range(count):
        tag,flags,size=struct.unpack_from('<IIQ',original,at);at+=16
        payload=original[at:at+size];at+=size
        if tag==0x16:
            raw=bytearray(zlib.decompress(payload[4:]) if flags else payload)
            require(struct.unpack_from('<4I',raw)==(0x504e534d,1,1,0),'Unexpected offline provider framing')
            interface,name_len,payload_len=struct.unpack_from('<III',raw,16)
            start=28+name_len
            require(interface==1 and bytes(raw[28:start])==b'mmx6.local-coop' and start+payload_len==len(raw),
                'Unexpected current co-op provider identity')
            require(struct.unpack_from('<II',raw,start)==(0x53503658,state.HOST_WIRE_SCHEMA),'Expected current internal wire')
            struct.pack_into('<I',raw,start+4,state.HOST_WIRE_SCHEMA+1);mutated=True
            payload=struct.pack('<I',len(raw))+zlib.compress(raw) if flags else bytes(raw)
        parts.extend([struct.pack('<IIQ',tag,flags,len(payload)),payload])
    require(mutated and at==len(original),'Provider mutation did not cover one complete current image')
    return b''.join(parts)


class SlotControls:
    def __init__(self,ctx,evidence,output,*,keyboard=False):
        self.ctx,self.evidence,self.output=ctx,evidence,output
        evidence.update(mapped_controls=[],overlay_observations=[],overlay_captures=[])
        self.keyboard=keyboard_input.OwnedKeyboard(ctx,evidence) if keyboard else None

    def wait(self,test,label,timeout=18):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            value=test()
            if value:return value
            time.sleep(.025)
        raise debug.DebugError(label+': timed out')

    def overlay(self):
        reply=self.ctx['request']('overlay_status')
        self.evidence['overlay_observations'].append(reply)
        return reply

    def capture(self,panel,label):
        path=self.output/(label+'.png')
        reply=self.ctx['request']('overlay_image',panel=panel,path=str(path))
        require(reply.get('ok') is True and path.is_file(),'Host overlay capture did not complete')
        self.evidence['overlay_captures'].append(dict(panel=panel,path=str(path),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),receipt=reply))

    def hold_until(self,bits,test,label):
        receipt=dict(label=label,seat=0,pressed=bits,source='published_host')
        self.evidence['mapped_controls'].append(receipt)
        try:
            receipt['input']=self.ctx['set_input'](0,bits)
            receipt['observed']=self.wait(test,label)
            return receipt['observed']
        finally:self.ctx['set_input'](0,0)

    def open_slot(self,slot):
        require(not self.overlay()['save_menu_open'],'Slot browser was already open')
        if self.keyboard:
            self.keyboard.until('F7',lambda:self.overlay()['save_menu_open'],self.wait,'Win32 F7 opens actual slot browser')
        else:self.hold_until(0x801,lambda:self.overlay()['save_menu_open'],'Select+R1 opens actual slot browser')
        time.sleep(.08)
        for _ in range(12):
            status=self.overlay()
            require(not status['save_unavailable'],'Current local mode blocks the slot browser')
            if status['save_slot']==slot:return
            current=status['save_slot']
            if self.keyboard:
                self.keyboard.until('Right',lambda:self.overlay()['save_slot']!=current,self.wait,'Keyboard slot-browser Right')
            else:self.hold_until(0x20,lambda:self.overlay()['save_slot']!=current,'Actual slot-browser Right')
            time.sleep(.08)
        raise debug.DebugError('Could not navigate to the requested ordinary slot')

    def operation(self,operation,slot,expected_ok=True):
        self.open_slot(slot)
        self.capture('save_states',f'before-mapped-{operation}-{slot}')
        before=self.ctx['request']('savestate_status')
        record=dict(path='mapped_win32_keyboard' if self.keyboard else 'mapped_controller',operation=operation,slot=slot,expected_ok=expected_ok,
            before=before,observations=[])
        self.evidence['operations'].append(record)
        def completed():
            after=self.ctx['request']('savestate_status');record['observations'].append(after)
            if operation_result(before,after,operation,slot,expected_ok):
                record['completion']=after;return after
        if self.keyboard:
            return self.keyboard.until('S' if operation=='save' else 'L',completed,self.wait,'Keyboard '+operation)
        return self.hold_until(0x8000 if operation=='save' else 0x4000,completed,'Mapped '+operation)


def restored_publications(case,saved,label):
    anchor=case.sample(label+' first observation')['observation']['tick']
    restored=case.wait(lambda row:all(state.reduce_private_restore(saved,row,completed_tick=anchor).values()),label)
    checks=state.reduce_private_restore(saved,restored,completed_tick=anchor)
    case.stable_window(label+' remains frozen')
    return restored,checks


def exercise(ctx,*,output,timeout=12,keyboard=False,resource_sources=None,inventory_source=None):
    require(ctx['mode']=='local' and ctx['input_path']=='published_host','Mapped states need the owned local host route')
    output.mkdir(parents=True,exist_ok=False)
    evidence={};ctx['report']['mapped_state']=evidence
    adapter=PublishedAdapter(ctx,evidence,timeout)
    case=state.PrivateStateCase(ctx['request'],output,evidence,timeout=timeout,
        adapter=adapter,input_path='published_host')
    controls=SlotControls(ctx,evidence,output,keyboard=keyboard)
    evidence['control_route']='owned_win32_keyboard' if keyboard else 'published_controller'
    evidence['limits']=['Local exact-image X/P1 + Zero/P2 intro only; physical keyboard hardware and netplay are separate.',
        'Owned Win32/SDL key events use the original host UI; physical hardware is not exercised.' if keyboard else
        'Controller shortcuts use the original host UI. Direct save RPCs only produce read-only provider probes.',
        'Rewind seek duration is a setup heuristic; only actual restored state establishes the outcome.',
        'A missed seek or observer setup failure is not automatically an engine defect.']
    def probe(label,saved):
        state.snapshot_operation(ctx['request'],'save',7,evidence['operations'])
        image=state.copy_slot_image(ctx['candidate'],7,output/(label+'-probe.pst'))
        evidence.setdefault('provider_probes',[]).append(dict(label=label,**image))
        checks=state.reduce_provider_restore(saved,image['inspection'])
        require(all(checks.values()),label+': full provider/static DSP differs from saved paused state')
        return checks
    try:
        if inventory_source:
            inventory_input.prepare(ctx,case,inventory_source)
        case.open_live_window()
        before=case.stable_window('Before mapped keyboard S save' if keyboard else 'Before mapped Square save')
        controls.operation('save',0)
        image=state.copy_slot_image(ctx['candidate'],0,output/'mapped-save.pst')
        evidence['mapped_saved_snapshot']=image;saved=image['inspection']
        state.require_audio_owner_contract(saved)
        reference=case.wait(lambda row:all(state.reduce_private_restore(saved,row,completed_tick=before[0]['observation']['tick']).values()),
            'Native published state after mapped Square save')
        evidence['checks']['keyboard_s_saved_live_private_pools' if keyboard else 'mapped_square_saved_live_private_pools']=True
        evidence['status']='failed_behavior'
        case.resume_and_retire(reference,'before-mapped-load')
        if inventory_source:
            spent=inventory_input.spend(ctx,case,'before-mapped-ammo-load')
            divergence=inventory_input.changed_resources(before[0],spent)
            controls.operation('load',0)
            reference,inventory_checks=restored_publications(case,saved,'Mapped load restores natively spent ammo and selection')
            inventory_checks.update(divergence)
            inventory_checks['personal_ammo_weapon_restored']=state.private_resources(reference)==state.private_resources(before[0])
            require(all(inventory_checks.values()),'Mapped load did not restore genuinely spent ammo and selection')
            evidence['checks'].update({'inventory_'+k:v for k,v in inventory_checks.items()})
            evidence['checks']['inventory_full_provider_probe']=all(probe('inventory-load',saved).values())
            case.resume_and_retire(reference,'before-mapped-hp-load')
        damaged=resource_input.exercise(ctx,case,resource_sources) if resource_sources else None
        controls.operation('load',0)
        reference,checks=restored_publications(case,saved,'Actual keyboard L restores private pools' if keyboard else 'Actual mapped Cross restores private pools')
        evidence['checks'].update(checks)
        if damaged is not None:
            resource_checks=resource_input.restored_resources(before[0],damaged,reference)
            require(all(resource_checks.values()),'Mapped load did not restore genuinely changed personal HP')
            evidence['checks'].update(resource_checks)
        evidence['checks']['keyboard_l_provider_probe' if keyboard else 'mapped_cross_provider_probe']=all(probe('mapped-load',saved).values())

        bad=malformed_current_wire(Path(image['path']).read_bytes());bad_path=output/f'invalid-internal-wire{state.HOST_WIRE_SCHEMA+1}.pst'
        bad_path.write_bytes(bad)
        relative=Path(image['slot_relative_path'])
        require(relative.name.endswith('_slot00.pst'),'Unexpected private state filename')
        target=ctx['candidate']/'saves'/relative.with_name(relative.name.replace('_slot00.pst','_slot01.pst'))
        shutil.copyfile(bad_path,target)
        evidence['malformed_snapshot']=dict(path=str(bad_path),sha256=hashlib.sha256(bad).hexdigest(),
            change=f'Only current provider internal wire{state.HOST_WIRE_SCHEMA} -> unsupported wire{state.HOST_WIRE_SCHEMA+1}; current build header retained')
        controls.operation('load',1,False)
        restored_publications(case,saved,'Mapped malformed load leaves native paused pools intact')
        evidence['checks']['native_malformed_provider_rejection_preserves_state']=all(probe('after-invalid',saved).values())

        rewind=ctx['request']('rewind_status');evidence['rewind_initial']=rewind
        require(rewind['enabled'] and not rewind['title_blocked'],'Local rewind is not enabled/available')
        adapter.wait_counter('tick',240,'Retain original paused private pools in rewind history')
        pause_end=case.stable_window('Original positive private pools retained before rewind divergence')[-1]
        case.resume_and_retire(pause_end,'before-mapped-rewind')
        if inventory_source:
            rewind_spent=inventory_input.spend(ctx,case,'before-mapped-ammo-rewind')
            divergence=inventory_input.changed_resources(before[0],rewind_spent)
            require(all(divergence.values()),'Rewind setup did not genuinely spend personal ammo/change selection')
            evidence['checks'].update({'rewind_inventory_'+k:v for k,v in divergence.items()})
        changed=case.sample('Retired pools and moved Zero before mapped rewind')
        require(not state.private_visible(changed),'Rewind setup did not diverge from the saved live pools')
        rewind=ctx['request']('rewind_status');evidence['rewind_before_open']=rewind
        require(rewind['snaps']>=20,'Insufficient actual rewind history')
        if controls.keyboard:
            controls.keyboard.until('F8',lambda:controls.overlay()['rewind_open'],controls.wait,'Win32 F8 opens actual rewind')
        else:controls.hold_until(5,lambda:controls.overlay()['rewind_open'],'Select+R3 opens actual rewind')
        time.sleep(.1);controls.capture('rewind','mapped-rewind-open')
        delta=(changed['observation']['tick']-pause_end['observation']['tick'])&0xffffffff
        # Overlay-open/capture RPCs also consume presentations before the
        # filmstrip freezes. Seek well inside the retained paused interval,
        # rather than the short original menu-closing transition.
        margin=18 if inventory_source else 12
        steps=math.ceil(delta/8)+margin
        require(12<=steps<=45,'Rewind setup exceeded its retained-history seek bound')
        seconds=.28+.07*(steps-1)
        evidence['rewind_seek_heuristic']=dict(publications_since_paused_window=delta,interval=8,
            desired_steps=steps,margin_steps=margin,held_seconds=seconds,qualification='Actual restored bytes only; duration is not a selected-tick proof')
        if controls.keyboard:controls.keyboard.held('Left',seconds)
        else:
            try:ctx['set_input'](0,0x80);time.sleep(seconds)
            finally:ctx['set_input'](0,0)
        time.sleep(.1);controls.capture('rewind','mapped-rewind-selected')
        if controls.keyboard:
            controls.keyboard.until('Enter',lambda:not controls.overlay()['rewind_open'],controls.wait,'Keyboard Enter accepts rewind')
        else:controls.hold_until(0x4000,lambda:not controls.overlay()['rewind_open'],'Mapped Cross accepts rewind')
        reference,checks=restored_publications(case,saved,'Actual mapped rewind restores positive original private pools')
        evidence['checks'].update({'rewind_'+k:v for k,v in checks.items()})
        if inventory_source:
            evidence['checks']['rewind_personal_ammo_weapon_restored']=state.private_resources(reference)==state.private_resources(before[0])
            require(evidence['checks']['rewind_personal_ammo_weapon_restored'],'Rewind did not restore personal ammo/selection')
        evidence['checks']['mapped_rewind_full_provider_probe']=all(probe('rewind',saved).values())
        case.capture('mapped-rewind-restored-live-pools')
        case.resume_and_retire(reference,'after-mapped-rewind')
        evidence['status']=SUCCESS
        return evidence
    finally:
        for seat in (0,1):
            try:ctx['set_input'](seat,0)
            except Exception as error:evidence.setdefault('cleanup_errors',[]).append(str(error))
