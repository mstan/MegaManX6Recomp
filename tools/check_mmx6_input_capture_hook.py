"""Fail closed unless generated native decoder actually emits the observer.

Read one explicit generated C unit, not a directory/drive. This checks source
emission only; compilation and native observation remain separate evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re


def check(source: str) -> dict:
    definitions = list(re.finditer(r"(?m)^void\s+func_80012A34\s*\(CPUState\s*\*\s*cpu\)\s*\{", source))
    if len(definitions) != 1:
        raise ValueError("exactly one generated native decoder definition required")
    start = definitions[0].start()
    following = re.search(r"(?m)^void\s+func_[0-9A-Fa-f]+\s*\(", source[definitions[0].end():])
    end = definitions[0].end() + following.start() if following else len(source)
    function = source[start:end]
    blocks = list(re.finditer(r"(?m)^block_80012C44:\s*$", function))
    if len(blocks) != 1:
        raise ValueError("exact post-decoder block missing/duplicated")
    block_start = blocks[0].end()
    following = re.search(r"(?m)^block_[0-9A-Fa-f]+:", function[block_start:])
    block = function[block_start:block_start + following.start() if following else len(function)]
    hooks = list(re.finditer(r"psx_mod_instruction\s*\(\s*cpu\s*,\s*0x80012C44u?\s*,\s*0x8FBF0010u?\s*\)\s*;", block))
    if len(hooks) != 1 or len(re.findall(r"psx_mod_instruction\s*\(", block)) != 1:
        raise ValueError("exact native input instruction hook missing/duplicated/malformed")
    load = re.search(r"cpu->gpr\[31\]\s*=\s*psx_cyc_load_word\(cpu,\s*cpu->gpr\[29\]\s*\+\s*16,", block)
    if not load or hooks[0].end() > load.start():
        raise ValueError("observer must precede original saved-RA load")
    if "/* 0x80012C44: 0x8FBF0010 */" not in block[load.start():]:
        raise ValueError("original instruction annotation/word unavailable")
    hook_offset = start + block_start + hooks[0].start()
    return {"schema": 1, "scope": "generated-source-emission-only",
            "function": "80012A34", "site": "80012C44", "word": "8FBF0010",
            "hook_line": source.count("\n", 0, hook_offset) + 1,
            "function_sha256": hashlib.sha256(function.encode("utf-8")).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", type=Path, required=True)
    args = parser.parse_args()
    if args.unit.stat().st_size > 64 * 1024 * 1024:
        raise SystemExit("generated unit exceeds bounded source-check size")
    raw = args.unit.read_bytes()
    try:
        result = check(raw.decode("utf-8"))
    except ValueError as error:
        raise SystemExit(f"native input hook emission refused: {error}") from error
    result.update(unit=str(args.unit.resolve()), unit_sha256=hashlib.sha256(raw).hexdigest())
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
