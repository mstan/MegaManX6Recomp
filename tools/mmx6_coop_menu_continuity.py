"""Read-only completed GP0-frame retention for native X6 menu transitions.

Uses existing Win64 symbols only to read packet arena and immutable sprite-bank
identities from the exact owned image. Never writes guest or process memory.
The owning runner controls lifetime, image/provenance and ordinary host input.
"""
import ctypes
from ctypes import wintypes
import gzip
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import time

import coop_debug as debug
import mmx6_coop_hud_presentation as hud
import mmx6_coop_native_quit as quit_ui

require=hud.require


class OwnedSymbols:
    def __init__(self,pid,exe,expected_sha):
        exe=Path(exe).resolve(strict=True)
        require(hashlib.sha256(exe.read_bytes()).hexdigest()==expected_sha,'Continuity exact owned image changed')
        symbols=subprocess.check_output(['C:/msys64/mingw64/bin/nm.exe','--defined-only',str(exe)],text=True,timeout=30)
        names=('assets','packets','hud_packets','bank_count','banks','p1','p2')
        addresses={}
        for name in names:
            matches=[int(m,16) for m in re.findall(r'^([0-9a-fA-F]+) [bBdD] '+name+'$',symbols,re.M)]
            if name=='banks':matches=[m for m in matches if m==addresses['bank_count']+16]
            require(len(matches)==1,'Ambiguous owned co-op symbol '+name)
            addresses[name]=matches[0]
        raw=exe.read_bytes();pe=struct.unpack_from('<I',raw,0x3c)[0]
        require(raw[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',raw,pe+24)[0]==0x20b,'Expected Win64 PE image')
        image_base=struct.unpack_from('<Q',raw,pe+48)[0]
        self.api=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
        self.api.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];self.api.OpenProcess.restype=wintypes.HANDLE
        self.api.CloseHandle.argtypes=[wintypes.HANDLE]
        self.api.ReadProcessMemory.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
        self.api.ReadProcessMemory.restype=wintypes.BOOL
        self.handle=self.api.OpenProcess(0x410,False,pid)  # QUERY_INFORMATION | VM_READ only.
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        try:
            modules=(wintypes.HMODULE*1024)();needed=wintypes.DWORD()
            psapi.EnumProcessModules.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.HMODULE),wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
            psapi.GetModuleFileNameExW.argtypes=[wintypes.HANDLE,wintypes.HMODULE,wintypes.LPWSTR,wintypes.DWORD]
            if not psapi.EnumProcessModules(self.handle,modules,ctypes.sizeof(modules),ctypes.byref(needed)):raise ctypes.WinError(ctypes.get_last_error())
            path=ctypes.create_unicode_buffer(32768)
            require(psapi.GetModuleFileNameExW(self.handle,modules[0],path,len(path)) and Path(path.value).resolve()==exe,'Process module differs from owned image')
            self.addresses={k:int(modules[0])+v-image_base for k,v in addresses.items()}
        except Exception:
            self.close();raise

    def close(self):
        if getattr(self,'handle',None):self.api.CloseHandle(self.handle);self.handle=None

    def read(self,address,size):
        require(0<size<=4096*56,'Unbounded read-only symbol request')
        result=ctypes.create_string_buffer(size);count=ctypes.c_size_t()
        if not self.api.ReadProcessMemory(self.handle,address,result,size,ctypes.byref(count)) or count.value!=size:raise ctypes.WinError(ctypes.get_last_error())
        return result.raw

    def u32(self,name):return struct.unpack('<I',self.read(self.addresses[name],4))[0]

    def snapshot(self):
        # Arenas are immutable after enrollment. Banks are append-only. Read
        # the announced prefix twice; no live actor-context coherence inferred.
        for _ in range(16):
            count=self.u32('bank_count');require(count<=4096,'Unbounded bank count')
            a=self.read(self.addresses['banks'],max(1,count*56));b=self.read(self.addresses['banks'],len(a))
            if a==b and count==self.u32('bank_count'):break
        else:raise debug.DebugError('No stable immutable bank prefix')
        banks=[]
        for i in range(count):
            source,identity,tile=struct.unpack_from('<IHH',a,i*56)
            require(identity==0x6000+i,'Unexpected native SpriteBank layout')
            banks.append(dict(source=source,id=identity,tile=tile))
        return dict(assets=self.u32('assets'),packets=self.u32('packets'),hud_packets=self.u32('hud_packets'),banks=banks)


