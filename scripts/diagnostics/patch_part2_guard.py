#!/usr/bin/env python3
# PART 2 -- STRUCTURAL CODE GUARD for CEI skip pollution.
# When an inspection has NO exclusion_list_id (even after batch_unit recovery),
# exclusions must be EMPTY. Previously it fell back to reading cycle_excluded_item
# (CEI), which is the pollution pathway. Rule: "no list => no skips", structural.
#
# Run on MACBOOK from repo root:
#   python3 scripts/diagnostics/patch_part2_guard.py
import io, sys

PATH = "app/routes/inspection.py"

OLD = """    else:
        excluded_rows = query_db(\"\"\"
            SELECT item_template_id, reason FROM cycle_excluded_item
            WHERE cycle_id = ? AND tenant_id = ?
        \"\"\", [cycle_id, tenant_id])
    if excluded_rows:"""

NEW = """    else:
        # v417: NO exclusion list (and none recoverable from batch_unit) means
        # ZERO exclusions -- structural guarantee "no list => no skips". We do
        # NOT fall back to cycle_excluded_item: those rows were polluted by a
        # 2026-05-19 cleanup script and are not a legitimate exclusion source.
        excluded_rows = []
    if excluded_rows:"""

with io.open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

assert OLD in content, "ABORT: expected old block not found verbatim -- inspect file, do not force."
assert content.count(OLD) == 1, "ABORT: old block not unique -- inspect before patching."

content = content.replace(OLD, NEW)

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("PATCHED app/routes/inspection.py -- CEI fallback removed; no-list => empty exclusions.")
