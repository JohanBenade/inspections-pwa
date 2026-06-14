#!/usr/bin/env python3
"""
v354 code fix -- extend the exclusion-skip guard so a born-skipped item
(prev status 'skipped') with a NULL-reason cycle_excluded_item row is NOT
re-skipped on follow-up cycles. It falls through to Scenario 5
(now-unexcluded -> pending) so the inspector sees it.

Genuine exclusions (non-NULL reason) and exclusion-list items (reason always
NULL but a real list) keep skipping:
  - exclusion-list path: every item gets reason=None here, BUT the guard's
    NULL-reason fall-through ONLY fires for cycle_number > 1 AND prev=='skipped'.
    A real exclusion-list exclusion that was correctly skipped last cycle has
    prev=='skipped' too -- so to avoid un-skipping legitimate list exclusions,
    the NULL-reason fall-through is gated to the cycle_excluded_item path only
    (excl_list_id IS NULL). See guard below.

Surgical: 3 exact-string replacements. ASCII only. Assert-guarded.
RUN ON: MACBOOK
"""
import io, sys

PATH = "app/routes/inspection.py"

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# ---- Replacement 1: init set() -> {} -------------------------------------
OLD1 = "    current_exclusions = set()\n"
NEW1 = "    current_exclusions = {}  # {template_id: reason} (v354)\n"
assert src.count(OLD1) == 1, "R1 init: expected exactly 1 match, got %d" % src.count(OLD1)

# ---- Replacement 2: queries select reason; build dict --------------------
OLD2 = (
    "    if excl_list_id:\n"
    "        excluded_rows = query_db(\"\"\"\n"
    "            SELECT item_template_id FROM exclusion_list_item\n"
    "            WHERE exclusion_list_id = ?\n"
    "        \"\"\", [excl_list_id])\n"
    "    else:\n"
    "        excluded_rows = query_db(\"\"\"\n"
    "            SELECT item_template_id FROM cycle_excluded_item\n"
    "            WHERE cycle_id = ? AND tenant_id = ?\n"
    "        \"\"\", [cycle_id, tenant_id])\n"
    "    if excluded_rows:\n"
    "        current_exclusions = set(r['item_template_id'] for r in excluded_rows)\n"
)
NEW2 = (
    "    if excl_list_id:\n"
    "        # exclusion-list path: a real curated list -- reason is N/A, set None\n"
    "        excluded_rows = query_db(\"\"\"\n"
    "            SELECT item_template_id, NULL AS reason FROM exclusion_list_item\n"
    "            WHERE exclusion_list_id = ?\n"
    "        \"\"\", [excl_list_id])\n"
    "    else:\n"
    "        excluded_rows = query_db(\"\"\"\n"
    "            SELECT item_template_id, reason FROM cycle_excluded_item\n"
    "            WHERE cycle_id = ? AND tenant_id = ?\n"
    "        \"\"\", [cycle_id, tenant_id])\n"
    "    if excluded_rows:\n"
    "        # {template_id: reason}; membership checks below work on dict keys (v354)\n"
    "        current_exclusions = {r['item_template_id']: r['reason'] for r in excluded_rows}\n"
)
assert src.count(OLD2) == 1, "R2 query/build: expected exactly 1 match, got %d" % src.count(OLD2)

# ---- Replacement 3: extend guard with NULL-reason fall-through -----------
OLD3 = (
    "        _prev_for_skip = prev_item_map.get(template_id)\n"
    "        if template_id in current_exclusions and not (\n"
    "            cycle['cycle_number'] > 1\n"
    "            and _prev_for_skip\n"
    "            and _prev_for_skip['status'] == 'pending'\n"
    "        ):\n"
)
NEW3 = (
    "        _prev_for_skip = prev_item_map.get(template_id)\n"
    "        # v354: also fall through (do NOT skip) when this is a follow-up\n"
    "        # cycle, the item was 'skipped' in the prior cycle, AND its\n"
    "        # cycle_excluded_item.reason is NULL (a propagated junk-exclusion,\n"
    "        # not a real one). Gated to the cycle_excluded_item path\n"
    "        # (excl_list_id IS NULL) so curated exclusion-list skips are kept.\n"
    "        _null_reason_born_skip = (\n"
    "            not excl_list_id\n"
    "            and cycle['cycle_number'] > 1\n"
    "            and _prev_for_skip\n"
    "            and _prev_for_skip['status'] == 'skipped'\n"
    "            and current_exclusions.get(template_id) is None\n"
    "        )\n"
    "        if template_id in current_exclusions and not (\n"
    "            cycle['cycle_number'] > 1\n"
    "            and _prev_for_skip\n"
    "            and _prev_for_skip['status'] == 'pending'\n"
    "        ) and not _null_reason_born_skip:\n"
)
assert src.count(OLD3) == 1, "R3 guard: expected exactly 1 match, got %d" % src.count(OLD3)

# Apply
src = src.replace(OLD1, NEW1).replace(OLD2, NEW2).replace(OLD3, NEW3)

# Post-assertions
assert "current_exclusions = {}" in src
assert "SELECT item_template_id, reason FROM cycle_excluded_item" in src
assert "_null_reason_born_skip" in src
assert src.count("current_exclusions = set(") == 0, "old set-build still present"

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("v354 code fix applied OK -- 3 replacements made.")
print("Verify with the grep commands below.")
