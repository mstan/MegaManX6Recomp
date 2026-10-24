"""Packet ownership admission must reject enemy art and unknown host banks."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import mmx6_coop_menu_continuity as subject


class MenuPacketTests(unittest.TestCase):
    identity=dict(assets=0x9f100000,banks=[dict(id=0x6000,source=0x9f100040,tile=0xffff),
                                            dict(id=0x6001,source=0x80103f40,tile=0xffff)])

    def packet(self,op,words):
        return dict(op=hex(op),src='0x000A51BC',w=[hex(w) for w in words])

    def summary(self,*entries):
        return subject.packet_summary(dict(entries=entries,count=len(entries)),self.identity)

    def native_x(self,clut=0x7800,page=0x25):
        # Actual v23 native X quad format retained in local frame2566.
        return self.packet(0x2d,[0x2d000000,0x00a200ba,clut<<16|15,0x00a200c9,
                                 page<<16,0x00b200ba,0x00c0100f,0x00b200c9,0x00201000])

    def bank(self,identity):
        return self.packet(0x34,[0x34808080,0,0,(identity&255)<<24,0,0,(identity>>8)<<24,0,0])

    def test_native_x_texture_page_is_five_and_enemy_palette_never_counts_as_x(self):
        self.assertEqual(self.summary(self.native_x())['counts']['x_sheet'],1)
        self.assertEqual(self.summary(self.native_x(page=0x20))['counts']['x_sheet'],0)
        self.assertEqual(self.summary(self.native_x(clut=0x7843))['counts']['x_sheet'],0)

    def test_host_banks_keep_original_source_character_and_reject_unknown_identity(self):
        row=self.summary(self.bank(0x6000),self.bank(0x6001),self.bank(0x6002))
        self.assertEqual((row['counts']['x_sheet'],row['counts']['zero_sheet']),(1,1))
        self.assertEqual(row['unknown_banks'],[0x6002])

    def test_ui_bank_cannot_substitute_for_either_character(self):
        row=self.summary(self.bank(0x7001))
        self.assertEqual((row['counts']['x_sheet'],row['counts']['zero_sheet'],row['counts']['private_hud']),(0,0,1))

    def test_only_original_hp_quad_anchor_counts_as_primary_hp_bar(self):
        def bar(dx=0,dy=0):
            xy=lambda x,y:((y+dy)<<16)|(x+dx)
            return self.packet(0x38,[0x3800f840,xy(22,16),0xf840,xy(25,16),0xf840,xy(22,80),0xf840,xy(25,80)])
        self.assertEqual(self.summary(bar())['counts']['native_hud'],1)
        self.assertEqual(self.summary(bar(dy=104))['counts']['native_hud'],0)
        self.assertEqual(self.summary(bar(dx=56))['counts']['native_hud'],0)


if __name__=='__main__':unittest.main()
