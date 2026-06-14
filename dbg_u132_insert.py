#!/usr/bin/env python3
# TEMP DIAGNOSTIC: insert a LOUNGE item_categories dump into desnag_view.
# Reversible: dbg_u132_revert.py removes the exact same block.
import io

PATH = "app/routes/inspection.py"

ANCHOR = (
    "            })\n"
    "\n"
    "    # Items count for grand totals (cohort = newly-visible at C2+, has_prior_defects=0)\n"
)

DEBUG = (
    "            })\n"
    "\n"
    "    # ===== TEMP DBG U132 (remove via dbg_u132_revert.py) =====\n"
    "    try:\n"
    "        import sys as _sys\n"
    "        _la = areas.get('LOUNGE', {})\n"
    "        print('DBG_U132 inspection_id=', inspection_id, 'is_followup=', is_followup, file=_sys.stderr, flush=True)\n"
    "        for _ic in _la.get('item_categories', []):\n"
    "            print('DBG_U132 CAT', _ic.get('name'), 'rows=', len(_ic.get('checklist', [])), file=_sys.stderr, flush=True)\n"
    "            for _it in _ic.get('checklist', []):\n"
    "                print('DBG_U132 ITEM', repr(_it.get('item_description')),\n"
    "                      'status=', _it.get('status'),\n"
    "                      'hpd=', _it.get('has_prior_defects'),\n"
    "                      'hop=', _it.get('has_open_prior'),\n"
    "                      'cok=', _it.get('is_carried_ok'),\n"
    "                      'chd=', _it.get('children_have_defects'),\n"
    "                      'parent=', _it.get('parent_item_id'),\n"
    "                      'pstatus=', _it.get('parent_status'),\n"
    "                      file=_sys.stderr, flush=True)\n"
    "    except Exception as _e:\n"
    "        print('DBG_U132 ERR', _e, file=_sys.stderr, flush=True)\n"
    "    # ===== END TEMP DBG U132 =====\n"
    "\n"
    "    # Items count for grand totals (cohort = newly-visible at C2+, has_prior_defects=0)\n"
)

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

assert src.count(ANCHOR) == 1, "anchor not unique/found: count=%d" % src.count(ANCHOR)
assert "DBG_U132" not in src, "debug block already present"

src2 = src.replace(ANCHOR, DEBUG, 1)
assert "DBG_U132" in src2, "insertion failed"
assert src2.count("# ===== END TEMP DBG U132 =====") == 1, "end marker missing"

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src2)

print("OK: DBG_U132 block inserted.")
