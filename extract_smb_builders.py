#!/usr/bin/env python3
"""
extract_smb_builders.py
Dump the two large SMB data-builder functions for status/cycle audit:
  - _build_pipeline_report_data
  - _build_brief_prev_desnag

Also grabs any sibling helper named _build_brief_* that's not _build_brief_by_trade
(already in context).

Walks backward to include decorators above each def, forward until the next
top-level def/class/@-decorator.

Output: ~/Desktop/smb_builders.txt  (Desktop — easy to drag into chat)
"""
import re
from pathlib import Path

SRC = Path("app/routes/analytics.py")
OUT = Path.home() / "Desktop" / "smb_builders.txt"

assert SRC.exists(), f"Source not found: {SRC}"

content = SRC.read_text()
lines = content.split("\n")

TARGETS = [
    re.compile(r"^def\s+_build_pipeline_report_data\b"),
    re.compile(r"^def\s+_build_brief_prev_desnag\b"),
    # Any other _build_brief_* helpers (catches new ones too), but skip the
    # two we already have in context.
    re.compile(r"^def\s+_build_brief_(?!by_trade\b|prev_desnag\b)\w+"),
]


def matches_any(line):
    return any(p.match(line) for p in TARGETS)


starts = [i for i, ln in enumerate(lines) if matches_any(ln)]

if not starts:
    print("[FAIL] No target functions found.")
    print("       Run this to investigate:")
    print("         grep -n '^def _build_' app/routes/analytics.py")
    raise SystemExit(1)


def find_block_start(def_line):
    i = def_line - 1
    while i >= 0:
        s = lines[i].strip()
        if s.startswith("@") or s.startswith("#") or s == "":
            i -= 1
            continue
        return i + 1
    return 0


def find_block_end(def_line):
    j = def_line + 1
    end_re = re.compile(r"^(def|class)\s+\w+|^@\w")
    while j < len(lines):
        if end_re.match(lines[j]):
            return j
        j += 1
    return len(lines)


blocks = []
for s in starts:
    block_start = find_block_start(s)
    block_end = find_block_end(s)
    name_match = re.match(r"^def\s+(\w+)", lines[s])
    name = name_match.group(1) if name_match else f"line_{s+1}"
    body = "\n".join(lines[block_start:block_end]).rstrip()
    blocks.append((name, block_start + 1, block_end, body))

dump_parts = []
for name, ls, le, body in blocks:
    dump_parts.append("=" * 78)
    dump_parts.append(f"FUNCTION: {name}")
    dump_parts.append(f"LINES:    {ls} - {le}  (of {len(lines)} total)")
    dump_parts.append("=" * 78)
    dump_parts.append(body)
    dump_parts.append("")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(dump_parts))

total_lines = sum(b[3].count("\n") + 1 for b in blocks)
print(f"[OK] Wrote {OUT}")
print(f"     {len(blocks)} function(s), {total_lines} lines captured.")
print()
print("Functions found:")
for name, ls, le, _ in blocks:
    print(f"  - {name}  (lines {ls}-{le})")
print()
print(f"Drag {OUT} into chat.")
