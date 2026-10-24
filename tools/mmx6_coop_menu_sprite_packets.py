"""Native sprite/rectangle paths supplement the retained menu quad reducer.

X's unflipped native draw uses GP0 16x16 sprites; flipped draws use quads.
The first retained reducer is left intact because completed evidence cites its
exact bytes. Callers explicitly install and snapshot this fuller reducer.
"""
from mmx6_coop_menu_continuity import packet_summary as quad_summary


def packet_summary(d,identity):
    result=quad_summary(d,identity)
    page=None;charge=0
    for entry in d['entries']:
        op=int(entry['op'],16);words=[int(v,16) for v in entry['w']]
        if op==0xe1 and words:page=words[0]&0x1f
        family=op&0xfc
        if family in (0x64,0x74,0x7c) and len(words)>=3 and page==5 and words[2]>>16==0x7800:
            result['counts']['x_sheet']+=1
        if family in (0x24,0x2c,0x64,0x74,0x7c) and len(words)>=3 and words[2]>>16 in (0x7801,0x7802):charge+=1
        if family in (0x24,0x2c) and len(words)>4:page=(words[4]>>16)&0x1f
        elif family in (0x34,0x3c) and len(words)>5:page=(words[5]>>16)&0x1f
    result['primary_charge_primitives']=charge
    return result
