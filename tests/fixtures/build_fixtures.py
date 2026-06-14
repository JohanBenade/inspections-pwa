#!/usr/bin/env python3
"""
build_fixtures.py - generate synthetic test databases for the invariant CI gate.

Produces two SQLite files next to this script:
  test_clean.db  - mirrors production baseline shape. Expected: R1=0, R2=1, R3=0.
  test_dirty.db  - one planted violation per rule. Expected: R1>=1, R2>=2, R3>=1.

NO production data. Every row is synthetic and declared explicitly below so the
fixture is auditable in a git diff (we commit this generator, not opaque .db blobs).

Only the 7 tables the invariant rules read are created, with only the columns the
rules use plus the NOT-NULL columns needed for inserts to succeed. Schema shapes
match the live CREATE TABLE statements (confirmed by PRAGMA dump).

Run: python3 build_fixtures.py   (writes both .db files; CI calls this at build time)
"""
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))

# Minimal schema: only the columns the rules touch + NOT-NULL columns for inserts.
# Shapes mirror the live DB (see schema dump). tenant_id kept NOT NULL like prod.
SCHEMA = """
CREATE TABLE item_template (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    floor_condition TEXT NOT NULL DEFAULT 'all',
    active INTEGER DEFAULT 1
);
CREATE TABLE unit (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    unit_number TEXT NOT NULL
);
CREATE TABLE inspection (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    exclusion_list_id TEXT,
    cycle_number INTEGER
);
CREATE TABLE inspection_item (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    inspection_id TEXT NOT NULL,
    item_template_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
CREATE TABLE cycle_excluded_item (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    item_template_id TEXT NOT NULL,
    reason TEXT
);
CREATE TABLE batch_unit (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    removed_at TEXT,
    exclusion_list_id TEXT
);
CREATE TABLE exclusion_list_item (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    exclusion_list_id TEXT NOT NULL,
    item_template_id TEXT NOT NULL
);
"""

T = "tenant-test"  # single synthetic tenant for all rows


def insert(cur, table, **cols):
    keys = ",".join(cols.keys())
    qs = ",".join("?" for _ in cols)
    cur.execute(f"INSERT INTO {table} ({keys}) VALUES ({qs})", tuple(cols.values()))


def build_common(cur):
    """Rows shared by BOTH fixtures: templates, units, the clean/legit cases.
    These must NOT trip any rule."""
    # --- item templates ---
    # normal active templates
    insert(cur, "item_template", id="tpl-normal-1", tenant_id=T, floor_condition="all", active=1)
    insert(cur, "item_template", id="tpl-normal-2", tenant_id=T, floor_condition="all", active=1)
    # a ground_only template (legit upper-floor structural skip path)
    insert(cur, "item_template", id="tpl-ground", tenant_id=T, floor_condition="ground_only", active=1)
    # the ONE known-inert ghost (R2 baseline = 1) - inactive, but referenced
    insert(cur, "item_template", id="tpl-ghost", tenant_id=T, floor_condition="all", active=0)
    # a template used for legit in-list exclusion
    insert(cur, "item_template", id="tpl-inlist", tenant_id=T, floor_condition="all", active=1)

    # --- units ---
    insert(cur, "unit", id="unit-A", tenant_id=T, unit_number="100")
    insert(cur, "unit", id="unit-B", tenant_id=T, unit_number="101")

    # --- inspections ---
    # NULL-link inspection on unit-A, cycle cyc-A
    insert(cur, "inspection", id="insp-A", tenant_id=T, unit_id="unit-A",
           cycle_id="cyc-A", exclusion_list_id=None, cycle_number=2)
    # inspection on unit-B with a real exclusion list link, cycle cyc-B
    insert(cur, "inspection", id="insp-B", tenant_id=T, unit_id="unit-B",
           cycle_id="cyc-B", exclusion_list_id="elist-B", cycle_number=2)

    # --- CLEAN/LEGIT inspection_items (must not trip anything) ---
    # normal ok item
    insert(cur, "inspection_item", id="ii-ok", tenant_id=T,
           inspection_id="insp-A", item_template_id="tpl-normal-1", status="ok")
    # R2 baseline: the ghost template is referenced by one item -> count=1
    insert(cur, "inspection_item", id="ii-ghost", tenant_id=T,
           inspection_id="insp-A", item_template_id="tpl-ghost", status="ok")
    # legit ground_only skip on NULL-link inspection -> R1/R3 must IGNORE (ground_only)
    insert(cur, "inspection_item", id="ii-ground", tenant_id=T,
           inspection_id="insp-A", item_template_id="tpl-ground", status="skipped")
    # legit in-list skip on unit-B: item is in the live batch_unit exclusion list
    insert(cur, "inspection_item", id="ii-inlist", tenant_id=T,
           inspection_id="insp-B", item_template_id="tpl-inlist", status="skipped")

    # batch_unit for unit-B, cycle cyc-B, live (removed_at NULL), points at elist-B
    insert(cur, "batch_unit", id="bu-B", tenant_id=T, unit_id="unit-B",
           cycle_id="cyc-B", removed_at=None, exclusion_list_id="elist-B")
    # exclusion_list_item: tpl-inlist IS in elist-B -> the skip on insp-B is explained
    insert(cur, "exclusion_list_item", id="eli-B", tenant_id=T,
           exclusion_list_id="elist-B", item_template_id="tpl-inlist")


