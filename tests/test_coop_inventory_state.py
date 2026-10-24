"""Resource qualification must not substitute fixture writes for consumption."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import mmx6_coop_inventory_state as subject


def sample(ammo=(288,288),weapons=(0,0),earned=0):
    body=bytearray(0x158);body[0xc9]=earned
    return dict(p1_body_hex=body.hex(),p2_body_hex=body.hex(),
                observation=dict(tick=10,players=[dict(hp=32,weapon=w,ammo=[a]*9)for w,a in zip(weapons,ammo)]))


class InventoryStateTests(unittest.TestCase):
    def test_both_native_ammo_and_selection_must_diverge(self):
        saved=sample()
        self.assertTrue(all(subject.changed_resources(saved,sample((280,264),(1,8))).values()))
        for changed in (sample(),sample((280,288),(1,8)),sample((280,264),(1,0)),sample((288,288),(1,8)),
                        sample((-1,264),(1,8)),sample((280,300),(1,8)),sample((280,264),(1,9))):
            self.assertFalse(all(subject.changed_resources(saved,changed).values()))

    def test_prerequisite_writes_only_the_dedicated_command_and_mask(self):
        client=Mock();client.read.side_effect=[b'original',b'\0']
        ctx=dict(mode='local',input_path='published_host',clients=[client],request=Mock())
        case=Mock();case.evidence={};case.sample.return_value=sample();case.wait.return_value=sample(earned=255)
        source=dict(address=123,bytes=8,code_hex=b'original'.hex(),prerequisite='earned flags only')
        subject.prepare(ctx,case,source)
        self.assertEqual([(c.args,c.kwargs)for c in ctx['request'].call_args_list],[
            (('write_ram',),dict(addr=hex(subject.debug.DIAGNOSTIC_ADDRESS+0x51),val='0xff')),
            (('write_ram',),dict(addr=hex(subject.debug.DIAGNOSTIC_ADDRESS+0x50),val='0x9'))])


if __name__=='__main__':unittest.main()
