"""Owned-window HUD captures and native personal-menu transitions.

No guest-memory or fixture writes. Window sizing affects only the exact owned
SDL HWND. Original gameplay changes HP; original Start opens/closes menus.
"""
import ctypes
from ctypes import wintypes
import time

import coop_debug as debug
import mmx6_coop_mapped_state as mapped
import mmx6_coop_state_resources as resources

state = mapped.state
require = mapped.require
SUCCESS = 'native_hud_presentation_captured_review_pending'
SIZES = ((960, 720), (1200, 600), (640, 900), (960, 720))
TRACE_TARGETS = (0x80025FB0, 0x80026028, 0x80022960)


def meter_anchors(boxes, layout, *, tolerance=1.1):
    require(layout in ('stacked', 'side_by_side'), 'Unknown HUD layout')
    if len(boxes) != 2:
        return dict(two_native_meters=False, matching_native_anchor=False)
    first, second = sorted(boxes, key=(lambda b: b['y1']) if layout == 'stacked' else (lambda b: b['x0']))
    dx, dy = (0, 104) if layout == 'stacked' else (56, 0)
    return dict(two_native_meters=True, matching_native_anchor=
                abs(second['x0']-first['x0']-dx) <= tolerance and
                abs(second['y1']-first['y1']-dy) <= tolerance)


def measure_meters(path):
    """Measure native bright HP fill, preserving the original composed PNG."""
    from PIL import Image
    with Image.open(path) as source:
        image = source.convert('RGB')
    width, height = image.size
    scale = min(width/320, height/240)
    ox, oy = (width-320*scale)/2, (height-240*scale)/2
    pixels = image.load(); columns = {}
    for x in range(round(ox+8*scale), round(ox+100*scale)):
        ys = []
        for y in range(round(oy+8*scale), round(oy+225*scale)):
            r, g, b = pixels[x, y]
            if g > 180 and b < 80 and g+10 >= r:
                ys.append(y)
        if len(ys) >= 8*scale:
            columns[x] = ys
    require(columns, 'No native HP fill found in composed image')
    cutoff = max(map(len, columns.values()))*.40
    xs = sorted(x for x, ys in columns.items() if len(ys) >= cutoff)
    groups = []
    for x in xs:
        if not groups or x > groups[-1][-1]+1:
            groups.append([])
        groups[-1].append(x)
    boxes = []
    for group in groups:
        if not .5*scale <= len(group) <= 8*scale:
            continue
        ys = sorted({y for x in group for y in columns[x]})
        runs = []
        for y in ys:
            if not runs or y > runs[-1][-1]+6*scale:
                runs.append([])
            runs[-1].append(y)
        for run in runs:
            if run[-1]-run[0] < 8*scale:
                continue
            area = sum(sum(run[0] <= y <= run[-1] for y in columns[x]) for x in group)
            boxes.append(dict(x0=(group[0]-ox)/scale, x1=(group[-1]+1-ox)/scale,
                              y0=(run[0]-oy)/scale, y1=(run[-1]+1-oy)/scale,
                              native_fill_area=area/(scale*scale)))
    return dict(image_size=[width, height], viewport=dict(x=ox, y=oy, scale=scale), boxes=boxes)


