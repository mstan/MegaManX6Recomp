"""Deliver keyboard events only to the owned SDL game HWND, without focus.

This exercises Win32/SDL key routing, not physical keyboard hardware. No global
key injection, foreground changes, debug UI action or guest-memory write occurs.
"""
import ctypes
from ctypes import wintypes
import os
import time


KEYS={'F7':0x76,'F8':0x77,'S':0x53,'L':0x4c,'Left':0x25,'Right':0x27,'Enter':0x0d}


def key_lparam(scancode,key,up):
    if type(scancode) is not int or not 0<scancode<256 or key not in KEYS:
        raise ValueError('Expected an allowed SDL keyboard key and scan code')
    value=1|(scancode<<16)
    if key in ('Left','Right'):value|=1<<24
    if up:value|=(1<<30)|(1<<31)
    return value


class OwnedKeyboard:
    def __init__(self,ctx,evidence):
        if os.name!='nt':raise ValueError('Owned Win32 keyboard route requires Windows')
        self.ctx,self.evidence=ctx,evidence
        self.pid=ctx['report']['owned_pid']
        if type(self.pid) is not int or self.pid<=0:raise ValueError('Missing owned native PID')
        self.api=ctypes.WinDLL('user32',use_last_error=True)
        self.enumproc=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
        self.api.EnumWindows.argtypes=[self.enumproc,wintypes.LPARAM];self.api.EnumWindows.restype=wintypes.BOOL
        self.api.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
        self.api.GetWindowThreadProcessId.restype=wintypes.DWORD
        for name in ('GetClassNameW','GetWindowTextW'):
            f=getattr(self.api,name);f.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int];f.restype=ctypes.c_int
        self.api.MapVirtualKeyW.argtypes=[wintypes.UINT,wintypes.UINT];self.api.MapVirtualKeyW.restype=wintypes.UINT
        self.api.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
        self.api.PostMessageW.restype=wintypes.BOOL
        ctx['request']('pad_status',port=1) # Existing process/listener ownership gate.
        windows=[]
        def inspect(hwnd,_):
            pid=wintypes.DWORD();self.api.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            if pid.value==self.pid:
                kind=ctypes.create_unicode_buffer(128);title=ctypes.create_unicode_buffer(512)
                self.api.GetClassNameW(hwnd,kind,len(kind));self.api.GetWindowTextW(hwnd,title,len(title))
                if kind.value.startswith('SDL'):windows.append(dict(hwnd=int(hwnd),class_name=kind.value,title=title.value,pid=pid.value))
            return True
        callback=self.enumproc(inspect)
        if not self.api.EnumWindows(callback,0):raise ctypes.WinError(ctypes.get_last_error())
        if len(windows)!=1:raise ValueError('Require exactly one SDL window owned by the native process: '+str(windows))
        self.window=windows[0]
        evidence.update(keyboard_window=self.window,keyboard_events=[],
            keyboard_scope='WM_KEYDOWN/WM_KEYUP to owned SDL HWND; no foreground/global injection or physical-hardware claim')

    def post(self,key,up):
        if key not in KEYS:raise ValueError('Key is outside the bounded state-control route')
        self.ctx['request']('pad_status',port=1)
        pid=wintypes.DWORD();self.api.GetWindowThreadProcessId(self.window['hwnd'],ctypes.byref(pid))
        if pid.value!=self.pid:raise ValueError('SDL window ownership changed')
        scan=self.api.MapVirtualKeyW(KEYS[key],0)
        value=key_lparam(scan,key,up);message=0x101 if up else 0x100
        record=dict(key=key,up=up,pid=self.pid,hwnd=self.window['hwnd'],message=message,
            vk=KEYS[key],scan=scan,lparam=value,monotonic_ns=time.monotonic_ns())
        self.evidence['keyboard_events'].append(record)
        if not self.api.PostMessageW(self.window['hwnd'],message,KEYS[key],value):
            raise ctypes.WinError(ctypes.get_last_error())
        record['posted']=True

    def until(self,key,predicate,wait,label):
        self.post(key,False)
        try:return wait(predicate,label)
        finally:self.post(key,True)

    def held(self,key,seconds):
        if type(seconds) not in (int,float) or not 0<seconds<=4:raise ValueError('Require a bounded keyboard seek hold')
        self.post(key,False)
        try:time.sleep(seconds)
        finally:self.post(key,True)
