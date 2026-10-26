"""The emitted entry hooks must admit every shared-effect replacement."""
from pathlib import Path
import re
import tomllib
import unittest

class SharedEffectEntryProfile(unittest.TestCase):
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
