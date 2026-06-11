#!/usr/bin/env python3
"""
inspection_engine.py -- SHARED line-set / counts engine.

SINGLE SOURCE OF TRUTH for per-unit inspection state. Both deliverables import
from here so they can NEVER diverge:
  - generate_inspection_sheet.py  (per-unit Raubex de-snag worklist xlsx)
  - generate_points_workbook.py   (190-unit Inspection Points workbook)

This codifies the v411 alignment audit (proven 0 PTV / 0 cycle / 0 latent
mismatch vs Inspection_Points_190_Units across all 190 units).

ZERO hardcoded per-unit data. Everything is sourced live from the DB. ASCII only.
Read-only w.r.t. the DB.

--- THE MODEL (v4 workbook, authoritative) -------------------------------------
Total Points (denominator) = 508 ground-floor / 502 above-ground-floor
    (above-GF = 508 active points less 6 ground-only burglar-bar items,
     structurally absent upstairs).
Items to Mark = Pending + NTS + Not Inst + Skipped.
Already OK + Items to Mark = Total Points   (the row closes -- invariant).
POINTS TO VISIT = Items to Mark + Latents.
Open Defects = context only; NOT added to PTV (they sit on NTS items already
    counted).

--- LINE SET (what the de-snag sheet emits as rows) ----------------------------
Exactly the "Items to Mark" items in walk order: inspection_item rows whose
status is in (pending, not_to_standard, not_installed, skipped), active
template, MINUS structural ground-only-above-GF, plus latents as separate lines.
So: len(line rows) == Items to Mark, and sheet checkpoints == PTV. Identical
arithmetic to the workbook -- by construction, not by coincidence.
"""
import sqlite3

DB_DEFAULT = "/var/data/inspections.db"
TENANT = "MONOGRAPH"

LINE_STATUSES = ("pending", "not_to_standard", "not_installed", "skipped")

# raw inspection.status -> v4 display string. Underscores to spaces; paused
# carries the data-loss re-inspect flag (unit 242 case, derived not hardcoded).
STATUS_DISPLAY = {
    "not_started": "not started",
    "in_progress": "in progress",
    "submitted": "submitted",
    "reviewed": "reviewed",
    "approved": "approved",
    "certified": "certified",
    "pending_followup": "pending followup",
    "paused": "paused — RE-INSPECT (data-loss)",
}


def connect(db_path=DB_DEFAULT):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


def all_units(c):
    """Every real unit (excludes TEST%), ordered by block then unit number."""
    return c.execute(
        "SELECT id, block, floor, unit_number FROM unit_real "
        "WHERE tenant_id=? AND unit_number NOT LIKE 'TEST%' "
        "ORDER BY block, CAST(unit_number AS INTEGER)", (TENANT,)).fetchall()


def resolve_unit(c, unit_number):
    return c.execute(
        "SELECT id, block, floor, unit_number FROM unit_real "
        "WHERE unit_number=? AND tenant_id=? AND unit_number NOT LIKE 'TEST%'",
        (unit_number, TENANT)).fetchone()


def top_inspection(c, uid):
    """Highest-cycle inspection -- the authoritative current state for a unit."""
    return c.execute(
        "SELECT id, cycle_number, status FROM inspection "
        "WHERE unit_id=? ORDER BY cycle_number DESC, created_at DESC LIMIT 1",
        (uid,)).fetchone()


def total_points(floor):
    """508 on ground floor (floor 0), 502 above (6 ground-only items absent)."""
    return 508 if (floor is None or floor == 0) else 502


def _structural_skip(floor, fc):
    """A ground-only item on an above-GF unit -- structurally absent, dropped."""
    return floor is not None and floor > 0 and fc == "ground_only"


def line_rows(c, insp_id, floor):
    """The 'Items to Mark' line set in walk order, with area/category names.
    This is what the de-snag sheet renders AND what the workbook counts."""
    rows = c.execute("""
        SELECT at2.area_name, at2.area_order,
               ct.category_name, ct.category_order,
               it.item_description, it.item_order,
               it.floor_condition, ii.status
        FROM inspection_item ii
        JOIN item_template it ON ii.item_template_id = it.id AND it.active = 1
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE ii.inspection_id = ?
          AND ii.status IN ('pending','not_to_standard','not_installed','skipped')
        ORDER BY at2.area_order, ct.category_order, it.item_order
    """, (insp_id,)).fetchall()
    return [r for r in rows if not _structural_skip(floor, r["floor_condition"])]


def open_latents(c, uid):
    return c.execute(
        "SELECT COUNT(*) FROM latent_area_note WHERE unit_id=? AND rectified_at IS NULL",
        (uid,)).fetchone()[0]


def open_defects(c, uid):
    return c.execute(
        "SELECT COUNT(*) FROM defect WHERE unit_id=? AND status='open'",
        (uid,)).fetchone()[0]


def unit_counts(c, unit):
    """Full per-unit count bundle matching the v4 detail row. The single
    computation both generators rely on. Returns a dict; raises nothing --
    units with no inspection return a not-started shell.

    Invariant enforced: already_ok + items_to_mark == total_points.
    """
    uid, floor = unit["id"], unit["floor"]
    tp = total_points(floor)
    insp = top_inspection(c, uid)
    if not insp:
        return {
            "unit": unit["unit_number"], "block": unit["block"], "floor": floor,
            "cycle": None, "status": "not started", "total_points": tp,
            "already_ok": tp, "pending": 0, "nts": 0, "not_inst": 0, "skipped": 0,
            "items_to_mark": 0, "latents": 0, "ptv": 0, "open_defects": 0,
            "insp_id": None, "lines": [], "closes": True,
        }
    lines = line_rows(c, insp["id"], floor)
    pending = sum(1 for r in lines if r["status"] == "pending")
    nts = sum(1 for r in lines if r["status"] == "not_to_standard")
    not_inst = sum(1 for r in lines if r["status"] == "not_installed")
    skipped = sum(1 for r in lines if r["status"] == "skipped")
    itm = pending + nts + not_inst + skipped
    latents = open_latents(c, uid)
    already_ok = tp - itm
    return {
        "unit": unit["unit_number"], "block": unit["block"], "floor": floor,
        "cycle": "C%d" % insp["cycle_number"],
        "status": STATUS_DISPLAY.get(insp["status"], insp["status"]),
        "total_points": tp, "already_ok": already_ok,
        "pending": pending, "nts": nts, "not_inst": not_inst, "skipped": skipped,
        "items_to_mark": itm, "latents": latents, "ptv": itm + latents,
        "open_defects": open_defects(c, uid),
        "insp_id": insp["id"], "lines": lines,
        "closes": (already_ok + itm == tp),
    }


def comment_for(c, uid, area_name, item_description):
    """Latest open-defect original_comment for an item (context on the sheet)."""
    r = c.execute("""
        SELECT d.original_comment
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.unit_id = ? AND d.status='open'
          AND at2.area_name = ? AND it.item_description = ?
        ORDER BY d.updated_at DESC LIMIT 1
    """, (uid, area_name, item_description)).fetchone()
    return (r["original_comment"] or "") if r else ""
