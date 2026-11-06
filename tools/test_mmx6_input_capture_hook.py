"""Pure malformed-emission negatives; synthetic C, no regeneration claim."""
import unittest
from check_mmx6_input_capture_hook import check

HOOK = "psx_mod_instruction(cpu, 0x80012C44u, 0x8FBF0010u);\n"
LOAD = "cpu->gpr[31] = psx_cyc_load_word(cpu, cpu->gpr[29] + 16, 31, 0x20000000u);\n/* 0x80012C44: 0x8FBF0010 */\n"
ADDRESS = "uint32_t _mod_ea = psx_mod_memory_address(cpu, 0x80012C44u, 0x8FBF0010u, (uint32_t)(cpu->gpr[29] + 16));\n"
INDIRECT_LOAD = LOAD.replace("cpu->gpr[29] + 16", "_mod_ea")
def fixture(body):
    return "void func_80012A34(CPUState* cpu)\n{\nblock_80012C44:\n" + body + "}\nvoid func_80012C54(CPUState* cpu){}\n"

class HookTests(unittest.TestCase):
    def test_exact_hook_precedes_native_instruction(self):
        self.assertEqual(check(fixture(HOOK + LOAD))["site"], "80012C44")

    def test_current_memory_address_emission_preserves_native_load(self):
        self.assertEqual(check(fixture(HOOK + ADDRESS + INDIRECT_LOAD))["site"], "80012C44")
        for body in (HOOK + INDIRECT_LOAD,
                     HOOK + ADDRESS.replace("+ 16", "+ 20") + INDIRECT_LOAD,
                     HOOK + ADDRESS.replace("0x8FBF0010u", "0x8FBF0014u") + INDIRECT_LOAD,
                     HOOK + ADDRESS.replace("0x80012C44u", "0x80012C40u") + INDIRECT_LOAD,
                     HOOK + ADDRESS + ADDRESS + INDIRECT_LOAD,
                     HOOK + ADDRESS + LOAD,
                     HOOK + ADDRESS + "_mod_ea += 4;\n" + INDIRECT_LOAD,
                     ADDRESS + HOOK + INDIRECT_LOAD,
                     HOOK + INDIRECT_LOAD + ADDRESS,
                     HOOK + ADDRESS + INDIRECT_LOAD.replace("_mod_ea", "_wrong_ea")):
            with self.subTest(body=body), self.assertRaises(ValueError):
                check(fixture(body))

    def test_missing_malformed_duplicate_and_late_hooks(self):
        for body in (LOAD, HOOK.replace("8FBF0010", "8FBF0014") + LOAD,
                     HOOK + HOOK + LOAD, HOOK + LOAD + LOAD, LOAD + HOOK, HOOK,
                     HOOK + LOAD.replace("+ 16", "+ 20")):
            with self.subTest(body=body), self.assertRaises(ValueError):
                check(fixture(body))

    def test_other_function_or_duplicate_decoder_is_not_evidence(self):
        for source in (fixture(LOAD) + "void func_80020000(CPUState* cpu){" + HOOK + "}",
                       fixture(HOOK + LOAD) * 2,
                       fixture(HOOK + LOAD).replace("block_80012C44:", "block_80012C40:")):
            with self.subTest(source=source), self.assertRaises(ValueError):
                check(source)

if __name__ == "__main__":
    unittest.main()
