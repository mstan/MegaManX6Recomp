"""Native entry profiles must admit the shared-effect and armor replacements."""
from pathlib import Path
import os
import re
import tomllib
import unittest

class SharedEffectEntryProfile(unittest.TestCase):
    def test_both_door_native_predicate_and_default_are_declared(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'src/mods/mmx6_coop_plugin.c').read_text(encoding='utf-8')
        self.assertIn('psx_mod_set_function_replacement(0x80050C88,door_eligibility)', source)
        self.assertIn('psx_mod_set_function_replacement(0x80050DFC,door_update)', source)
        for config in ('game.toml', 'packaging/release/game.toml'):
            profile = tomllib.loads((root / config).read_text(encoding='utf-8'))
            entries = [int(a, 16) for a in profile['recompiler']['mod_function_entry_funcs']]
            self.assertEqual(entries.count(0x80050C88), 1)
            self.assertEqual(entries.count(0x80050DFC), 1)
        manifest = tomllib.loads((root / 'mods/preloaded/packages/mmx6.local-coop/0.0.1/manifest.toml').read_text())
        option = next(o for o in manifest['option'] if o['id'] == 'doors')
        self.assertEqual((option['feature'], option['type'], option['default']),
                         ('prototype', 'choice', 'either'))
        self.assertEqual([c['value'] for c in option['choice']], ['either', 'both'])

    @unittest.skipUnless(os.environ.get('MMX6_COOP_DOOR_GENERATED_UNIT'),
                         'set MMX6_COOP_DOOR_GENERATED_UNIT to regenerated unit containing func_80050C88')
    def test_actual_generated_door_predicate_entry(self):
        source = Path(os.environ['MMX6_COOP_DOOR_GENERATED_UNIT']).read_text(encoding='utf-8')
        for address in ('80050C88', '80050DFC'):
            match = re.search(rf'(?ms)^void func_{address}\(CPUState\* cpu\)\n\{{(.*?)(?=^void |\Z)', source)
            self.assertIsNotNone(match)
            entry = match[1].split(f'block_{address}:', 1)[0]
            for hook in ('psx_mod_function_entry', 'psx_mod_try_function_replacement'):
                self.assertEqual(len(re.findall(
                    rf'if \({hook}\(cpu, 0x{address}u\)\) return;', entry)), 1)

    def test_private_view_draw_entry_is_emitted(self):
        root = Path(__file__).resolve().parents[1]
        for config in ('game.toml', 'packaging/release/game.toml'):
            with self.subTest(config=config):
                profile = tomllib.loads((root / config).read_text(encoding='utf-8'))
                entries = [int(address, 16) for address in
                           profile['recompiler']['mod_function_entry_funcs']]
                self.assertEqual(entries.count(0x80066744), 1,
                                 'compiled DrawOTag must reach private-view admission')

    @unittest.skipUnless(os.environ.get('MMX6_COOP_VIEW_GENERATED_UNIT'),
                         'set MMX6_COOP_VIEW_GENERATED_UNIT to the actual full_28.c')
    def test_actual_generated_private_view_entry(self):
        source = Path(os.environ['MMX6_COOP_VIEW_GENERATED_UNIT']).read_text(encoding='utf-8')
        match = re.search(r'(?ms)^void func_80066744\(CPUState\* cpu\)\n\{(.*?)(?=^void |\Z)', source)
        self.assertIsNotNone(match, 'actual native DrawOTag function is required')
        entry = match[1].split('block_80066744:', 1)[0]
        for hook in ('psx_mod_function_entry', 'psx_mod_try_function_replacement'):
            self.assertEqual(len(re.findall(
                rf'if \({hook}\(cpu, 0x80066744u\)\) return;', entry)), 1,
                f'{hook} must precede the native DrawOTag body')

    def test_shared_ride_armor_replacement_is_emitted(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'src/mods/mmx6_coop_plugin.c').read_text(encoding='utf-8')
        required = re.findall(
            r'psx_mod_set_function_replacement\((0x[0-9A-Fa-f]+),ride_tick\)', source)
        self.assertEqual(required, ['0x80020A08'])
        for config in ('game.toml', 'packaging/release/game.toml'):
            with self.subTest(config=config):
                profile = tomllib.loads((root / config).read_text(encoding='utf-8'))
                declared = [int(address, 16) for address in
                            profile['recompiler']['mod_function_entry_funcs']]
                self.assertEqual(declared.count(0x80020A08), 1,
                                 'native AOT armor entry must consult ride_tick')

    @unittest.skipUnless(os.environ.get('MMX6_COOP_RIDE_GENERATED_UNIT'),
                         'set MMX6_COOP_RIDE_GENERATED_UNIT to the actual generated full_04.c')
    def test_actual_generated_ride_entry(self):
        source = Path(os.environ['MMX6_COOP_RIDE_GENERATED_UNIT']).read_text(encoding='utf-8')
        match = re.search(r'(?ms)^void func_80020A08\(CPUState\* cpu\)\n\{(.*?)(?=^void |\Z)', source)
        self.assertIsNotNone(match, 'actual native armor function is required')
        entry = match[1].split('block_80020A08:', 1)[0]
        for hook in ('psx_mod_function_entry', 'psx_mod_try_function_replacement'):
            self.assertEqual(len(re.findall(
                rf'if \({hook}\(cpu, 0x80020A08u\)\) return;', entry)), 1,
                f'{hook} must precede the native armor body')

    def test_native_callback_replacements_are_emitted(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'src/mods/mmx6_coop_plugin.c').read_text(encoding='utf-8')
        required = {int(address, 16) for address in re.findall(
            r'psx_mod_set_function_replacement\((0x[0-9A-Fa-f]+),shared_effect_callback\)', source)}
        profile = tomllib.loads((root / 'game.toml').read_text(encoding='utf-8'))
        declared = {int(address, 16) for address in profile['recompiler']['mod_function_entry_funcs']}
        self.assertTrue(required)
        self.assertFalse(required - declared, [hex(address) for address in required - declared])

if __name__ == '__main__':
    unittest.main()