def build_clean(path):
    if os.path.exists(path):
        os.remove(path)
    c = sqlite3.connect(path)
    cur = c.cursor()
    cur.executescript(SCHEMA)
    build_common(cur)
    c.commit()
    c.close()


def build_dirty(path):
    if os.path.exists(path):
        os.remove(path)
    c = sqlite3.connect(path)
    cur = c.cursor()
    cur.executescript(SCHEMA)
    build_common(cur)

    # === planted violations ===

    # R1 violation: skipped, non-ground, NULL-link, has a cleanup CEI row, NOT in list.
    insert(cur, "item_template", id="tpl-r1", tenant_id=T, floor_condition="all", active=1)
    insert(cur, "inspection_item", id="ii-r1", tenant_id=T,
           inspection_id="insp-A", item_template_id="tpl-r1", status="skipped")
    insert(cur, "cycle_excluded_item", id="cei-r1", tenant_id=T,
           cycle_id="cyc-A", item_template_id="tpl-r1", reason="Excluded via cleanup")

    # R2 violation: a SECOND distinct inactive template referenced by an item -> count=2.
    insert(cur, "item_template", id="tpl-ghost2", tenant_id=T, floor_condition="all", active=0)
    insert(cur, "inspection_item", id="ii-ghost2", tenant_id=T,
           inspection_id="insp-A", item_template_id="tpl-ghost2", status="ok")

    # R3 violation: skipped, non-ground, NULL-link, NOT in list, and NO cei row
    # (so it is an R3-only gap, proving R3 fires independently of R1).
    insert(cur, "item_template", id="tpl-r3", tenant_id=T, floor_condition="all", active=1)
    insert(cur, "inspection_item", id="ii-r3", tenant_id=T,
           inspection_id="insp-A", item_template_id="tpl-r3", status="skipped")

    # removed_at trap: tpl-trap WOULD be in-list, but the batch_unit row is removed,
    # so the live-row filter (removed_at IS NULL) must NOT find it -> still an R3 gap.
    insert(cur, "item_template", id="tpl-trap", tenant_id=T, floor_condition="all", active=1)
    insert(cur, "inspection_item", id="ii-trap", tenant_id=T,
           inspection_id="insp-A", item_template_id="tpl-trap", status="skipped")
    insert(cur, "batch_unit", id="bu-A-removed", tenant_id=T, unit_id="unit-A",
           cycle_id="cyc-A", removed_at="2026-05-01 10:00:00", exclusion_list_id="elist-A")
    insert(cur, "exclusion_list_item", id="eli-A-trap", tenant_id=T,
           exclusion_list_id="elist-A", item_template_id="tpl-trap")

    c.commit()
    c.close()


if __name__ == "__main__":
    clean = os.path.join(HERE, "test_clean.db")
    dirty = os.path.join(HERE, "test_dirty.db")
    build_clean(clean)
    build_dirty(dirty)
    print("built:", clean)
    print("built:", dirty)
