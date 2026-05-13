#!/usr/bin/env python3
"""
Fix: _build_brief_latent SQL comparison fails on isoformat-stored timestamps.

latent_area_note.created_at is stored in isoformat ('2026-05-12T06:34:13.889531+00:00')
but snap_str is in strftime format ('2026-05-12 09:59:00'). String comparison fails
because 'T' (ASCII 84) > ' ' (32), so same-day isoformat dates compare as > snap_str.

Effect: 47 of 48 SR-015 latent notes captured on the snap day were excluded from
today's brief.

Fix: wrap both sides of the comparison with SQLite's datetime() function. SQLite
parses both formats and produces a normalized internal representation, so the
comparison becomes chronologically correct.

Single-line SQL change. Assert-guarded, idempotent.

Run from inspections-pwa repo root.
"""
from pathlib import Path

TARGET = Path("app/routes/analytics.py")
assert TARGET.exists(), f"Expected {TARGET} to exist. Run from inspections-pwa repo root."

OLD = """        WHERE n.tenant_id = ?
          AND n.created_at <= ?
          AND u.unit_number NOT LIKE 'TEST%'"""

NEW = """        WHERE n.tenant_id = ?
          AND datetime(n.created_at) <= datetime(?)
          AND u.unit_number NOT LIKE 'TEST%'"""

src = TARGET.read_text()

# Idempotency
if NEW in src and OLD not in src:
    print("[NO-OP] Fix already applied. File unchanged.")
    raise SystemExit(0)

# Pre-flight
assert OLD in src, (
    "OLD anchor not found in analytics.py. File may have been edited since v295. "
    "Investigate before re-running."
)
n_old = src.count(OLD)
assert n_old == 1, f"OLD found {n_old} times (expected 1). Refusing to write."
assert NEW not in src, "NEW already present (partial prior run?). Investigate."

# Apply
new_src = src.replace(OLD, NEW)

# Post-flight
assert NEW in new_src, "Post-flight: NEW missing after replacement (unexpected)."
assert new_src.count(NEW) == 1, "Post-flight: NEW count != 1 after replacement."
assert OLD not in new_src, "Post-flight: OLD still present after replacement."

# Write
TARGET.write_text(new_src)

print("[OK] Latent created_at comparison normalized.")
print()
print("Old: AND n.created_at <= ?")
print("New: AND datetime(n.created_at) <= datetime(?)")
print()
print("Verify: git --no-pager diff app/routes/analytics.py")
print("Deploy when Alex is paused.")
