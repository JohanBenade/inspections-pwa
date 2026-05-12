#!/usr/bin/env python3
"""
extract_smb_routes.py
Dump the two SMB route handler bodies for tomorrow morning's §03 build.

Targets in app/routes/analytics.py:
  - site_meeting_brief_view  (HTML preview at /analytics/site-meeting-brief)
  - site_meeting_brief_pdf   (PDF download at /analytics/site-meeting-brief/pdf)

Walks backward from each `def site_meeting_brief_*(` to capture any
decorators above it, then forward until the next top-level def/class.

Output: ~/Desktop/smb_routes.txt  (Desktop, not /tmp — easy to drag into chat)
"""
import re
from pathlib import Path

SRC = Path("app/routes/analytics.py")
OUT = Path.home() / "Desktop" / "smb_routes.txt"

assert SRC.exists(), f"Source not found: {SRC}"

content = SRC.read_text()
lines = content.split("\n")

# Find candidate function start lines
def_re = re.compile(r"^def\s+site_meeting_brief_(view|pdf)\b")
starts = [i for i, ln in enumerate(lines) if def_re.match(ln)]

if len(starts) != 2:
    print(f"[FAIL] Expected 2 SMB route defs (view + pdf); found {len(starts)} at lines {[s+1 for s in starts]}.")
    print("       Run this manually to investigate:")
    print("         grep -n 'site_meeting_brief' app/routes/analytics.py")
    raise SystemExit(1)

# Backwalk to pick up decorators
def find_block_start(def_line):
    i = def_line - 1
    while i >= 0:
        s = lines[i].strip()
        if s.startswith("@") or s.startswith("#") or s == "":
            i -= 1
            continue
        return i + 1
    return 0

# Forward walk to next top-level def or class (column-0)
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
    name = def_re.match(lines[s]).group(0).replace("def ", "").rstrip("(")
    body = "\n".join(lines[block_start:block_end]).rstrip()
    blocks.append((name, block_start + 1, block_end, body))

# Write to ~/Desktop/smb_routes.txt
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
print(f"     {len(blocks)} functions, {total_lines} lines of code captured.")
print()
print("Functions found:")
for name, ls, le, _ in blocks:
    print(f"  - {name}  (lines {ls}-{le})")
print()
print(f"Drag {OUT} into chat.")
