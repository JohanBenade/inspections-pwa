"""
v319 - Filter ground_only items from de-snag PDF excluded-items addendum

Bug:
  app/services/pdf_generator.py get_defects_data() collects all 'skipped'
  inspection_items into excluded_count and excluded_items_by_area without
  distinguishing between two categorically different skip reasons:
    1. Exclusion-list skips (Raubex "not ready") - legitimately pending
    2. floor_condition='ground_only' on upper floors - NOT APPLICABLE,
       never to be inspected on this unit

  This causes every upper-floor unit (floor > 0) to show ground_only items
  (typically the 6 burglar-bar items: W1, W1a, W2, W3 x3) in the
  "Addendum: Excluded Items" section of the de-snag PDF, with text reading
  "Excluded from inspection: N items not yet assessed".

  Side-effect: is_certified at line 299 checks excluded_count == 0, so the
  bug ALSO prevents any upper-floor unit from auto-certifying even when
  all defects are rectified.

  First documented while reviewing unit 248 (Block 1, Floor 2) de-snag PDF
  on 23 May 2026 - showed 76 rectified / 0 not rectified / 0 open AND a
  6-item excluded addendum + "Certification date: Not Certified".

Fix:
  Add JOIN inspection -> unit, and an additional WHERE clause that excludes
  floor_condition='ground_only' rows when COALESCE(u.floor, 0) > 0. Ground-
  floor behaviour is unchanged - if a ground_only item is skipped on floor=0
  it is by exclusion list, and still appears in the addendum.

Downstream effects (all corrected by this single query change):
  - excluded_count (line 167)
  - excluded_items_by_area - the addendum list (line 184)
  - summary.excluded (lines 373, 419)
  - is_certified (line 299)
"""

PATH = "app/services/pdf_generator.py"

with open(PATH, "r") as f:
    content = f.read()

old_sql = '''        excluded_raw = query_db("""
            SELECT it.item_description,
                   parent.item_description as parent_description,
                   ct.category_name, ct.category_order,
                   at2.area_name, at2.area_order,
                   it.item_order
            FROM inspection_item ii
            JOIN item_template it ON ii.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            LEFT JOIN item_template parent ON it.parent_item_id = parent.id
            WHERE ii.inspection_id = ? AND ii.status = 'skipped'
            ORDER BY at2.area_order, ct.category_order, it.item_order
        """, [inspection['id']])'''

new_sql = '''        excluded_raw = query_db("""
            SELECT it.item_description,
                   parent.item_description as parent_description,
                   ct.category_name, ct.category_order,
                   at2.area_name, at2.area_order,
                   it.item_order
            FROM inspection_item ii
            JOIN item_template it ON ii.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            LEFT JOIN item_template parent ON it.parent_item_id = parent.id
            JOIN inspection insp ON ii.inspection_id = insp.id
            JOIN unit u ON insp.unit_id = u.id
            WHERE ii.inspection_id = ? AND ii.status = 'skipped'
              AND (COALESCE(u.floor, 0) = 0 OR it.floor_condition != 'ground_only')
            ORDER BY at2.area_order, ct.category_order, it.item_order
        """, [inspection['id']])'''

assert old_sql in content, "MATCH FAILED: SQL block not found in pdf_generator.py"
n = content.count(old_sql)
assert n == 1, f"Expected exactly 1 match, found {n}"
content = content.replace(old_sql, new_sql)

with open(PATH, "w") as f:
    f.write(content)

print("OK: v319 patched - excluded query now filters ground_only items on upper floors")
