# Inspections PWA - Handover Document
**Date:** 28 January 2026  
**Version:** v24 (Session 2)  
**Status:** Multiple fixes applied, navigation changes UNTESTED  

---

## 1. PROJECT CONTEXT

### Client
- **Company:** Monograph Architects (Kevin Coetzee)
- **Contractor:** Raubex
- **Project:** Power Park / Soshanguve Student Housing - Phase 1
- **Domain:** archops.co.za (not yet deployed)

### User
- IT/PM background, not a coder
- Designs Notion systems for SA architectural firms
- Uses Claude for system/database design and coding

### Purpose
Mobile-first PWA for construction defect inspections:
- **Students** - Conduct inspections, mark items, raise defects
- **Kevin (Architect)** - Manage cycles, review inspections, certify units

---

## 2. ARCHITECTURE OVERVIEW

### Tech Stack
```
Frontend: HTMX + Tailwind CSS (CDN)
Backend:  Flask (Python)
Database: SQLite
Hosting:  Render (planned)
```

### Schema Hierarchy
```
Project
  -> Phase
       -> Unit (block/floor fields exist but unused)
       -> Inspection Cycle (created by architect)
            -> Cycle Area Notes
            -> Cycle Excluded Items
            -> Inspection (one per unit per cycle)
                 -> Inspection Items

Templates (by unit_type):
  Area (KITCHEN, BATHROOM, BEDROOM)
    -> Category (DOORS, PLUMBING, ELECTRICAL)
         -> Item (self-referencing for parent/child)
              parent_item_id = NULL, depth = 0  --> Parent
              parent_item_id = X, depth = 1     --> Sub-item
```

### Key Design Decisions
- **Cycle-based workflow**: Architect creates cycles, students inspect within cycles
- **Self-referencing items**: Single `item_template` table with parent_item_id (TECH DEBT - see section 8)
- **Progress counts parent items only**: 18 parents tracked, children follow parent status
- **Area-specific notes**: Kevin can add notes per area per cycle

---

## 3. CURRENT SESSION FIXES

### Bug Fixes Applied
| Issue | Fix | Files Modified |
|-------|-----|----------------|
| Dict method collision | `category.items` -> `category.checklist` | inspection.py, area.html |
| Progress count mismatch | Count only parent items (parent_item_id IS NULL) | inspection.py (2 places) |
| Jinja2 math unreliable | Calculate `progress['active']` in Python | inspection.py, _progress.html |
| Unit display format | Show "Unit 001" not "4-Bed" | projects.py, certification.py, defects.py, phase.html |
| Standalone item buttons | Items with no children get OK/N.T.S./N/I buttons | inspection.py (child_count query), area.html |
| Setup FK constraint | Delete in correct dependency order | setup_project.py |
| Excluded category notes | Show area note when all items skipped | area.html |

### Features Added
| Feature | Details | Files |
|---------|---------|-------|
| Cycle area notes | Notes per area (KITCHEN, BATHROOM, BEDROOM) | schema.sql, cycles.py, edit.html, view.html, area.html |
| Delete cycle | Only if no inspections exist | cycles.py, list.html, view.html |
| Student cycle selection | Unit page shows active cycles with Start/Continue | projects.py, unit.html |

### UNTESTED Changes (Navigation)
| Change | Details | Files |
|--------|---------|-------|
| Kevin header nav | Added: Cycles / Certify / Defects links | base.html |
| Kevin mobile nav | Added: Cycles + Certify tabs | base.html |
| Desktop logout link | Added to header | base.html |

---

## 4. FILE STRUCTURE

```
inspections-pwa/
├── app/
│   ├── __init__.py           # Flask app factory, home route
│   ├── auth.py               # Login decorators
│   ├── utils.py              # generate_id()
│   ├── routes/
│   │   ├── cycles.py         # Kevin: cycle management (CRUD)
│   │   ├── inspection.py     # Student: inspection flow
│   │   ├── certification.py  # Kevin: certify dashboard
│   │   ├── projects.py       # Student: navigation
│   │   └── defects.py        # Defect register (shared)
│   ├── services/
│   │   ├── db.py             # Database connection
│   │   ├── schema.sql        # v2.0 with cycles
│   │   └── template_seed.sql # Test checklist (50 items)
│   └── templates/
│       ├── base.html         # Layout + navigation (MODIFIED)
│       ├── cycles/           # Kevin's cycle management
│       ├── inspection/       # Student inspection flow
│       ├── certification/    # Kevin's certify dashboard
│       └── projects/         # Student navigation
├── config/
│   └── soshanguve.json       # 10 test units
├── scripts/
│   └── setup_project.py      # Creates demo data
└── HANDOVER_v24_Session2.md  # This file
```

---

## 5. SETUP & TESTING

### Fresh Setup Commands
```bash
cd ~/Downloads
rm -rf inspections-pwa
unzip inspections-pwa-v24.zip
cd inspections-pwa
rm -rf data
python3 -c "from app import create_app; create_app()"
python3 scripts/setup_project.py
python3 -m flask --app app run --debug --port 5000
```

