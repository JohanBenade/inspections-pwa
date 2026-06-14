#!/usr/bin/env python3
"""
fix_total_units_analytics.py
Replaces hardcoded PROJECT_TOTAL_UNITS = 191 with a live-count helper.
Run from repo root: python3 fix_total_units_analytics.py
"""
import io

PATH = "app/routes/analytics.py"

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# --- 1. Replace the constant definition with a helper function ---
OLD_CONST = "PROJECT_TOTAL_UNITS = 191\n"
NEW_HELPER = (
    "def get_project_total_units(tenant_id):\n"
    "    \"\"\"Live count of real 4-bed units (excludes TEST units). Single source of truth.\"\"\"\n"
    "    row = query_db(\n"
    "        \"SELECT COUNT(DISTINCT u.id) AS n FROM unit_real u \"\n"
    "        \"WHERE u.tenant_id = ? AND u.unit_number NOT LIKE 'TEST%'\",\n"
    "        [tenant_id], one=True)\n"
    "    return row['n'] if row else 0\n"
)
assert src.count(OLD_CONST) == 1, "Expected exactly 1 constant definition"
src = src.replace(OLD_CONST, NEW_HELPER)

# --- 2. Replace each usage. tenant_id is in scope at every call site. ---
# There are 6 in-function usages of the bare identifier PROJECT_TOTAL_UNITS.
USAGE = "PROJECT_TOTAL_UNITS"
# After the helper text is inserted, the only remaining occurrences are usages.
n_usages = src.count(USAGE)
# 6 usage lines, but lines 202 and 3148 each reference the identifier twice
# (the `... if PROJECT_TOTAL_UNITS > 0` guard), so 8 string occurrences.
assert n_usages == 8, "Expected 8 remaining usages, found %d" % n_usages
src = src.replace(USAGE, "get_project_total_units(tenant_id)")

# Verify zero bare-identifier usages remain (helper name differs)
assert "PROJECT_TOTAL_UNITS" not in src, "Some PROJECT_TOTAL_UNITS still present"
assert "get_project_total_units(tenant_id)" in src, "Replacement missing"

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("OK: constant -> helper, 6 usages rewired")
