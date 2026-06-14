#!/usr/bin/env python3
"""
v355 fix: Top 50 denominator excludes TEST units.

Root cause (live-verified): _build_top_50_data denominator counts the `unit`
table with no test filter. unit table holds TEST999 (id fce163c3, unit_type
'4-Bed', phase-003) which unit_real does not. -> denominator 191, numerator 190
-> "190 of 191". Adding NOT LIKE 'TEST%' to the denominator query (only) brings
it to 190, matching the cohort table. Same-table, symmetric, no hardcode.

ASCII-only. Single targeted string replace. Assert-guarded.
RUN ON: MACBOOK (from repo root).
"""
import io, sys

PATH = "app/routes/analytics.py"

OLD = (
    "    # Total 4-Bed units in PH3 (denominator for \"X of N\")\n"
    "    total_row = query_db(\"\"\"\n"
    "        SELECT COUNT(*) AS n FROM unit u\n"
    "        WHERE u.tenant_id = ? AND u.phase_id = ? AND u.unit_type = '4-Bed'\n"
    "    \"\"\", [tenant_id, phase_id], one=True)\n"
)

NEW = (
    "    # Total 4-Bed units in PH3 (denominator for \"X of N\")\n"
    "    # v355: exclude TEST units (e.g. TEST999) so denominator matches cohort table.\n"
    "    total_row = query_db(\"\"\"\n"
    "        SELECT COUNT(*) AS n FROM unit u\n"
    "        WHERE u.tenant_id = ? AND u.phase_id = ? AND u.unit_type = '4-Bed'\n"
    "        AND u.unit_number NOT LIKE 'TEST%'\n"
    "    \"\"\", [tenant_id, phase_id], one=True)\n"
)

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

assert OLD in src, "OLD denominator block not found verbatim - aborting, no write."
assert src.count(OLD) == 1, "OLD block not unique - aborting."
assert NEW not in src, "NEW block already present - already applied, aborting."

src = src.replace(OLD, NEW)

# Post-replace guards
assert NEW in src, "NEW block missing after replace - aborting."
assert "NOT LIKE 'TEST%'" in src, "TEST guard missing after replace - aborting."

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("OK: Top 50 denominator now excludes TEST units.")
print("Verify next with: grep -n \"NOT LIKE 'TEST%'\" app/routes/analytics.py")
