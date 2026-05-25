"""
v326b - include items-with-priors in desnag denominator

Removes 'AND ii.has_prior_defects = 0' filter from 4 queries in app/routes/inspection.py:
  - L~2455: items_row (initial page render, unit-wide total)
  - L~2472: items_per_area (initial page render, per-area rollup)
  - L~2823: _desnag_progress.i_row (HTMX progress update, unit-wide)
  - L~2870: _desnag_area_progress.i_row (HTMX progress update, per-area)

Why: per v315 workflow rule, inspector must MS/NTS every item, including items
with priors. Previously the denominator excluded items-with-priors so the
progress bar showed 123/125 = 98% on unit 011 when in fact 10 items-with-priors
were still pending MS/NTS. After v326b: 147/159 = 92%, denominator includes all
work items.

Side effect: aligns desnag items count with inspector home (both show 111/121
items for unit 011 after the patch).
"""
import pathlib

P = pathlib.Path('app/routes/inspection.py')
src = P.read_text()

old = "          AND ii.has_prior_defects = 0\n"
count = src.count(old)
assert count == 4, f"expected 4 occurrences of has_prior_defects=0 filter, found {count}"
src = src.replace(old, "")

P.write_text(src)
print(f"v326b applied: removed {count} occurrences of has_prior_defects=0 filter")
