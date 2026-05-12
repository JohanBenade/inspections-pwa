#!/usr/bin/env python3
"""
Phase 1: SMB cutoff shift from Tue 00:00 SAST to Tue 11:59 SAST.

Single-line code change in analytics.py:L5518 (plus matching comment update at L5517).

Effect: SMB brief includes inspection reviews up to Tue 11:59 SAST instead of Tue 00:00 SAST.
Allows Tuesday-morning review activity to land in today's brief.

Downstream (all inherit automatically, no further edits needed):
  - snapshot_utc        (analytics.py:L5519)
  - snapshot_str        (analytics.py:L5520)
  - prev_week_utc       (analytics.py:L5521) -- relative offset, shifts with snapshot_utc
  - prev_week_str       (analytics.py:L5522)
  - SMB view route      (analytics.py:L6772-L6773) -- derives from data['snapshot_str']
  - SMB pdf route       (analytics.py:L6799-L6800) -- derives from data['snapshot_str']
  - Pipeline dashboard  (analytics.py:L6843-L6849) -- derives via _build_pipeline_report_data() call

Pre-flight asserts every anchor. Post-flight asserts every replacement.
Idempotent: aborts cleanly with [NO-OP] if already applied.
File written ONLY if all asserts pass.

Run from inspections-pwa repo root.
"""

from pathlib import Path

TARGET = Path("app/routes/analytics.py")
assert TARGET.exists(), f"Expected {TARGET} to exist. Run from inspections-pwa repo root."

OLD_BLOCK = """        # Snapshot moment = Tue 00:00 SAST (= Mon 23:59:59 frozen)
        snapshot_sast = snapshot_mon + _td(days=1)"""

NEW_BLOCK = """        # Snapshot moment = Tue 11:59 SAST (allows Tuesday morning reviews to land in today's brief)
        snapshot_sast = snapshot_mon + _td(days=1, hours=11, minutes=59)"""

src = TARGET.read_text()

# Idempotency: NEW already present and OLD gone = already applied
if NEW_BLOCK in src and OLD_BLOCK not in src:
    print("[NO-OP] Cutoff shift already applied. File unchanged.")
    raise SystemExit(0)

# Pre-flight: OLD must exist exactly once
assert OLD_BLOCK in src, (
    "OLD_BLOCK not found in analytics.py. File may have been edited since v295 dump. "
    "Investigate before re-running."
)
n_old = src.count(OLD_BLOCK)
assert n_old == 1, (
    f"OLD_BLOCK appears {n_old} times in analytics.py (expected exactly 1). Refusing to write."
)

# Pre-flight: NEW must not already exist (would indicate partial prior run)
assert NEW_BLOCK not in src, (
    "NEW_BLOCK already present (partial prior run?). Investigate."
)

# Apply
new_src = src.replace(OLD_BLOCK, NEW_BLOCK)

# Post-flight asserts
assert NEW_BLOCK in new_src, "Post-flight: NEW_BLOCK missing after replacement (unexpected)."
assert new_src.count(NEW_BLOCK) == 1, "Post-flight: NEW_BLOCK count != 1 after replacement."
assert OLD_BLOCK not in new_src, "Post-flight: OLD_BLOCK still present after replacement."
assert len(new_src) > 0, "Post-flight: empty file output. Refusing to write."

# Write (only reached if all asserts pass)
TARGET.write_text(new_src)

print(f"[OK] Applied cutoff shift to {TARGET}")
print()
print("Old: snapshot_sast = snapshot_mon + _td(days=1)                        # Tue 00:00 SAST")
print("New: snapshot_sast = snapshot_mon + _td(days=1, hours=11, minutes=59)  # Tue 11:59 SAST")
print()
print("Next: verify locally with -> git --no-pager diff app/routes/analytics.py")
print("Then (when Alex is paused) commit + push with the deploy command from chat.")