def packet_summary(d,identity):
    counts=dict(x_sheet=0,zero_sheet=0,private_hud=0,native_hud=0)
    banks={b['id']:b for b in identity['banks']};unknown=[]
    for e in d['entries']:
        op=int(e['op'],16);src=int(e['src'],16)&0xffffff;w=[int(v,16) for v in e['w']]
        if op&0xfc==0x34 and len(w)>=9:
            bank=(w[3]>>24)|((w[6]>>24)<<8)
            if 0x6000<=bank<0x7000:
                info=banks.get(bank)
                if info is None:unknown.append(bank)
                elif 0x80010000<=info['source']<0x80200000:counts['x_sheet']+=1
                elif identity['assets']<=info['source']<identity['assets']+0x80000:counts['zero_sheet']+=1
            elif 0x7000<=bank<0x8000:counts['private_hud']+=1
        # Original X's resident texture page uses its native CLUT. Original
        # Zero is always expanded to retained host banks in this X/P1 roster.
        if op&0xfc==0x2c and len(w)>=9 and w[2]>>16==0x7800 and (w[4]>>16)&0x1f==5:
            counts['x_sheet']+=1
        # Original HP bars are Gouraud quads with all four x coordinates at
        # native22..25 and y <=80; the alternate P2 bar is at y+104 or x+56.
        if op&0xfc==0x38 and len(w)>=8:
            xy=[(v&0xffff,v>>16) for v in w[1:8:2]]
            if all(22<=x<=25 and 0<=y<=80 for x,y in xy):counts['native_hud']+=1
    return dict(counts=counts,unknown_banks=sorted(set(unknown)),commands=d['count'])


