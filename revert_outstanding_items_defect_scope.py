#!/usr/bin/env python3
"""
Revert Outstanding Items defect scope.

The d.raised_cycle_number >= 2 filter zeroes the report because all
defects in the table are C1-raised (verified via Render probe:
raised_cycle_number=1 returned 5859 rows, no other values).

C2 inspections clear defects; they don't raise them. C2+ findings live
in latent_area_note. The correct rule for Ralph's punch list is
unit-level: defects on units that have had a C2+ inspection.

Restoring the unit-level EXISTS clause.
"""
from pathlib import Path

ANALYTICS = Path("app/routes/analytics.py")
assert ANALYTICS.exists()

OLD = """            WHERE d.tenant_id = ? AND d.status = 'open'
              AND d.raised_cycle_number >= 2"""

NEW = """            WHERE d.tenant_id = ? AND d.status = 'open'
              AND EXISTS (
                  SELECT 1 FROM inspection i
                  WHERE i.unit_id = d.unit_id
                    AND i.tenant_id = d.tenant_id
                    AND i.cycle_number >= 2
              )"""


def main():
    src = ANALYTICS.read_text()

    if "AND d.raised_cycle_number >= 2" not in src:
        print('[NO-OP] Defect filter already reverted (or never patched).')
        raise SystemExit(0)

    assert OLD in src, "Anchor missing - drift"
    assert src.count(OLD) == 1, "Anchor not unique"

    before_cycle2 = src.count('AND i.cycle_number >= 2')
    new_src = src.replace(OLD, NEW)
    after_cycle2 = new_src.count('AND i.cycle_number >= 2')

    assert "AND d.raised_cycle_number >= 2" not in new_src
    assert "WHERE i.unit_id = d.unit_id" in new_src
    # Defect EXISTS restored alongside latent EXISTS:
    assert (after_cycle2 - before_cycle2) == 1, \
        f"Expected +1 cycle>=2 occurrence, got delta={after_cycle2 - before_cycle2}"

    ANALYTICS.write_text(new_src)
    print(f"[OK] Defect filter reverted to unit-level EXISTS. "
          f"i.cycle_number>=2 occurrences: {before_cycle2} -> {after_cycle2}.")


if __name__ == '__main__':
    main()
