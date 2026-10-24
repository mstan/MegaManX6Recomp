"""Offline reference reducers; no synthetic input is counted as native evidence."""
import struct
import unittest

import mmx6_native_contact_audio as contact


def pool(*,slot=0,phase=1,hp=8,strength=4,pointer=0x800FAA00):
    raw=bytearray(contact.enemies.STRIDE*contact.enemies.SLOTS)
    offset=slot*contact.enemies.STRIDE
    raw[offset:offset+7]=bytes((1,7,0,1,phase,2,0))
    struct.pack_into('<I',raw,offset+0x10,0x800F6540)
    struct.pack_into('<ii',raw,offset+8,544<<16,380<<16)
    struct.pack_into('<I',raw,offset+0x50,pointer)
    raw[offset+0x5C]=hp;raw[offset+0x60]=strength
    return raw


def sample(hp=32,pending=False,terrain=8):
    return dict(player=dict(hp=hp,pending_hit=pending,terrain=terrain,previous_terrain=8,
        timer=100,reaction=1,action=0x11,state=1),actor=dict(address='0x8008ef48'))


class NativeContactTests(unittest.TestCase):
    def test_source_spawner_allocation_and_retry_fields_do_not_change_authored_record(self):
        expected=bytes.fromhex('0007000020027c01')
        for flags in (0,1):
            for retry in (0,0x10,0x20,0x30,0x40,0x50):
                actual=bytearray(expected);actual[0]=flags;actual[3]=retry
                self.assertTrue(contact.placement_matches(expected,actual))
        for offset,value in ((0,2),(1,8),(2,1),(3,1),(3,0x60),(4,0x30)):
            actual=bytearray(expected);actual[offset]=value
            self.assertFalse(contact.placement_matches(expected,actual))

    def test_target_is_bound_to_original_placement_type_and_subtype(self):
        target=contact.TARGETS_BY_STAGE[1]
        actor,pending,count=contact.target_actor(pool(),target)
        self.assertEqual((actor['type'],actor['subtype'],actor['strength']),(7,0,4))
        self.assertIsNone(pending);self.assertEqual(count,1)
        for field,value in (('record',0x800F6548),('object_id',8),('subtype',1)):
            self.assertIsNone(contact.target_actor(pool(),dict(target,**{field:value}))[0])

    def test_pending_first_allocation_is_not_contact_proof(self):
        actor,pending,count=contact.target_actor(pool(phase=0,hp=0,strength=0,pointer=0),contact.TARGETS_BY_STAGE[1])
        self.assertIsNone(actor);self.assertEqual(pending['phase'],0);self.assertEqual(count,1)

    def test_duplicate_authored_instance_is_rejected(self):
        raw=pool();second=pool(slot=1)
        raw[contact.enemies.STRIDE:contact.enemies.STRIDE*2]=second[contact.enemies.STRIDE:contact.enemies.STRIDE*2]
        with self.assertRaises(contact.native.debug.DebugError):
            contact.target_actor(raw,contact.TARGETS_BY_STAGE[1])

    def test_only_committed_hp_loss_counts_and_does_not_claim_caller(self):
        self.assertIsNone(contact.hp_change(sample(),sample(pending=True)))
        self.assertIsNone(contact.hp_change(sample(pending=True),sample(28)))
        self.assertIsNone(contact.hp_change(sample(),sample()))
        row=contact.hp_change(sample(),sample(28))
        self.assertEqual((row['before'],row['after'],row['loss']),(32,28,4))
        self.assertIn('unverified',row['exact_contact_caller_identity'])
        self.assertEqual(contact.hp_change(sample(4),sample(0))['after'],0)

    def test_hazard_or_retry_cannot_qualify_original_enemy_damage(self):
        for before,after in ((sample(28),sample(32)),(sample(),sample(28,terrain=12)),
                             (sample(terrain=3),sample(28))):
            with self.assertRaises(contact.native.debug.DebugError):contact.hp_change(before,after)

    def test_trace_scope_retains_hurt_source_and_native_death_handler(self):
        self.assertTrue({contact.native.SOUND,contact.native.STOP,contact.CONTACT,contact.DEATH} <= contact.TARGETS)

    def test_projectile_damage_does_not_permanently_block_ledge_jump_retry(self):
        player=dict(x=309<<16,hp=31,ground=True,airborne=0,pending_hit=False,reaction_lock=0)
        source=contact.TARGETS_BY_STAGE[0]
        bits,frames=contact.seek_input(player,None,source,stalled=3,jumps=1)
        self.assertEqual((bits,frames),(0x4020,24))
        for fields in ({'hp':0},{'pending_hit':True},{'reaction_lock':1},{'ground':False},{'airborne':1}):
            self.assertEqual(contact.seek_input(dict(player,**fields),None,source,3,1)[0]&0x4000,0)
        self.assertEqual(contact.seek_input(player,None,source,3,8)[0]&0x4000,0)

    def test_shared_death_effect_does_not_substitute_for_character_death_vocal(self):
        def row(number,ret,disposition):
            return dict(record=dict(group=3,record=number),source_call=dict(target=hex(contact.native.SOUND),
                a2=hex(contact.native.reference.PLAYER),ra=hex(ret)),lifetime=dict(disposition=disposition))
        vocal=row(16,0x8003D9BC,'natural_end');effect=row(14,0x8003D9CC,'keyed_off')
        self.assertEqual(contact.death_audio([vocal,effect]),([vocal],[effect]))
        for rows in ([effect],[vocal],[row(16,0x8003D9CC,'natural_end'),effect],
                     [row(16,0x8003D9BC,'keyed_off'),effect],
                     [vocal,row(14,0x8003D9CC,'replaced')]):
            with self.assertRaises(contact.native.debug.DebugError):contact.death_audio(rows)


if __name__ == '__main__':unittest.main()
