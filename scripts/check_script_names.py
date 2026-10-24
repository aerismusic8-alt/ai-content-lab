#!/usr/bin/env python3
"""Fail if any script in this directory shadows a standard-library module.

`scripts/queue.py` did exactly that: with `scripts/` on sys.path — which the
MCP server and any `python3 scripts/thing.py` invocation puts it on — `import
queue` resolved to it, so `urllib3` (via `requests`, via the Google libraries)
died with "module 'queue' has no attribute 'LifoQueue'". Anything that imports
`requests` breaks. Run this before adding a script.
"""
import os
import sys
import sysconfig

HERE = os.path.dirname(os.path.abspath(__file__))
stdlib = sysconfig.get_paths()["stdlib"]


def main() -> int:
    names = {os.path.splitext(f)[0] for f in os.listdir(HERE) if f.endswith(".py")}
    names.discard("__init__")
    clashes = sorted(n for n in names
                     if os.path.exists(os.path.join(stdlib, n + ".py"))
                     or os.path.isdir(os.path.join(stdlib, n)))
    for n in clashes:
        print(f"SHADOWS STDLIB: scripts/{n}.py  (breaks `import {n}`)")
    if clashes:
        return 1
    print(f"ok — {len(names)} scripts, none shadows a standard-library module")
    return 0


if __name__ == "__main__":
    sys.exit(main())
