"""Require the dialogue palette hook in the actual generated native loader."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit',type=Path,required=True)
    args=parser.parse_args()
    if args.unit.stat().st_size>64*1024*1024:raise SystemExit('Generated unit exceeds bounded check size')
    raw=args.unit.read_bytes();source=raw.decode('utf-8')
    functions=list(re.finditer(r'(?m)^void func_8002B3D4\(CPUState\* cpu\)\s*\{',source))
    if len(functions)!=1:raise SystemExit('One generated native palette loader required')
    start=functions[0].start();tail=source[functions[0].end():]
    following=re.search(r'(?m)^void func_[0-9A-F]+\(',tail)
    end=functions[0].end()+following.start() if following else len(source)
    function=source[start:end]
    block=function.find('block_8002B3D4:')
    hooks=list(re.finditer(r'if\s*\(psx_mod_function_entry\(cpu,\s*0x8002B3D4u\)\)\s*return;',function))
    if block<0 or len(hooks)!=1 or hooks[0].end()>block:
        raise SystemExit('Native dialogue palette entry hook missing, duplicated or after original instructions')
    print(json.dumps(dict(scope='generated-native-entry-emission-only',function='8002B3D4',
        unit=str(args.unit.resolve()),unit_sha256=hashlib.sha256(raw).hexdigest(),
        function_sha256=hashlib.sha256(function.encode()).hexdigest())))


if __name__=='__main__':main()
