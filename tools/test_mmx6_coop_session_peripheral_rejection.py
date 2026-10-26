"""Run only the compiled resource fixture's authored forbidden-path probes.

This is a unit fixture, with no launcher, disc, guest gameplay or native saves.
Each variant must visibly reject actual memory.c MMIO/render routing and a
direct device callback; normal resource tests run independently in CTest.
"""
import argparse
from pathlib import Path
import subprocess

EXPECTED={
    'mmio-route':'psx_devices_mmio_sync',
    'render-route':'render_pass_store_to',
    'device':'cdrom_read',
}

def validate_probe(result,expected):
    marker='F39 fixture forbidden peripheral: '+expected+'\n'
    if result.returncode!=86 or result.stdout or result.stderr.replace('\r\n','\n')!=marker:
        raise ValueError('Forbidden fixture path did not fail with exact exit86/marker: '+
                         repr((result.returncode,result.stdout,result.stderr)))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--debug',type=Path,required=True)
    parser.add_argument('--production',type=Path,required=True)
    args=parser.parse_args()
    for fixture in(args.debug,args.production):
        fixture=fixture.resolve(strict=True)
        if not fixture.is_file():raise ValueError('Actual fixture executable required')
        for probe,expected in EXPECTED.items():
            result=subprocess.run([str(fixture),'--peripheral-probe',probe],capture_output=True,
                                  text=True,encoding='utf-8',timeout=10,check=False)
            validate_probe(result,expected)
            print(f'{fixture.name}: {probe} -> exact exit86 {expected}',flush=True)

if __name__=='__main__':main()