class OwnedWindow:
    def __init__(self, ctx, evidence):
        self.keyboard = mapped.keyboard_input.OwnedKeyboard(ctx, evidence)
        self.ctx, self.evidence, self.api = ctx, evidence, self.keyboard.api
        self.api.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.api.GetClientRect.restype = wintypes.BOOL
        self.api.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        self.api.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.api.AdjustWindowRectEx.argtypes = [ctypes.POINTER(wintypes.RECT), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.AdjustWindowRectEx.restype = wintypes.BOOL
        self.api.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.api.SetWindowPos.restype = wintypes.BOOL
        evidence['window_resizes'] = []

    def client_size(self):
        rect = wintypes.RECT()
        if not self.api.GetClientRect(self.keyboard.window['hwnd'], ctypes.byref(rect)):
            raise ctypes.WinError(ctypes.get_last_error())
        return [rect.right-rect.left, rect.bottom-rect.top]

    def resize(self, width, height):
        require((width, height) in SIZES, 'Window dimensions are outside this bounded capture case')
        self.ctx['request']('pad_status', port=1)
        hwnd = self.keyboard.window['hwnd']; pid = wintypes.DWORD()
        self.api.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        require(pid.value == self.keyboard.pid, 'SDL window ownership changed before resize')
        rect = wintypes.RECT(0, 0, width, height)
        style = self.api.GetWindowLongPtrW(hwnd, -16) & 0xffffffff
        extended = self.api.GetWindowLongPtrW(hwnd, -20) & 0xffffffff
        if not self.api.AdjustWindowRectEx(ctypes.byref(rect), style, False, extended):
            raise ctypes.WinError(ctypes.get_last_error())
        # NOMOVE | NOZORDER | NOACTIVATE: preserve hidden state and owner focus.
        if not self.api.SetWindowPos(hwnd, None, 0, 0, rect.right-rect.left, rect.bottom-rect.top, 0x0016):
            raise ctypes.WinError(ctypes.get_last_error())
        deadline = time.monotonic()+8
        while time.monotonic() < deadline:
            info = self.ctx['request']('video_info')
            if self.client_size() == [width, height] and [info['window_w'], info['window_h']] == [width, height]:
                self.evidence['window_resizes'].append(dict(requested=[width, height], actual=self.client_size(), video=info))
                time.sleep(.08)
                return info
            time.sleep(.025)
        raise debug.DebugError('Owned SDL/window renderer dimensions did not converge')


def exercise(ctx, *, output, layout, resource_sources, timeout=18):
    require(ctx['mode'] == 'local' and ctx['input_path'] == 'published_host', 'HUD case needs the owned local sampler')
    require(layout in ('stacked', 'side_by_side'), 'Unknown HUD layout')
    output.mkdir(parents=True, exist_ok=False)
    evidence = {}; ctx['report']['hud_presentation'] = evidence
    adapter = mapped.PublishedAdapter(ctx, evidence, timeout)
    case = state.PrivateStateCase(ctx['request'], output, evidence, timeout=timeout,
                                  adapter=adapter, input_path='published_host')
    window = OwnedWindow(ctx, evidence)
    evidence.update(layout=layout, status='failed_setup', menu_sequences=[], meter_captures=[],
                    limits=['Actual local final-window captures; physical input, other OS/hosts and netplay remain separate.',
                            'Pixel meter extraction checks native fill anchors; character art and menu transitions require visual review.'])

    def capture(label, *, meter=False):
        before = case.sample(label+' before composed capture')
        receipt = debug.capture_present(ctx['clients'][0], output/(label+'.png'), request=ctx['request'])
        after = case.sample(label+' after composed capture')
        record = dict(label=label, **receipt, native_before=before, native_after=after, video=ctx['request']('video_info'))
        evidence['captures'].append(record)
        if meter:
            measurement = measure_meters(receipt['path']); checks = meter_anchors(measurement['boxes'], layout)
            record.update(measurement=measurement, checks=checks)
            evidence['meter_captures'].append(record)
            require(measurement['image_size'] == [record['video']['drawable_w'], record['video']['drawable_h']],
                    'Composed image is not the actual final drawable size')
            require(all(checks.values()), 'Native P1/P2 meter anchors differ from selected layout')
        return record

    def start(owner, label):
        # Capture immediately after host publication: waiting for a complete
        # menu-input window would skip the first world-draw/fade interval.
        before = case.sample(label+' before original Start')
        try:
            ctx['set_input'](owner, 8)
            receipt = debug.capture_present(ctx['clients'][0], output/(label.replace(' ', '-')+'-earliest.png'),
                                            request=ctx['request'])
        finally:
            ctx['set_input'](owner, 0)
        after = case.sample(label+' after earliest composed frame')
        evidence['inputs'].append(dict(seat=owner, pressed=8, label=label, source='published_host',
                                       before_tick=before['observation']['tick'], after_tick=after['observation']['tick']))
        record = dict(label=label+' earliest', **receipt, native_before=before, native_after=after,
                      video=ctx['request']('video_info'))
        evidence['captures'].append(record)
        return record

    try:
        adapter.settle_idle(); window.resize(960, 720)
        capture('healthy-default-window', meter=True)
        for owner in (0, 1):
            adapter.wait_counter('native_timer', 8, 'Healthy settle before owner menu')
            ctx['request']('fntrace_arm_clear')
            for target in TRACE_TARGETS:
                ctx['request']('fntrace_arm', target=hex(target))
            ctx['request']('fntrace_clear')
            sequence = dict(owner=owner, opening=[], closing=[])
            evidence['menu_sequences'].append(sequence)
            sequence['earliest_opening'] = start(owner, 'Owner'+str(owner)+' opens native menu')
            for index in range(6):
                sequence['opening'].append(capture(f'owner{owner}-opening-{index}'))
            opened = case.wait(lambda r: r['observation']['native_phase'] == 2 and
                              r['observation']['pause_owner'] == owner+1 and r['native_menu_state'][0] == 1,
                              'Native owner menu becomes input-ready')
            sequence['input_ready'] = opened
            sequence['paused'] = capture(f'owner{owner}-paused')
            sequence['earliest_closing'] = start(owner, 'Owner'+str(owner)+' closes native menu')
            for index in range(8):
                sequence['closing'].append(capture(f'owner{owner}-closing-{index}'))
            resumed = case.wait(lambda r: r['observation']['native_phase'] == 0 and not r['observation']['pause_owner'],
                               'Native owner menu returns to gameplay')
            sequence['resumed'] = resumed
            sequence['trace'] = ctx['request']('fntrace_dump', count=4096, seq_lo='0')
            require(sequence['trace']['seq_hi'] <= 4096, 'Menu render trace was evicted')
            ctx['request']('fntrace_arm_clear')
            require(state.private_resources(opened) == state.private_resources(resumed), 'Menu presentation changed actor resources')
            capture(f'owner{owner}-resumed', meter=True)
        evidence['checks']['both_original_menu_owners_complete_and_preserve_resources'] = True
        adapter.settle_idle()
        resources.exercise(ctx, case, resource_sources)
        for index, (width, height) in enumerate(SIZES):
            window.resize(width, height)
            capture(f'damaged-aspect-{index}-{width}x{height}', meter=True)
        evidence['checks']['all_final_drawable_meter_anchors'] = all(all(c['checks'].values()) for c in evidence['meter_captures'])
        evidence['checks']['both_native_hp_values_changed'] = evidence['native_resource_damage']['checks']['both_native_hp_values_diverged']
        evidence['status'] = SUCCESS
        return evidence
    finally:
        for actor in (0, 1):
            try:
                ctx['set_input'](actor, 0)
            except Exception as error:
                evidence.setdefault('cleanup_errors', []).append(str(error))
        try:
            ctx['request']('fntrace_arm_clear')
        except Exception as error:
            evidence.setdefault('cleanup_errors', []).append(str(error))
