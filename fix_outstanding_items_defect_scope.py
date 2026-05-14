#!/usr/bin/env python3
"""
Outstanding Items: tighten defect scope to defect-level filter.

Replace the unit-level EXISTS(inspection where cycle_number >= 2)
on the defect query with d.raised_cycle_number >= 2.

Result: Ralph's list shrinks to defects raised in C2+ only. C1-raised
items, even if still open, are hidden.

Latent query is left untouched (bullet explosion stays, unit-EXISTS
safety net stays).
"""
from pathlib import Path

ANALYTICS = Path("app/routes/analytics.py")
assert ANALYTICS.exists()

OLD = """            WHERE d.tenant_id = ? AND d.status = 'open'
              AND EXISTS (
                  SELECT 1 FROM inspection i
                  WHERE i.unit_id = d.unit_id
                    AND i.tenant_id = d.tenant_id
                    AND i.cycle_number >= 2
              )"""

NEW = """            WHERE d.tenant_id = ? AND d.status = 'open'
              AND d.raised_cycle_number >= 2"""


def main():
    src = ANALYTICS.read_text()

    # Idempotency: bail out if the new clause is already present in the defect query
    if "AND d.raised_cycle_number >= 2" in src:
        print('[NO-OP] Already applied.')
        raise SystemExit(0)

    assert OLD in src, "Anchor missing - drift"
    assert src.count(OLD) == 1, "Anchor not unique"

    before_cycle2 = src.count('AND i.cycle_number >= 2')
    new_src = src.replace(OLD, NEW)
    after_cycle2 = new_src.count('AND i.cycle_number >= 2')

    assert "AND d.raised_cycle_number >= 2" in new_src
    # Defect EXISTS gone, latent EXISTS remains:
    assert (before_cycle2 - after_cycle2) == 1, \
        f"Expected -1 cycle>=2 occurrence, got delta={before_cycle2 - after_cycle2}"
    # The d.unit_id reference inside the removed defect EXISTS must be gone:
    assert "WHERE i.unit_id = d.unit_id" not in new_src

    ANALYTICS.write_text(new_src)
    print(f"[OK] Defect scope -> d.raised_cycle_number >= 2. "
          f"i.cycle_number>=2 occurrences: {before_cycle2} -> {after_cycle2}.")


if __name__ == '__main__':
    main()
