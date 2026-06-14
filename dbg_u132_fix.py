#!/usr/bin/env python3
# Fixes the live DBG_U132 block: removes the is_followup reference that
# caused NameError, so the checklist dump can run.
import io

PATH = "app/routes/inspection.py"

OLD = (
    "        print('DBG_U132 inspection_id=', inspection_id, 'is_followup=', is_followup, file=_sys.stderr, flush=True)\n"
)
NEW = (
    "        print('DBG_U132 inspection_id=', inspection_id, file=_sys.stderr, flush=True)\n"
)

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

assert src.count(OLD) == 1, "old line not found exactly once: %d" % src.count(OLD)

src2 = src.replace(OLD, NEW, 1)
assert "is_followup=', is_followup" not in src2, "is_followup ref still present"
assert "DBG_U132 inspection_id=', inspection_id, file=" in src2, "new line missing"

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src2)

print("OK: is_followup reference removed from DBG_U132 block.")
