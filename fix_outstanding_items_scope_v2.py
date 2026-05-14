#!/usr/bin/env python3
"""
Re-run of fix_outstanding_items_scope with relaxed post-flight assertion.

Previous version asserted total count of 'AND i.cycle_number >= 2' == 2,
which fails because other helpers in analytics.py already use that
predicate. Replace the count check with a delta check (after - before = 2).
"""
from pathlib import Path

ANALYTICS = Path("app/routes/analytics.py")
assert ANALYTICS.exists()

OLD = """    try:
        defect_rows = conn.execute(\"\"\"
            SELECT u.block, u.floor, u.unit_number,
                   at.area_name, at.area_order,
                   ct.category_name AS trade, ct.category_order,
                   it.item_description, it.item_order,
                   COALESCE(NULLIF(d.reviewed_comment,''), NULLIF(d.raw_comment,''), d.original_comment) AS description,
                   d.raised_cycle_number, d.created_at
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id AND it.tenant_id = d.tenant_id
            JOIN category_template ct ON it.category_id = ct.id AND ct.tenant_id = d.tenant_id
            JOIN area_template at ON ct.area_id = at.id AND at.tenant_id = d.tenant_id
            JOIN unit_real u ON d.unit_id = u.id AND u.tenant_id = d.tenant_id
            WHERE d.tenant_id = ? AND d.status = 'open'
            ORDER BY u.block, u.floor, CAST(u.unit_number AS INTEGER),
                     at.area_order, ct.category_order, it.item_order
        \"\"\", (tenant_id,)).fetchall()

        latent_rows = conn.execute(\"\"\"
            SELECT u.block, u.floor, u.unit_number,
                   at.area_name, at.area_order,
                   lan.note_html, lan.cycle_number, lan.created_at
            FROM latent_area_note lan
            JOIN area_template at ON lan.area_template_id = at.id AND at.tenant_id = lan.tenant_id
            JOIN unit_real u ON lan.unit_id = u.id AND u.tenant_id = lan.tenant_id
            WHERE lan.tenant_id = ? AND lan.rectified_at IS NULL
            ORDER BY u.block, u.floor, CAST(u.unit_number AS INTEGER), at.area_order
        \"\"\", (tenant_id,)).fetchall()
    finally:
        conn.close()"""

NEW = """    try:
        defect_rows = conn.execute(\"\"\"
            SELECT u.block, u.floor, u.unit_number,
                   at.area_name, at.area_order,
                   ct.category_name AS trade, ct.category_order,
                   it.item_description, it.item_order, it.depth,
                   COALESCE(pit.item_order, it.item_order) AS sort_parent,
                   COALESCE(NULLIF(d.reviewed_comment,''), NULLIF(d.raw_comment,''), d.original_comment) AS description,
                   d.raised_cycle_number, d.created_at
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id AND it.tenant_id = d.tenant_id
            LEFT JOIN item_template pit ON it.parent_item_id = pit.id AND pit.tenant_id = it.tenant_id
            JOIN category_template ct ON it.category_id = ct.id AND ct.tenant_id = d.tenant_id
            JOIN area_template at ON ct.area_id = at.id AND at.tenant_id = d.tenant_id
            JOIN unit_real u ON d.unit_id = u.id AND u.tenant_id = d.tenant_id
            WHERE d.tenant_id = ? AND d.status = 'open'
              AND EXISTS (
                  SELECT 1 FROM inspection i
                  WHERE i.unit_id = d.unit_id
                    AND i.tenant_id = d.tenant_id
                    AND i.cycle_number >= 2
              )
            ORDER BY u.block, u.floor, CAST(u.unit_number AS INTEGER),
                     at.area_order, ct.category_order,
                     sort_parent, it.depth, it.item_order
        \"\"\", (tenant_id,)).fetchall()

        latent_rows = conn.execute(\"\"\"
            SELECT u.block, u.floor, u.unit_number,
                   at.area_name, at.area_order,
                   lan.note_html, lan.cycle_number, lan.created_at
            FROM latent_area_note lan
            JOIN area_template at ON lan.area_template_id = at.id AND at.tenant_id = lan.tenant_id
            JOIN unit_real u ON lan.unit_id = u.id AND u.tenant_id = lan.tenant_id
            WHERE lan.tenant_id = ? AND lan.rectified_at IS NULL
              AND EXISTS (
                  SELECT 1 FROM inspection i
                  WHERE i.unit_id = lan.unit_id
                    AND i.tenant_id = lan.tenant_id
                    AND i.cycle_number >= 2
              )
            ORDER BY u.block, u.floor, CAST(u.unit_number AS INTEGER), at.area_order
        \"\"\", (tenant_id,)).fetchall()
    finally:
        conn.close()"""


def main():
    src = ANALYTICS.read_text()

    if 'sort_parent' in src and 'LEFT JOIN item_template pit ON it.parent_item_id' in src:
        print('[NO-OP] Already applied.')
        raise SystemExit(0)

    assert OLD in src, 'Anchor missing'
    assert src.count(OLD) == 1, 'Anchor not unique'

    before_cycle2 = src.count('AND i.cycle_number >= 2')
    new_src = src.replace(OLD, NEW)
    after_cycle2 = new_src.count('AND i.cycle_number >= 2')

    assert 'sort_parent, it.depth, it.item_order' in new_src
    assert 'LEFT JOIN item_template pit ON it.parent_item_id' in new_src
    assert (after_cycle2 - before_cycle2) == 2, f'Expected +2 EXISTS predicates, got +{after_cycle2 - before_cycle2}'

    ANALYTICS.write_text(new_src)
    print(f'[OK] Patch applied. Cycle>=2 predicates: {before_cycle2} -> {after_cycle2} (+2).')


if __name__ == '__main__':
    main()