### Login URLs
- **Kevin (architect):** `http://127.0.0.1:5000/login?u=insp-002`
- **Student:** `http://127.0.0.1:5000/login?u=insp-001`

### Browser Strategy
- Chrome Incognito: Kevin
- Chrome Guest: Student

### Test Data
- 10 units: 001-005 (Floor 0), 006-010 (Floor 1)
- Template: 18 parent items, 32 sub-items = 50 total
- 3 areas: KITCHEN, BATHROOM, BEDROOM
- 9 categories

---

## 6. TESTING CHECKLIST

### Kevin Flow (NEEDS TESTING)
- [ ] Login redirects to /cycles/
- [ ] Header shows: Cycles | Certify | Defects | Logout
- [ ] Mobile bottom nav shows: Cycles | Certify | Register | Logout
- [ ] Create Cycle 1
- [ ] Edit Cycle - add area notes (KITCHEN: "Electrical not installed")
- [ ] Edit Cycle - exclude 4 ELECTRICAL items
- [ ] View Cycle - shows area notes + excluded items
- [ ] Delete Cycle (only visible if no inspections)
- [ ] Certify dashboard shows units by status

### Student Flow
- [ ] Login redirects to /projects/
- [ ] Navigate: Project -> Phase -> Unit
- [ ] Unit page shows "Active Inspection Cycles" with Start button
- [ ] Start inspection in Cycle 1
- [ ] Progress shows "0/14 items (4 excluded)" initially
- [ ] KITCHEN tab shows area note at top
- [ ] ELECTRICAL category shows "Excluded this cycle"
- [ ] Mark items OK / N.T.S. / N/I
- [ ] Standalone items (Floor tiles, Mirror) have OK/N.T.S./N/I buttons
- [ ] Parent items with children (D1 - Main Entry) have Installed/Not Installed buttons
- [ ] Submit inspection
- [ ] Unit page shows "Cycle 1" in history

---

## 7. KNOWN ISSUES / LIMITATIONS

### Working
- Cycle creation, editing, closing, reopening, deleting
- Area-specific notes
- Item exclusions
- Progress tracking (parent items only)
- Standalone vs parent-with-children button logic

### Not Implemented
- PDF generation (parked - needs hierarchy fix)
- Cycle unit ranges (Cycle 1 for 001-010, Cycle 2 for 011-020)
- PWA icons (placeholders in place)
- Deployment to Render

### Potential Issues
- Old inspection data may show wrong progress (needs fresh DB)
- `round_type` column may not exist in older DBs (removed from v24)

---

## 8. TECH DEBT: ITEM/SUB-ITEM REFACTOR

### Current Approach (Self-Referencing)
```sql
item_template (
    id, category_id, parent_item_id, depth, item_description
)
-- parent_item_id = NULL, depth = 0  --> Parent item
-- parent_item_id = X, depth = 1     --> Sub-item
```

### Problems
1. Every query needs `WHERE parent_item_id IS NULL` to get parents
2. Progress counting bugs (already fixed twice)
3. Complex UI logic: `is_parent and has_children` vs standalone
4. Doesn't match domain (Excel has Items and Sub-items, not recursive tree)

### Recommended Refactor
```sql
item_template (
    id, category_id, item_description, item_order
    -- Always a main item: D1, Sink, Floor tiles
)

sub_item_template (
    id, item_id, sub_item_description, sub_item_order
    -- Always a detail: frame, hinges, bowl & finish
)
```

### Impact
- ~15-20 files need updates
- Cleaner queries, lower bug risk
- Better match to Excel template structure
- Recommend doing this with fresh token budget

---

## 9. NEXT PRIORITIES

1. **Test navigation changes** - Kevin header/mobile nav
2. **Complete student flow testing** - Full cycle from start to submit
3. **Item/Sub-item refactor** - Separate tables (tech debt)
4. **Cycle unit ranges** - Allow cycles for specific unit ranges
5. **PDF generation** - Match Excel hierarchy
6. **Deploy to Render** - Production setup

---

## 10. PROJECT FILES

| File | Location |
|------|----------|
| This handover | `HANDOVER_v24_Session2.md` |
| Previous handover | `/mnt/project/Inspections_PWA_Handover_v24_28Jan2026.md` |
| Excel template | `/mnt/project/Defective_works_Unit_empty_20260126.xlsx` |
| Logo | `/mnt/project/Monograph_Architects_Logo_Black_on_White.jpg` |
| Signature | `/mnt/project/KC_Signiture.png` |

---

## 11. SESSION TRANSCRIPT

Previous session transcript: `/mnt/transcripts/2026-01-28-09-39-50-inspections-pwa-v24-progress-units-exclusions-fix.txt`

This session covered:
- Progress calculation fixes
- Unit display format
- Standalone item buttons
- Area notes per cycle
- Navigation improvements (untested)
- Delete cycle feature
- Student cycle selection
- Tech debt analysis (item/sub-item)

---

**End of Handover Document**
