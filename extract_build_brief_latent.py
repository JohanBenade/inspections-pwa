#!/usr/bin/env python3
"""
Extract _build_brief_latent from app/routes/analytics.py and write
to /tmp/build_brief_latent_dump.txt for Claude to read.
"""
import re
from pathlib import Path

SRC = Path("app/routes/analytics.py")
OUT = Path("/tmp/build_brief_latent_dump.txt")

assert SRC.exists(), "analytics.py not found"

src = SRC.read_text()

# Find _build_brief_latent function. It ends at the next def at the same indent level.
match = re.search(r'\ndef _build_brief_latent\b.*?(?=\ndef |\Z)', src, re.DOTALL)
assert match, "_build_brief_latent not found"

OUT.write_text(match.group(0))
print(f"[OK] Extracted {len(match.group(0))} chars to {OUT}")
print(f"Copy to Desktop: cp {OUT} ~/Desktop/")
