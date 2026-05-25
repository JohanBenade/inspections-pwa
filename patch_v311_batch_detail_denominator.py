"""Patch v311: Fix batch detail unit denominator to query actual data
instead of hardcoded constants.

The `detail` and `detail_data` routes in batches.py both compute the
C1 checkpoints denominator as `509 - excl_count`, with `excl_count`
including a hardcoded `3` for "ground_only items on upper floors"
(burglar bars). The data shows there are actually 6 such items per
unit in Power Park Phase 3, not 3 -- so upper-floor units' denominator
is over-reported by 3 (e.g. unit 208 C1 shows 506 instead of correct 503).

Fix: query `item_template` once per request to get the real ground_only
count and total items count. Replace the hardcoded 3 and 509 with the
queried values.

Both buggy callsites are character-identical (lines 348-354 in `detail`
and lines 529-535 in `detail_data`), so this patch uses a single
find-replace with count==2 to fix both at once.

Run from repo root:
    python3 patch_v311_batch_detail_denominator.py
"""
import sys

PATH = 'app/routes/batches.py'

OLD = """            excl_count_map = {r['exclusion_list_id']: r['cnt'] for r in el_rows}

    for u in units:
        el_count = excl_count_map.get(u.get('exclusion_list_id'), 0)
        ground_only_skips = 3 if (u.get('floor') or 0) > 0 else 0
        u['excl_count'] = el_count + ground_only_skips
        u['checkpoints_c1'] = 509 - u['excl_count']"""

NEW = """            excl_count_map = {r['exclusion_list_id']: r['cnt'] for r in el_rows}

    # Checkpoint constants: total items + ground_only count (excluded on upper floors).
    # Queried from item_template so the math always tracks real data.
    go_row = query_db(
        "SELECT COUNT(*) AS cnt FROM item_template WHERE floor_condition = 'ground_only'",
        [], one=True)
    ground_only_count = go_row['cnt'] if go_row else 0
    total_row = query_db(
        "SELECT COUNT(*) AS cnt FROM item_template",
        [], one=True)
    items_per_unit = total_row['cnt'] if total_row else 509

    for u in units:
        el_count = excl_count_map.get(u.get('exclusion_list_id'), 0)
        ground_only_skips = ground_only_count if (u.get('floor') or 0) > 0 else 0
        u['excl_count'] = el_count + ground_only_skips
        u['checkpoints_c1'] = items_per_unit - u['excl_count']"""

MARKER = "ground_only_count = go_row['cnt'] if go_row else 0"

with open(PATH, 'r') as f:
    content = f.read()

if MARKER in content:
    print(f'SKIP: v311 patch already applied to {PATH}')
    sys.exit(0)

count = content.count(OLD)
assert count == 2, (
    f'v311: OLD string found {count} times in {PATH} (expected 2: '
    f'detail and detail_data routes). Has the file drifted, or has '
    f'one of the routes already been patched separately?'
)

new_content = content.replace(OLD, NEW)
assert new_content.count(MARKER) == 2, (
    f'v311: MARKER appears {new_content.count(MARKER)} times after '
    f'replace (expected 2)'
)

with open(PATH, 'w') as f:
    f.write(new_content)

print(f'OK: v311 patch applied to {PATH} (both detail and detail_data routes)')
