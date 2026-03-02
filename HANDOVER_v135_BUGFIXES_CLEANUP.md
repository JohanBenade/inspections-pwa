# Inspections PWA - Handover Document
**Date:** 2 March 2026 (Monday)
**Version:** v135
**Previous:** v134 (Playwright test suite, inspector feedback, bug fixes designed)
**Status:** Bug fixes deployed. Analytics gate fixed. Cleanup enhanced. Batch filter + Excl designed but not built.

---

## WHAT THIS SESSION (v135) ACCOMPLISHED

### 1. Bug 4 Fix: Panel Overlap / Ghost Menus (DEPLOYED)
- File: app/templates/inspection/_single_item.html line 154
- Closes all open panels before opening new one. Restores Inspect buttons.
- Likely resolves Bug 1 (scroll-triggered marking) as side effect.

### 2. Bug 3 Fix: OK/NI Button Lag - Optimistic UI (DEPLOYED)
- File: app/templates/inspection/_single_item.html lines 159-160
- onclick swaps button colour instantly before server responds.

### 3. Analytics Reviewed-Gate Fix (DEPLOYED)
- File: app/routes/analytics.py - 41 occurrences
- Added pending_followup to IN clause. Signed-off units now visible.
- Root cause: Kevin sign-off sets status to pending_followup which was excluded.

### 4. Defects Cleanup Page Enhancements (DEPLOYED)
- Narrower desc column (min 120px, max 280px)
- Horizontal action buttons (flex row): Edit, Move, Del, Excl (disabled), Re-Insp (disabled)
- Row flash feedback: Edit=green 1.5s, Move=amber 1.5s (no reload), Delete=red fadeout 1.2s

### 5. Delete FK Constraint Fix (DEPLOYED)
- File: app/routes/approvals.py ~line 1371
- Delete defect_history before defect (FK to defect table)

### 6. Manage Exclusions Button Visibility (DEPLOYED)
- File: app/templates/batches/detail.html ~line 26
- Visible for all non-complete batches (was only open/in_progress)

### 7. DB Fix: Batch Notes HTML Tags (Render)
- Batch 78a45234: removed p tags from notes field

---

## TERMINOLOGY ALIGNMENT (AGREED)

| Term | Meaning | Example |
|------|---------|---------|
| Zone | Block + Floor | B5 Ground, B6 1st Floor |
| Round | Inspection sequence in zone | R1, R2, R3 |
| Batch | Snagging Request from Raubex | Raubex 17-Feb-2026 |
| Inspection | Unit-level pass | Unit 029 Inspection 1, 2 |

Snagging Request = Batch (one-to-one, same thing).
DB inspection_cycle = zone + round. Use "B5 Ground R1" in UI.

---

## PENDING / CARRY FORWARD

### Priority 1: Defects Cleanup - Batch Filter (DESIGNED, NOT BUILT)
- Cleanup page becomes batch-scoped - one batch at a time
- Batch name in header, batch selector needed
- All cleanup queries filtered by batch
- PREREQUISITE for Excl feature

### Priority 2: Defects Cleanup - Excl Button (DESIGNED, NOT BUILT)
- Modal: item being excluded, batch name, impact count (X defects across Y units)
- On confirm (in order):
  1. Find batch via batch_unit where cycle_id = defect.raised_cycle_id
  2. Find ALL defects with same item_template_id across ALL units in batch
  3. Delete defect_history records (FK)
  4. Delete defect records
  5. Reset inspection_item to status=skipped
  6. Add to cycle_excluded_item for ALL cycles in that batch
  7. Audit trail
- Scope: own batch only

### Priority 3: Snagging Request Analytics (DESIGNED, NOT BUILT)
- New page: /analytics/batch/<batch_id>
- Five milestones: Received, Inspected, Reviewed, Approved, PDFs Pushed
- Three analytics levels: per batch (NEW), per zone (EXISTS), project-wide (EXISTS)

### Priority 4: Bug 2 - Guide Pill Auto-Submit (DECISION NEEDED)
- Option A (recommended): pills set input value, require tap Add
- Option B: 300ms touch delay
- Option C: undo toast

### Priority 5: Re-inspection Workflow B5 2nd Floor
- 11 units (231-243), 240 placeholder defects
- Approach: delete placeholders, reset items, reassign to Alex
- Waiting on Johan/Alex discussion

### Priority 6: Grammar scripts f2/f3 - need recreation from v133
### Priority 7: Batch Status Auto-Advance - import batches stuck
### Priority 8: Re-Insp Button - specs to follow
### Priority 9: Playwright Test Fixes

