"""Preservation without genuine divergence cannot qualify resource restoration."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import mmx6_coop_state_resources as subject


def sample(hp):
    return dict(observation=dict(players=[dict(hp=v,weapon=0,ammo=[288]*9) for v in hp]))


class ResourceRestoreTests(unittest.TestCase):
    def test_primary_sample_does_not_read_the_borrowed_live_player_slot(self):
        body=bytearray(0x158);body[2]=0;body[4]=1;body[0x5c]=32;body[0xe7]=1
        row=dict(p1_body_hex=body.hex(),observation=dict(native_mode=10,native_phase=0,native_timer=77,tick=99))
        case=Mock();case.sample.return_value=row
        client=Mock();client.read.return_value=b'\0\0'
        player=subject.coherent_primary(client,case)
        self.assertEqual((player['character'],player['form'],player['hp'],player['timer']),(0,1,32,77))
        client.read.assert_called_once_with(subject.native_contact.native.reference.PLAY+12,2)

    def test_unchanged_resources_and_only_one_changed_hero_cannot_pass(self):
        saved=sample([32,32])
        for hp in ([32,32],[30,32],[32,28],[0,28],[30,0]):
            self.assertFalse(all(subject.restored_resources(saved,sample(hp),saved).values()))

    def test_both_damaged_heroes_need_their_own_exact_saved_resources(self):
        saved,damaged=sample([32,32]),sample([30,28])
        self.assertTrue(all(subject.restored_resources(saved,damaged,saved).values()))
        self.assertFalse(all(subject.restored_resources(saved,damaged,damaged).values()))
        restored=sample([32,32]);restored['observation']['players'][1]['ammo'][3]-=1
        self.assertFalse(all(subject.restored_resources(saved,damaged,restored).values()))


if __name__=='__main__':unittest.main()
