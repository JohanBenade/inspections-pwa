#!/usr/bin/env python3
"""
fix_total_units_templates.py
Commit 2 of the project-total live-count fix.
- Injects project_total into _build_pipeline_report_data and _build_rectification_data
- Replaces hardcoded 191 unit-count literals in rectification.html (5x)
  and site_meeting_brief.html (1x) with the project_total variable.
Run from repo root.
"""
import io

def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()

def write(p, s):
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(s)

# ============================================================
# 1. analytics.py — inject project_total into both return dicts
# ============================================================
AP = "app/routes/analytics.py"
src = read(AP)

# 1a. _build_pipeline_report_data return at 6491: insert after `return {`
PIPE_OLD = "    return {\n        'units_inspected': units_inspected,\n"
PIPE_NEW = ("    return {\n"
            "        'project_total': get_project_total_units(tenant_id),\n"
            "        'units_inspected': units_inspected,\n")
assert src.count(PIPE_OLD) == 1, "pipeline return anchor not unique/found"
src = src.replace(PIPE_OLD, PIPE_NEW)

# 1b. _build_rectification_data return at 2071: `return dict(has_data=True,`
REC_OLD = "    return dict(has_data=True,\n"
REC_NEW = "    return dict(has_data=True,\n                project_total=get_project_total_units(tenant_id),\n"
assert src.count(REC_OLD) == 1, "rectification return anchor not unique/found"
src = src.replace(REC_OLD, REC_NEW)

write(AP, src)
print("analytics.py: project_total injected into both builders")

# ============================================================
# 2. rectification.html — 5 literal 191s -> project_total
# ============================================================
RH = "app/templates/analytics/rectification.html"
r = read(RH)

reps = [
    ("of 191 ({{ (pp_not_started / 191 * 100)|round|int }}%)",
     "of {{ project_total }} ({{ (pp_not_started / project_total * 100)|round|int }}%)"),
    ("of {{ 191 - pp_not_started }} inspected",
     "of {{ project_total - pp_not_started }} inspected"),
    ("of 191 ({{ (pp_certified / 191 * 100)|round|int }}%)",
     "of {{ project_total }} ({{ (pp_certified / project_total * 100)|round|int }}%)"),
    ("return 'Total: ' + total + ' / 191';",
     "return 'Total: ' + total + ' / {{ project_total }}';"),
    ("max: 191,",
     "max: {{ project_total }},"),
]
for old, new in reps:
    assert r.count(old) == 1, "rectification anchor missing/non-unique: %r" % old
    r = r.replace(old, new)
assert "191" not in r, "rectification.html still has a 191 literal"
write(RH, r)
print("rectification.html: 5 literals replaced")

# ============================================================
# 3. site_meeting_brief.html — subtitle 191 -> {{ project_total }}
# ============================================================
SMB = "app/templates/analytics/site_meeting_brief.html"
s = read(SMB)
SMB_OLD = "Phase 3 &mdash; 191 four-bed Units"
SMB_NEW = "Phase 3 &mdash; {{ project_total }} four-bed Units"
assert s.count(SMB_OLD) == 1, "SMB subtitle anchor missing/non-unique"
s = s.replace(SMB_OLD, SMB_NEW)
assert "191" not in s, "site_meeting_brief.html still has a 191 literal"
write(SMB, s)
print("site_meeting_brief.html: subtitle replaced")

print("ALL OK")
