"""Primary HP/lifecycle/overlap reducers; not native gameplay qualification."""
import struct
import unittest

import mmx6_coop_primary_audio as primary


def row(hp=32,pending=False,life=(0,0)):
    return dict(observation=dict(ready=1,enrolled=1,failed=0,mailbox=0,native_mode=10,native_phase=0,
        pause_owner=0,scene_owner=0,lifecycle=life),players=[
        dict(character=0,form=1,hp=hp,pending_hit=pending,state=1,terrain=8,previous_terrain=8,timer=100,tick=100),
        dict(character=1,form=5,hp=32,pending_hit=False,state=1,terrain=8,previous_terrain=8,timer=100,tick=100)])


def event(seq,frame,kind,voice,bank):
    return dict(seq=seq,frame=frame,kind=kind,v=voice,sample_bank=bank)


class PrimaryTests(unittest.TestCase):
    def test_only_alive_dying_fallen_primary_with_living_Zero_is_admitted(self):
        for life in ((0,0),(4,0),(5,0)):primary.context_checks(row(0 if life[0] else 32,life=life))
        for life in ((1,0),(2,0),(3,0),(0,4),(5,5)):
            with self.assertRaises(primary.audio.AudioQualificationError):primary.context_checks(row(life=life))
        r=row();r['players'][1]['hp']=28;primary.context_checks(r)
        for hp in (0,33):
            r=row();r['players'][1]['hp']=hp
            with self.assertRaises(primary.audio.AudioQualificationError):primary.context_checks(r)

    def test_hazard_pause_or_unready_snapshot_cannot_qualify_primary_audio(self):
        for key,value in (('ready',0),('mailbox',1),('pause_owner',1),('native_mode',9)):
            r=row();r['observation'][key]=value
            with self.assertRaises(primary.audio.AudioQualificationError):primary.context_checks(r)
        r=row();r['players'][0]['terrain']=12
        with self.assertRaises(primary.audio.AudioQualificationError):primary.context_checks(r)

    def test_pending_hit_bit_does_not_fabricate_committed_fatal_history(self):
        rows=[row(),row(30,pending=True),row(30),row(28),row(0)]
        self.assertEqual([r['after'] for r in primary.hp_history(rows)],[30,28,0])
        for rows in ([row(),row(0,pending=True)],[row(),row(28),row(32),row(0)],[row(),row(28)]):
            with self.assertRaises(primary.audio.AudioQualificationError):primary.hp_history(rows)

    def test_hurt_and_attack_need_actual_overlapping_natural_independent_routes(self):
        x=event(0,100,'KEYON',20,0);z=event(1,105,'KEYON',44,31)
        endx=event(2,120,'END_STOP',20,0);endz=event(3,125,'END_STOP',44,31)
        xm=dict(record=dict(group=3,record=0),event=x,observed_sha256='x')
        zm=dict(record=dict(group=3,record=3),event=z,observed_sha256='z')
        r=primary.overlap_pairs([xm],[zm],[x,z,endx,endz])
        self.assertEqual(r['saber_hurt'][0]['overlap_engine_frames'],15)
        self.assertFalse(r['jump_hurt'])
        replaced=event(2,110,'KEYON',20,0)
        self.assertFalse(primary.overlap_pairs([xm],[zm],[x,z,replaced,endx,endz])['saber_hurt'])
        late=dict(z,frame=120)
        self.assertFalse(primary.overlap_pairs([xm],[dict(zm,event=late)],[x,endx,late,endz])['saber_hurt'])

    def test_jump_family_is_independent_and_wrong_route_is_rejected(self):
        x=event(0,100,'KEYON',20,0);z=event(1,101,'KEYON',44,31)
        ex=event(2,120,'END_STOP',20,0);ez=event(3,130,'END_STOP',44,31)
        xm=dict(record=dict(group=3,record=1),event=x,observed_sha256='x')
        zm=dict(record=dict(group=3,record=7),event=z,observed_sha256='z')
        self.assertEqual(len(primary.overlap_pairs([xm],[zm],[x,z,ex,ez])['jump_hurt']),1)
        bad=dict(z,v=20,sample_bank=0);badend=dict(ez,v=20,sample_bank=0)
        with self.assertRaises(primary.audio.AudioQualificationError):
            primary.overlap_pairs([xm],[dict(zm,event=bad)],[x,bad,ex,badend])

    def test_one_body_snapshot_preserves_pending_HP_and_original_reaction(self):
        raw=bytearray(0x158);raw[0x5C]=0x9E;raw[0x63]=4;raw[0x70]=8;raw[0xE7]=1
        struct.pack_into('<i',raw,8,309<<16)
        p=primary.player(raw,dict(native_timer=100,tick=200))
        self.assertEqual((p['hp'],p['pending_hit'],p['reaction'],p['x']),(30,True,4,309<<16))


if __name__=='__main__':unittest.main()
