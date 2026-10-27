"""Source contract for the actual-TU SDK session-resource regression fixture.

This executes no compiler, fixture, game process or launcher.
"""
import argparse
import importlib.util
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
SDK=ROOT/'psxrecomp-v4'
def function(source,name):
    found=list(re.finditer(r'^.*\b'+re.escape(name)+r'\([^;]*?\)\s*\{',source,re.M))
    if len(found)!=1:raise ValueError('Unique actual function required: '+name)
    start=source.index('{',found[0].start());depth=0
    for end in range(start,len(source)):
        depth+=(source[end]=='{')-(source[end]=='}')
        if not depth:return source[start:end+1]
    raise ValueError('Unterminated function: '+name)

class SessionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin=(ROOT/'src/mods/mmx6_coop_plugin.c').read_text(encoding='utf-8')
        cls.audio=(ROOT/'src/mods/mmx6_coop_jump_audio.inc').read_text(encoding='utf-8')
        cls.activate=function(cls.plugin,'activate');cls.audio_activate=function(cls.audio,'jump_audio_activate')
        cls.memory=(SDK/'runtime/src/memory.c').read_text(encoding='utf-8')
        cls.textures=(SDK/'runtime/src/mod_texture_banks.c').read_text(encoding='utf-8')
        cls.main=(SDK/'runtime/src/main.cpp').read_text(encoding='utf-8')
    def test_real_SDK_boundary_retires_all_ownership_before_activation(self):
        start=self.main.index('auto start_mod_session =')
        text=self.main[start:self.main.index('if (!start_mod_session(',start)]
        self.assertLess(text.index('mod_texture_banks_reset_session()'),text.index('mod_runtime_activate_plugins()'))
        self.assertLess(text.index('psx_mod_memory_reset_session()'),text.index('mod_runtime_activate_plugins()'))
        self.assertIn('mod_memory_used = mod_gpu_dma_memory_used = 0;',function(self.memory,'psx_mod_memory_reset_session'))
        reset=function(self.textures,'mod_texture_banks_reset_session')
        self.assertIn('psx_mod_forget_texture_bank_range(1,65535)',reset)
        self.assertIn('arena_count=0;',reset)
    def test_every_current_session_handle_is_reacquired(self):
        for name,api in(('assets','guest'),('diagnostic','guest'),('packets','texture_packet'),
            ('hud_packets','texture_packet'),('menu_memory','gpu_dma')):
            self.assertRegex(self.activate,r'\b'+name+r'=psx_mod_alloc_'+api+r'_memory\(')
            self.assertNotRegex(self.activate,r'if\s*\(\s*!'+name+r'\s*\)')
        self.assertIn('b->guest=psx_mod_alloc_guest_memory(',self.audio_activate)
        self.assertNotIn('uint32_t address=b->guest',self.audio_activate)
    def test_old_host_cache_ids_and_derived_addresses_retire(self):
        for token in('free(banks[i].pixels)','bank_count=0','ui_bank_count=0',
            'menu_memory=menu_assembly=hud_packets=world_packets=0',
            'assets=assembly=palette_source=active_palette=packets=diagnostic=0',
            'snapshot_discard_prepared()','working_palette_assets_ready=0'):
            self.assertIn(token,self.activate)
        self.assertIn('jump_audio_bound_epoch=jump_audio_owned_epoch=0',self.audio_activate)
    def test_fixture_uses_actual_memory_texture_and_registration_code(self):
        bridge=(ROOT/'tests/mmx6_coop_session_sdk_fixture.c').read_text(encoding='utf-8')
        self.assertIn('#include "memory.c"',bridge)
        self.assertIn('#include "mod_texture_banks.c"',bridge)
        self.assertIn('if(!mod_texture_banks_reset_session()||!psx_mod_memory_reset_session())return 0;',bridge)
        self.assertIn('#include "mod_function_replacements.c"',bridge)
        self.assertIn('psx_mod_clear_function_replacements()',bridge)
        self.assertIn('mod_memory_offset(physical,1,&offset)',bridge)
        self.assertIn('mod_gpu_dma_memory_offset(physical,1,&offset)',bridge)
        self.assertNotRegex(bridge,r'\bint psx_mod_memory_reset_session\(')
    def test_actual_plugin_fixture_checks_ownership_and_current_state(self):
        test=(ROOT/'tests/test_mmx6_coop_session_resources.c').read_text(encoding='utf-8')
        for token in('session<24','activate();allocated()','mod_texture_packet_bank(old_packets+4',
            'mod_texture_bank_pixels(0x6000','snapshot_write(state,n)','snapshot_validate(state,n)',
            'snapshot_read(state,n);snapshot_resources_restored()','psx_mod_memory_snapshot_read(arena,m)',
            'fail_guest_allocation=1','CHECK(!host_buffers)','owners[0]==JUMP_AUDIO_OWNER+1'):
            self.assertIn(token,test)
    def test_fixture_option_boundary_is_exact_and_exercises_current_default(self):
        test=(ROOT/'tests/test_mmx6_coop_session_resources.c').read_text(encoding='utf-8')
        option=function(test,'psx_mod_option_value')
        for token in('"mmx6.local-coop"','"prototype"','"hud_layout"','"doors"',
                     '?"either"','?"stacked"','capacity>strlen(value)','++option_reads'):
            self.assertIn(token,option)
        self.assertIn('hud_offsets(&hud_x,&hud_y)',function(test,'allocated'))
        self.assertIn('option_reads==before+1&&hud_x==0&&hud_y==P2_HUD_Y',
                      function(test,'allocated'))
    def test_both_fixture_variants_have_all_actual_providers(self):
        cmake=(ROOT/'CMakeLists.txt').read_text(encoding='utf-8')
        self.assertRegex(cmake,r'foreach\(_mmx6_visual_kind\b[^)]*\bsession_resources\b')
        self.assertRegex(cmake,r'tests/test_mmx6_coop_\([^)]*\bsession_resources\b[^)]*\)\[\.\]c')
        for token in('tests/mmx6_coop_session_sdk_fixture.c','runtime/src/psx_ram_geometry.c',
            'runtime/src/mod_function_replacements.c','runtime/src")'):
            self.assertIn(token,cmake)
    def test_retained_hardware_references_are_typed_fail_fast_boundaries(self):
        bridge=(ROOT/'tests/mmx6_coop_session_sdk_fixture.c').read_text(encoding='utf-8')
        peripheral=(ROOT/'tests/mmx6_coop_session_peripherals.inc').read_text(encoding='utf-8')
        self.assertIn('#include "mmx6_coop_session_peripherals.inc"',bridge)
        self.assertIn('exit(86)',function(peripheral,'mmx6_session_forbidden'))
        self.assertIn('fflush(stderr)',function(peripheral,'mmx6_session_forbidden'))
        for macro in('F39_VOID0','F39_VOID1','F39_VOID2','F39_VOID3','F39_VOID4','F39_READ0','F39_READ1'):
            line=next(line for line in peripheral.splitlines()if line.startswith('#define '+macro+'('))
            self.assertIn('mmx6_session_forbidden(#name)',line)
        for name in('psx_get_in_exception','ls_read_hook','card_data_writes_check',
                    'render_pass_mmio_read_allowed','render_pass_store_to'):
            self.assertIn('mmx6_session_forbidden("'+name+'")',function(peripheral,name))
        for forbidden in('psx_mod_memory_alloc','psx_mod_gpu_dma_memory_alloc','psx_mod_memory_reset_session',
                          'mod_texture_banks_reset_session','psx_mod_clear_function_replacements'):
            self.assertNotRegex(peripheral,r'\b'+forbidden+r'\(')
        # The pure kernel helper is real SDK code, not another boundary double.
        self.assertIn('runtime/src/kernel_patch_ranges.c',(ROOT/'CMakeLists.txt').read_text(encoding='utf-8'))
        for name in('psx_kernel_patch_cmp','psx_kernel_patch_ends_at'):
            self.assertNotIn(name,peripheral)
    def test_negative_probes_use_actual_memory_routing_and_exact_failure(self):
        peripheral=(ROOT/'tests/mmx6_coop_session_peripherals.inc').read_text(encoding='utf-8')
        probe=function(peripheral,'mmx6_test_session_peripheral_probe')
        self.assertIn('mmio_read8(0x1F801800u)',probe)
        self.assertIn('render_pass_store(0x80010000u,0,4)',probe)
        self.assertIn('cdrom_read(0x1F801800u)',probe)
        file=ROOT/'tools/test_mmx6_coop_session_peripheral_rejection.py'
        spec=importlib.util.spec_from_file_location('fixture_rejection_contract',file)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        # Pure validation only: no compiled fixture or subprocess is run here.
        good=SimpleNamespace(returncode=86,stdout='',stderr='F39 fixture forbidden peripheral: cdrom_read\r\n')
        module.validate_probe(good,'cdrom_read')
        for bad in(SimpleNamespace(returncode=0,stdout='',stderr=good.stderr),
                   SimpleNamespace(returncode=86,stdout='',stderr='unrelated failure\n'),
                   SimpleNamespace(returncode=1,stdout='',stderr=good.stderr),
                   SimpleNamespace(returncode=86,stdout='unexpected output',stderr=good.stderr)):
            with self.assertRaises(ValueError):module.validate_probe(bad,'cdrom_read')
        cmake=(ROOT/'CMakeLists.txt').read_text(encoding='utf-8')
        for token in('mmx6_coop_session_peripheral_rejection_test',
                      '--debug "$<TARGET_FILE:mmx6_coop_session_resources_debug_test>"',
                      '--production "$<TARGET_FILE:mmx6_coop_session_resources_production_test>"'):
            self.assertIn(token,cmake)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--sdk-root',type=Path,default=SDK)
    options,remaining=parser.parse_known_args();SDK=options.sdk_root.resolve(strict=True)
    unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)
