#!/usr/bin/env python3
"""
v353 DATA REPAIR -- second hide-path (62 units / 2071 items).

Flips the validated id-list: inspection_item.status 'skipped' -> 'pending'
(comment/marked_at already NULL on these rows; left untouched).
Reopens the 2 submitted inspections in scope: status -> 'in_progress',
submitted_at -> NULL (mirrors v350/v351 done-state precedent).

Rollback source: in-DB table v353_repair_backup, written BEFORE any mutation.
Captures verbatim pre-state for every affected row.

DRY=True  -> select id-list, print counts/sample, assert scope, MUTATE NOTHING.
DRY=False -> create backup table, capture pre-state, mutate, re-assert, commit.

Run DRY first. Review. Only then flip DRY=False.
"""
import sqlite3

DB = "/var/data/inspections.db"
DRY = False                      # <<< flip to False for the live run

EXPECT_ITEMS = 2071
EXPECT_UNITS = 62
EXPECT_SUBMITTED = 2

# --- the validated selector (item ids in scope) ---
SEL_ITEMS = """
SELECT cur.id AS item_id, cur.status, cur.comment, cur.marked_at,
       cur.inspection_id
FROM inspection_item cur
JOIN inspection i ON i.id=cur.inspection_id
JOIN inspection_cycle ic ON ic.id=i.cycle_id
JOIN inspection_item prv ON prv.item_template_id=cur.item_template_id
JOIN inspection pi ON pi.id=prv.inspection_id AND pi.unit_id=i.unit_id
JOIN inspection_cycle pic ON pic.id=pi.cycle_id AND pic.cycle_number=ic.cycle_number-1
JOIN item_template it ON it.id=cur.item_template_id
WHERE cur.status='skipped' AND prv.status='pending'
  AND it.floor_condition!='ground_only' AND i.exclusion_list_id IS NULL
"""

# the submitted inspections in scope (done-state reopen set)
SEL_SUBMITTED = """
SELECT DISTINCT i.id AS insp_id, i.status, i.submitted_at
FROM inspection_item cur
JOIN inspection i ON i.id=cur.inspection_id
JOIN inspection_cycle ic ON ic.id=i.cycle_id
JOIN inspection_item prv ON prv.item_template_id=cur.item_template_id
JOIN inspection pi ON pi.id=prv.inspection_id AND pi.unit_id=i.unit_id
JOIN inspection_cycle pic ON pic.id=pi.cycle_id AND pic.cycle_number=ic.cycle_number-1
JOIN item_template it ON it.id=cur.item_template_id
WHERE cur.status='skipped' AND prv.status='pending'
  AND it.floor_condition!='ground_only' AND i.exclusion_list_id IS NULL
  AND i.status='submitted'
"""

def main():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row

    items = c.execute(SEL_ITEMS).fetchall()
    subs  = c.execute(SEL_SUBMITTED).fetchall()

    n_items = len(items)
    n_units = len(set(r["inspection_id"] for r in items))
    n_subs  = len(subs)

    print("SCOPE: items=%d  units=%d  submitted_to_reopen=%d" % (n_items, n_units, n_subs))
    print("EXPECT: items=%d units=%d submitted=%d" % (EXPECT_ITEMS, EXPECT_UNITS, EXPECT_SUBMITTED))

    # hard scope guards -- abort on any mismatch
    assert n_items == EXPECT_ITEMS, "ITEM COUNT MISMATCH -- abort"
    assert n_units == EXPECT_UNITS, "UNIT COUNT MISMATCH -- abort"
    assert n_subs  == EXPECT_SUBMITTED, "SUBMITTED COUNT MISMATCH -- abort"

    # sanity: every in-scope item must currently be skipped
    bad = [r["item_id"] for r in items if r["status"] != "skipped"]
    assert not bad, "Non-skipped row in scope -- abort: %r" % bad[:5]

    print("\n--- submitted inspections to reopen ---")
    for r in subs:
        print("  %s  status=%s  submitted_at=%s" % (r["insp_id"], r["status"], r["submitted_at"]))

    print("\n--- sample of 3 items to flip ---")
    for r in items[:3]:
        print("  %s  status=%s comment=%r marked_at=%r" % (r["item_id"], r["status"], r["comment"], r["marked_at"]))

    if DRY:
        print("\nDRY RUN -- nothing mutated. Review, then set DRY=False.")
        return

    # ---------- LIVE ----------
    print("\nLIVE RUN -- writing backup then mutating.")

    # backup table (drop+recreate so a re-run starts clean; rollback uses the latest)
    c.execute("DROP TABLE IF EXISTS v353_repair_backup")
    c.execute("""
        CREATE TABLE v353_repair_backup (
            kind TEXT, row_id TEXT,
            old_status TEXT, old_comment TEXT, old_marked_at TEXT,
            old_submitted_at TEXT
        )
    """)

    # capture item pre-state
    for r in items:
        c.execute(
            "INSERT INTO v353_repair_backup (kind,row_id,old_status,old_comment,old_marked_at,old_submitted_at) VALUES ('item',?,?,?,?,NULL)",
            (r["item_id"], r["status"], r["comment"], r["marked_at"]))
    # capture submitted-inspection pre-state
    for r in subs:
        c.execute(
            "INSERT INTO v353_repair_backup (kind,row_id,old_status,old_comment,old_marked_at,old_submitted_at) VALUES ('inspection',?,?,NULL,NULL,?)",
            (r["insp_id"], r["status"], r["submitted_at"]))

    bk = c.execute("SELECT COUNT(*) FROM v353_repair_backup").fetchone()[0]
    assert bk == n_items + n_subs, "Backup row count mismatch -- abort before mutate"
    print("Backup rows written: %d (items %d + inspections %d)" % (bk, n_items, n_subs))

    # mutate items
    item_ids = [r["item_id"] for r in items]
    for iid in item_ids:
        c.execute("UPDATE inspection_item SET status='pending' WHERE id=?", (iid,))
    # mutate submitted inspections
    for r in subs:
        c.execute("UPDATE inspection SET status='in_progress', submitted_at=NULL WHERE id=?", (r["insp_id"],))

    # re-assert post-state before commit
    still_skipped = c.execute(
        "SELECT COUNT(*) FROM inspection_item WHERE id IN (%s) AND status!='pending'"
        % ",".join("?"*len(item_ids)), item_ids).fetchone()[0]
    assert still_skipped == 0, "Some items not flipped -- ABORT, rolling back"

    sub_ids = [r["insp_id"] for r in subs]
    still_sub = c.execute(
        "SELECT COUNT(*) FROM inspection WHERE id IN (%s) AND (status!='in_progress' OR submitted_at IS NOT NULL)"
        % ",".join("?"*len(sub_ids)), sub_ids).fetchone()[0]
    assert still_sub == 0, "Some submitted not reopened -- ABORT, rolling back"

    c.commit()
    print("COMMITTED. items flipped=%d  inspections reopened=%d" % (n_items, n_subs))
    print("Rollback table: v353_repair_backup (kept until you confirm).")

if __name__ == "__main__":
    main()
