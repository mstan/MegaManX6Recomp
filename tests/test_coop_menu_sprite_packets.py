"""Both original facing paths and both charge primitive families count."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import mmx6_coop_menu_sprite_packets as subject


class NativeSpriteTests(unittest.TestCase):
    def reduce(self,*rows):
        entries=[dict(op=hex(op),src='0x000A51BC',w=[hex(w) for w in words]) for op,words in rows]
        return subject.packet_summary(dict(count=len(entries),entries=entries),dict(assets=0x9f100000,banks=[]))

    def test_unflipped_x_requires_actual_native_draw_mode_and_own_clut(self):
        sprite=(0x7d,[0x7d000000,0x00a20061,0x78000000])
        self.assertEqual(self.reduce((0xe1,[0xe1000045]),sprite)['counts']['x_sheet'],1)
        self.assertEqual(self.reduce((0xe1,[0xe1000044]),sprite)['counts']['x_sheet'],0)
        self.assertEqual(self.reduce(sprite)['counts']['x_sheet'],0)
        self.assertEqual(self.reduce((0xe1,[0xe1000045]),(0x7d,[0x7d000000,0,0x78430000]))['counts']['x_sheet'],0)

    def test_polygon_texture_page_updates_inherited_sprite_mode(self):
        sprite=(0x7d,[0x7d000000,0,0x78000000])
        quad=(0x2d,[0x2d000000,0,0x78430000,0,0x00240000,0,0,0,0])
        self.assertEqual(self.reduce((0xe1,[0xe1000045]),quad,sprite)['counts']['x_sheet'],0)

    def test_original_charge_sprite_and_quad_are_independent_of_body_counts(self):
        row=self.reduce((0x7d,[0x7d000000,0,0x7802f000]),(0x2d,[0x2d000000,0,0x78010000,0,0,0,0,0,0]))
        self.assertEqual(row['primary_charge_primitives'],2)
        self.assertEqual(row['counts']['x_sheet'],0)


if __name__=='__main__':unittest.main()
