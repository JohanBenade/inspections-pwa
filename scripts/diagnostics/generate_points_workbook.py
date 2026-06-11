#!/usr/bin/env python3
"""
generate_points_workbook.py -- PERMANENT 190-unit Inspection Points workbook
generator.  TEMPLATE-INHERITANCE build (HANDOVER v415 #1 rule).

This generator NEVER hand-codes fonts/fills/borders/number-formats and NEVER
rebuilds the visual from a sample.  It loads the styled reference workbook
(template_points_190.xlsx, a frozen copy of Inspection_Points_190_Units_v4.xlsx)
as a shell and writes ONLY data VALUES into the detail rows.  All styling,
merges, column widths, row heights, freeze panes, the Summary sheet and every
formula are inherited 100% by construction -- zero style code, zero drift.

Data comes from the SHARED engine (inspection_engine.py), so the workbook and
the de-snag sheets can never disagree (Johan's core requirement).

Detail sheet layout (inherited from template):
  rows 1-3   title / source-note / column headers   (styling + A2 note text)
  rows 4..   one data row per unit                   (VALUES overwritten here)
  last+1     PROJECT TOTAL                           (SUM formulas, restyled
                                                       only if rows are added)
Per data row, only cols A-K, M, O carry literal values.  L and N are formulas
(=H+I+J+K and =L+M) -- written as formulas so the sheet stays live.

USAGE (on Render, read-only DB):
    python3 scripts/diagnostics/generate_points_workbook.py
    python3 scripts/diagnostics/generate_points_workbook.py --out /tmp \
        --snap "2026-06-09 09:59 UTC"

Writes <out>/Inspection_Points_190_Units.xlsx.  ASCII only.  Read-only DB.
"""
import sys
import os
import copy
import argparse
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inspection_engine as eng

DETAIL = "190-Unit Detail"
SUMMARY = "Summary"

# Template copy lives beside this script. It is the single styling source.
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "template_points_190.xlsx")

FIRST_DATA_ROW = 4  # template data starts at row 4 (rows 1-3 = title/note/hdr)

# Detail source-note text. Snapshot string is appended at runtime so the note
# always reflects the DB it was built from. Body is the template's wording.
NOTE_BODY = ("Total Points = 508 (ground) / 502 (above ground = 508 active "
             "points less 6 ground-only burglar-bar items, structurally absent "
             "upstairs).   Items to Mark = Pending + NTS + Not Inst + Skipped.   "
             "Already OK + Items to Mark = Total Points (row closes).   POINTS "
             "TO VISIT = Items to Mark + Latents.   Open Defects shown for "
             "context only \u2014 NOT added to PTV (they sit on the NTS items "
             "already counted).")


def _copy_row_style(ws, src_row, dst_row, ncols):
    """Clone every cell's style from src_row to dst_row (no re-styling)."""
    for ci in range(1, ncols + 1):
        s = ws.cell(src_row, ci)
        d = ws.cell(dst_row, ci)
        d._style = copy.copy(s._style)
    ws.row_dimensions[dst_row].height = ws.row_dimensions[src_row].height


def write_detail(ws, rows, snap):
    """Overwrite VALUES into the styled template detail rows. Styling untouched."""
    ncols = 15  # A..O

    # --- source note (A2): keep template styling, refresh text + snapshot -----
    note = NOTE_BODY
    if snap:
        note += "   Source: %s, SNAP %s." % (eng.DB_DEFAULT, snap)
    ws.cell(2, 1).value = note

    # --- locate the template's PROJECT TOTAL row dynamically ------------------
    template_total_row = None
    r = FIRST_DATA_ROW
    while r <= ws.max_row + 1:
        if str(ws.cell(r, 1).value).strip().upper() == "PROJECT TOTAL":
            template_total_row = r
            break
        r += 1
    if template_total_row is None:
        raise RuntimeError("PROJECT TOTAL row not found in template")
    template_data_count = template_total_row - FIRST_DATA_ROW

    n = len(rows)

    # --- reconcile row count to live unit count, COPYING style (never restyle)-
    if n != template_data_count:
        style_src = FIRST_DATA_ROW  # an existing fully-styled data row
        if n > template_data_count:
            add = n - template_data_count
            ws.insert_rows(template_total_row, amount=add)
            for i in range(add):
                _copy_row_style(ws, style_src, template_total_row + i, ncols)
        else:
            remove = template_data_count - n
            ws.delete_rows(template_total_row - remove, amount=remove)
        template_total_row = FIRST_DATA_ROW + n  # total row shifts with count

    # --- write VALUES only into data rows -------------------------------------
    for i, d in enumerate(rows):
        r = FIRST_DATA_ROW + i
        ws.cell(r, 1).value = d["unit"]
        ws.cell(r, 2).value = d["block"]
        ws.cell(r, 3).value = d["floor"]
        ws.cell(r, 4).value = d["cycle"]
        ws.cell(r, 5).value = d["status"]
        ws.cell(r, 6).value = d["total_points"]
        ws.cell(r, 7).value = d["already_ok"]
        ws.cell(r, 8).value = d["pending"]
        ws.cell(r, 9).value = d["nts"]
        ws.cell(r, 10).value = d["not_inst"]
        ws.cell(r, 11).value = d["skipped"]
        ws.cell(r, 12).value = "=H%d+I%d+J%d+K%d" % (r, r, r, r)
        ws.cell(r, 13).value = d["latents"]
        ws.cell(r, 14).value = "=L%d+M%d" % (r, r)
        ws.cell(r, 15).value = d["open_defects"]

    # --- rebuild PROJECT TOTAL SUM formulas to the live last data row ---------
    last = FIRST_DATA_ROW + n - 1
    tr = template_total_row
    for ci in range(6, 16):  # F..O
        L = get_column_letter(ci)
        ws.cell(tr, ci).value = "=SUM(%s%d:%s%d)" % (L, FIRST_DATA_ROW, L, last)

    return tr, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp")
    ap.add_argument("--db", default=eng.DB_DEFAULT)
    ap.add_argument("--snap", default="")
    ap.add_argument("--template", default=TEMPLATE)
    args = ap.parse_args()

    if not os.path.exists(args.template):
        sys.exit("TEMPLATE MISSING: %s (commit template_points_190.xlsx beside "
                 "this script)" % args.template)

    c = eng.connect(args.db)
    units = eng.all_units(c)
    rows = [eng.unit_counts(c, u) for u in units]

    broken = [r["unit"] for r in rows if not r["closes"]]
    if broken:
        print("WARN: rows do not close (already_ok+items!=total):", broken)

    wb = load_workbook(args.template)  # inherits ALL styling, both sheets
    det = wb[DETAIL]
    total_row, last = write_detail(det, rows, args.snap)

    # Summary sheet is 100% formula-driven off the detail total row; leave its
    # formulas/styling untouched. Refresh only the literal snapshot line (A3).
    if SUMMARY in wb.sheetnames and args.snap:
        sm = wb[SUMMARY]
        sm.cell(3, 1).value = ("190 four-bed units, 7 blocks, DB SNAP %s" % args.snap)

    path = "%s/Inspection_Points_190_Units.xlsx" % args.out.rstrip("/")
    wb.save(path)
    print("Units: %d | data rows %d-%d | PROJECT TOTAL row: %d | rows-close: %s "
          "-> %s" % (len(rows), FIRST_DATA_ROW, last, total_row, not broken, path))


if __name__ == "__main__":
    main()
