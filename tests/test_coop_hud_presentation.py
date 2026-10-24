"""Final-drawable meter measurements must detect anchor/layout errors."""
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import mmx6_coop_hud_presentation as subject


class HudPresentationTests(unittest.TestCase):
    def test_missing_or_displaced_meter_never_passes_either_layout(self):
        one = dict(x0=22, y1=80)
        self.assertFalse(all(subject.meter_anchors([one], 'stacked').values()))
        for layout, dx, dy in (('stacked', 0, 104), ('side_by_side', 56, 0)):
            two = dict(x0=22+dx, y1=80+dy)
            self.assertTrue(all(subject.meter_anchors([one, two], layout).values()))
            self.assertFalse(all(subject.meter_anchors([one, dict(two, x0=two['x0']+4)], layout).values()))
            self.assertFalse(all(subject.meter_anchors([one, dict(two, y1=two['y1']-4)], layout).values()))

    def test_letterboxed_final_pixels_preserve_native_anchors_at_all_aspects(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'fixture.png'
            for width, height in ((960, 720), (1200, 600), (640, 900)):
                scale = min(width/320, height/240); ox = (width-320*scale)/2; oy = (height-240*scale)/2
                for layout, dx, dy in (('stacked', 0, 104), ('side_by_side', 56, 0)):
                    image = Image.new('RGB', (width, height), (0, 0, 0)); draw = ImageDraw.Draw(image)
                    for x, y0, y1 in ((22, 48, 80), (22+dx, 52+dy, 80+dy)):
                        draw.rectangle((round(ox+x*scale), round(oy+y0*scale),
                                        round(ox+(x+3)*scale)-1, round(oy+y1*scale)-1), fill=(64, 248, 0))
                    image.save(path)
                    measured = subject.measure_meters(path)
                    self.assertEqual(measured['image_size'], [width, height])
                    self.assertTrue(all(subject.meter_anchors(measured['boxes'], layout).values()), (layout, measured))


if __name__ == '__main__':
    unittest.main()
