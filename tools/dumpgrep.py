#!/usr/bin/env python3
"""Grep a freeze/starvation dump JSON for keys of interest. Usage: python tools/dumpgrep.py <file> [keywords...]"""
import json, sys

path = sys.argv[1]
kws = [k.lower() for k in (sys.argv[2:] or ["bail","anomaly","reason","frame","current_func","in_exception","stop","sp"])]

with open(path) as f:
    # may be JSONL (first line meta) or single JSON
    first = f.readline()
    try:
        d = json.loads(first)
    except Exception:
        f.seek(0); d = json.load(f)

def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if any(s in k.lower() for s in kws) and not isinstance(v, (dict, list)):
                print(f"{path}{k} = {v}")
            if isinstance(v, (dict, list)):
                walk(v, path + k + ".")
    elif isinstance(o, list) and o and isinstance(o[0], dict):
        walk(o[0], path + "[0].")

walk(d)
