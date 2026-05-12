#!/usr/bin/env python3
"""
Patch for build_smb_section_03.py — remove two over-strict post-flight assertions.

Both assertions check "OLD not in NEW_FILE" but OLD is a substring of NEW by design
(insert-after pattern: NEW = OLD + appended content). The actual replacement DID work;
the assertions are just over-strict. The count-based assertions that follow
(_build_brief_latent count == 2, encode_latent_photos count == 2, etc.) correctly
verify the replacement happened.

Removes:
  Lines 523-525: assert A_ROUTE_OLD not in a_new, ...
  Lines 540-542: assert T_S03_OLD not in t_new, ...

Assert-guarded, idempotent. File written ONLY if all asserts pass.

Run from inspections-pwa repo root.
"""
from pathlib import Path

TARGET = Path("build_smb_section_03.py")
assert TARGET.exists(), f"Expected {TARGET} in cwd. Run from inspections-pwa repo root."

OLD_1 = """    assert A_ROUTE_OLD not in a_new, (
        "Old route anchor still present after replace (replace did nothing)"
    )
"""

OLD_2 = """    assert T_S03_OLD not in t_new, (
        "S03 anchor still present after replace (replace did nothing)"
    )
"""

src = TARGET.read_text()

# Idempotency: both already removed = nothing to do
if OLD_1 not in src and OLD_2 not in src:
    print("[NO-OP] Both assertions already removed. File unchanged.")
    raise SystemExit(0)

# Pre-flight: both must exist exactly once
assert OLD_1 in src, "OLD_1 (route assertion block) not found. Script may have changed."
n1 = src.count(OLD_1)
assert n1 == 1, f"OLD_1 found {n1} times (expected 1). Refusing to write."

assert OLD_2 in src, "OLD_2 (template assertion block) not found. Script may have changed."
n2 = src.count(OLD_2)
assert n2 == 1, f"OLD_2 found {n2} times (expected 1). Refusing to write."

# Apply (remove both blocks)
new_src = src.replace(OLD_1, "")
new_src = new_src.replace(OLD_2, "")

# Post-flight
assert OLD_1 not in new_src, "Post-flight: OLD_1 still present (unexpected)."
assert OLD_2 not in new_src, "Post-flight: OLD_2 still present (unexpected)."
assert len(new_src) < len(src), (
    f"Post-flight: file did not shrink ({len(src)} -> {len(new_src)}). Refusing to write."
)

# Make sure the surrounding structure survived (sanity check)
assert "assert a_new.count('_build_brief_latent(_tenant') == 2" in new_src, (
    "Post-flight: subsequent count assertion missing. Patch may have damaged the file."
)
assert "for i, (old, new) in enumerate(RENUMBERS, 1):" in new_src, (
    "Post-flight: RENUMBERS loop missing. Patch may have damaged the file."
)

# Write
TARGET.write_text(new_src)

bytes_removed = len(src) - len(new_src)
print(f"[OK] Patched {TARGET}")
print(f"     Removed two over-strict assertions ({bytes_removed} bytes).")
print()
print(f"Next: re-run the latent defects deploy command from chat.")