---

## CURRENT DATABASE STATE

Gated open defects: 2068 | Ungated: 3403 | Placeholders: 240

### Batches
```
812dab77: Import B5 Ground (in_progress, 14 units)
7132b6f9: Import B5 1st Floor (in_progress, 14 units)
c173fdf3: Import B6 Ground (in_progress, 12 units)
78b3b756: Import B7 Ground (in_progress, 4 units)
f7d88d82: Raubex 17-Feb-2026 (in_progress, 16 units) Locked
78a45234: Raubex 25-Feb-2026 (submitted, 13 units)
```

### Cycles
```
B5 Ground R1=792812c7 | R2=855cd617 | C99=c2725b56 (TEST)
B5 1st Floor R1=179b2b9d
B5 2nd Floor R1=951ea2db
B6 Ground R1=36e85327 | R2=aecf1133
B6 1st Floor R1=213a746f
B7 Ground R1=915b43b4 | R2=9d053777
```

---

## CONSTANTS
```
TENANT = 'MONOGRAPH'
PHASE_ID = 'phase-003'
ITEMS_PER_UNIT = 437
PROJECT_TOTAL_UNITS = 192
```

## INSPECTOR IDs
```
admin (Johan Benade) - admin
alex (Alex Nataniel) - team_lead
stemi (Stemi Tumona) - inspector
thebe (Thebe Majodina) - inspector
thembinkosi (Thembinkosi Biko) - inspector
lindo (Lindokuhle Zulu) - inspector
fiso (Fisokuhle Matsepe) - inspector
thando (Thando Sibanyoni) - inspector
mpho (Mpho Mdluli) - inspector
insp-002 / kevin (Kevin Coetzee) - manager
test-jb (Johan Test) - inspector (TEST)
```

## DEPLOYMENT WORKFLOW
1. Edit on MacBook (~/Documents/GitHub/inspections-pwa/)
2. git add -A && git commit -m "message" && git push
3. Render auto-deploys. NEVER edit on Render.
4. Long scripts: heredoc to /tmp/ then python3
5. No sed for code edits - Python find/replace only.

## URLS
```
Dashboard: /analytics/
Unified report: /analytics/report/unified
Defects Cleanup: /approvals/cleanup
Batches: /batches/
Batch detail: /batches/<batch_id>
```

## PLAYWRIGHT
```
Tests: ~/Documents/GitHub/inspections-pwa/tests/inspection.spec.js
Test unit: 999 (inspector: test-jb)
Run: npx playwright test --project="iPhone 14" --headed
```

---

## VERIFY SCRIPT (run at start of next session on RENDER)
```
cat > /tmp/verify.py << 'XEOF'
import sqlite3
conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

print("=== OPEN DEFECTS (reviewed-gate) ===")
cur.execute("""
    SELECT COUNT(*) FROM defect d
    WHERE d.tenant_id = 'MONOGRAPH' AND d.status = 'open'
    AND d.raised_cycle_id NOT LIKE 'test-%'
    AND EXISTS (SELECT 1 FROM inspection i2
        WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id
        AND i2.status IN ('reviewed','approved','certified','pending_followup'))
""")
print(f"  Gated: {cur.fetchone()[0]}")

print("\n=== PLACEHOLDER DEFECTS ===")
cur.execute("""
    SELECT COUNT(*) FROM defect d
    WHERE d.tenant_id = 'MONOGRAPH' AND d.status = 'open'
    AND LOWER(COALESCE(d.reviewed_comment, d.original_comment))
        IN ('defect noted','n/a','na','as indicated','',
            'not applicable','not tested','to be tested','to be inspected')
""")
print(f"  Total placeholders: {cur.fetchone()[0]}")

print("\n=== BATCHES ===")
cur.execute("""
    SELECT ib.id, ib.name, ib.status,
           COUNT(CASE WHEN bu.status != 'removed' THEN 1 END) as active
    FROM inspection_batch ib
    LEFT JOIN batch_unit bu ON bu.batch_id = ib.id
    WHERE ib.tenant_id = 'MONOGRAPH'
    GROUP BY ib.id ORDER BY ib.created_at
""")
for r in cur.fetchall():
    print(f"  {r[0][:8]}: {r[1]} ({r[2]}, {r[3]} units)")

conn.close()
XEOF
python3 /tmp/verify.py
```

---

**END OF HANDOVER DOCUMENT v135**
