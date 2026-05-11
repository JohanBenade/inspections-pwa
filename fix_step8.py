#!/usr/bin/env python3
"""
Fix the post-apply assertion miscount in step8_pdf_latent.py.

The original line:
    assert gen_new.count('encode_latent_photos(data)') == 1
expected the substring to appear once, but after edits G2+G3 it appears
twice in pdf_generator.py:
  1. In the function signature 'def encode_latent_photos(data):' (G2)
  2. In the standalone call 'encode_latent_photos(data)' (G3)

Both occurrences are correct and intentional. Patch the assertion to == 2.

This patch does NOT modify any source files -- only the step8 script.
After running this, re-run step8_pdf_latent.py to apply Step 8 cleanly.
"""
import pathlib
import sys

p = pathlib.Path("step8_pdf_latent.py")
if not p.exists():
    print("ERROR: step8_pdf_latent.py not found in current directory.")
    sys.exit(1)

s = p.read_text()
old = "assert gen_new.count('encode_latent_photos(data)') == 1"
new = "assert gen_new.count('encode_latent_photos(data)') == 2  # def signature + standalone call"

if new in s:
    print("Already patched. Just run: python3 step8_pdf_latent.py")
    sys.exit(0)

assert s.count(old) == 1, "Patch anchor not found exactly once in step8_pdf_latent.py"
p.write_text(s.replace(old, new))
print("[OK] step8_pdf_latent.py patched.")
print("Now re-run: python3 step8_pdf_latent.py")