def exercise(ctx,*,output,layout,resource_sources,timeout=18):
    online=ctx['mode']=='netplay'
    require(ctx['mode'] in ('local','netplay') and ctx['input_path']=='published_host','Continuity route requires owned host publication')
    require(len(ctx['clients'])==(2 if online else 1),'Continuity route has wrong peer count')
    if online:
        import mmx6_coop_jump_audio_pair as binding
        binding.validate_context(ctx,ctx['expected_sha256'])
        require(callable(ctx.get('network')) and callable(ctx.get('matched')),'Continuity pair lacks transport validation')
    output.mkdir(exist_ok=False)
    evidence=dict(status='failed_behavior',checks={},captures=[],phases=[],observations=[],limits=[
        'Completed GP0 emission frames plus composed samples; sheet counts do not establish every sprite pixel or effect owner.',
        'Read-only host symbols are Win64 QA only. No game-side instrumentation or guest/process-memory writes.',
        'Current X/P1-Zero/P2 image and intro only; no other-host or physical-device claim.',
    ])
    ctx['report']['menu_continuity']=evidence
    clients=ctx['clients'];both=ctx['both'] if online else lambda f:[f(0)]
    requests=[c.request for c in clients] if online else [ctx['request']]
    readers=[]

    def sample(label):
        def one(i):
            row=quit_ui.observe_native_quit(clients[i],debug)
            row['frame']=requests[i]('frame')['frame'];return row
        rows=both(one);evidence['observations'].append(dict(label=label,peers=rows))
        if online:ctx['network']()
        return rows

    def wait(test,label):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            rows=sample(label)
            if all(test(row) for row in rows):return rows
            time.sleep(.008)
        raise debug.DebugError(label+' timed out')

    def capture(label):
        evidence['captures'].extend(both(lambda i:dict(label=label,peer=i,**debug.capture_present(clients[i],output/(f'peer-{i}-'+label+'.png'),request=requests[i]))))

    def collect(phase,end,peer):
        request=requests[peer]
        phase['ring_before']=request('gpu_ring_stats');start=phase['start_frame']
        require(phase['ring_before']['oldest_frame']<start and phase['ring_before']['newest_frame']>end,'Transition evicted or incomplete before dump')
        phase['identity']=identity=readers[peer].snapshot();frames=[];directory=output/(f'peer-{peer}-'+phase['label']);directory.mkdir()
        for f in range(start,end+1):
            d=request('gpu_frame_dump',frame=f,count=65536)
            require(0<d['count']<65536,'Empty or truncated completed GPU frame')
            with gzip.open(directory/(str(f)+'.json.gz'),'wt',encoding='utf-8') as stream:json.dump(d,stream,separators=(',',':'))
            frames.append(dict(frame=f,first_seq=d['entries'][0]['seq'],last_seq=d['entries'][-1]['seq'],**packet_summary(d,identity)))
        phase['frames']=frames;phase['end_frame']=end;phase['ring_after']=request('gpu_ring_stats')
        require(phase['ring_after']['oldest_frame']<start,'Transition evicted during collection')
        phase['world_frames']=[f['frame'] for f in frames if f['counts']['x_sheet'] or f['counts']['zero_sheet']]
        phase['one_sheet_missing']=[f['frame'] for f in frames if bool(f['counts']['x_sheet'])!=bool(f['counts']['zero_sheet'])]
        phase['private_hud_missing']=[f['frame'] for f in frames if f['counts']['native_hud'] and not f['counts']['private_hud']]
        phase['unknown_banks']=[f['frame'] for f in frames if f['unknown_banks']]
        phase['ui_with_gameplay_hud']=[f['frame'] for f in frames if not (f['counts']['x_sheet'] or f['counts']['zero_sheet']) and (f['counts']['native_hud'] or f['counts']['private_hud'])]
        require(all(a['last_seq']+1==b['first_seq'] for a,b in zip(frames,frames[1:])),'GPU command sequence has a gap')
        print(json.dumps(dict(peer=peer,phase=phase['label'],frames=len(frames),world=len(phase['world_frames']),one_sheet_missing=phase['one_sheet_missing'],hud_missing=phase['private_hud_missing'])),flush=True)

    def phase(label,seat,bits,predicate):
        before=sample(label+' before');p=dict(label=label,before=before,peers=[dict(label=label,start_frame=row['frame']-2) for row in before]);evidence['phases'].append(p)
        try:
            ctx['set_input'](seat,bits);p['terminal']=wait(predicate,label)
        finally:ctx['set_input'](seat,0)
        capture(label)
        # Wait for another completed GPU frame without advancing the world via
        # a debug step or local emulator pause.
        tails=sample(label+' completed tail anchor')
        deadline=time.monotonic()+timeout
        while True:
            rows=sample(label+' completed frame tail')
            if all(row['frame']>=old['frame']+3 for row,old in zip(rows,tails)):break
            require(time.monotonic()<deadline,'GPU frame tail timed out');time.sleep(.008)
        for peer,record in enumerate(p['peers']):collect(record,rows[peer]['frame']-2,peer)
        if online:ctx['matched']('Native menu continuity '+label)
        return p

    try:
        for i in range(len(clients)):
            peer=ctx['report']['peers'][i] if online else dict(owned_pid=ctx['report']['owned_pid'],directory=str(ctx['candidate']))
            readers.append(OwnedSymbols(peer['owned_pid'],Path(peer['directory'])/'mmx6-runtime.exe',ctx['expected_sha256']))
        if not online:hud.mapped.PublishedAdapter(ctx,evidence,timeout).settle_idle()
        initial=sample('Native continuity preflight')
        require(all(not row['observation']['pause_owner'] and row['native_play_phase']==0 for row in initial),'Continuity needs healthy initial gameplay')
        capture('initial-world');evidence['initial_identity']=[reader.snapshot() for reader in readers]
        for owner in (0,1):
            phase(f'owner{owner}-open',owner,8,lambda r:quit_ui.owned_ready(r,owner))
            phase(f'owner{owner}-close',owner,8,lambda r:r['native_play_phase']==0 and r['fade']==0 and not r['observation']['pause_owner'])
        phase('p1-open-for-quit',0,8,lambda r:quit_ui.owned_ready(r,0))
        phase('p1-quit-page-one',0,1,lambda r:quit_ui.owned_ready(r,0,page=0,choice=0))
        phase('p1-choose-quit',0,0x40,lambda r:quit_ui.owned_ready(r,0,page=0,choice=1))
        phase('p1-quit-page-two',0,0x4000,lambda r:quit_ui.owned_ready(r,0,page=1,choice=1))
        phase('p1-cancel-second',0,0x4000,lambda r:quit_ui.owned_ready(r,0,page=0,choice=0))
        phase('p1-cancel-first',0,0x4000,lambda r:quit_ui.owned_ready(r,0))
        phase('p1-resume-after-quit',0,8,lambda r:r['native_play_phase']==0 and r['fade']==0 and not r['observation']['pause_owner'])
        phases=[peer for phase in evidence['phases'] for peer in phase['peers']]
        evidence['checks'].update(all_completed_frames_retained=True,no_unknown_host_banks=all(not p['unknown_banks'] for p in phases),both_character_sheets_whenever_either_draws=all(not p['one_sheet_missing'] for p in phases),private_hud_whenever_native_hp_bar_draws=all(not p['private_hud_missing'] for p in phases),ui_only_frames_suppress_gameplay_hud=all(not p['ui_with_gameplay_hud'] for p in phases))
        require(all(evidence['checks'].values()),'Completed native transition packet check failed')
        evidence['status']=hud.SUCCESS
        return evidence
    finally:
        for reader in readers:reader.close()
        for seat in (0,1):ctx['set_input'](seat,0)
