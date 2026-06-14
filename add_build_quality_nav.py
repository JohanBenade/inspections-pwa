#!/usr/bin/env python3
"""
Add 'Build Quality' nav link to base.html, in the shared
['team_lead','manager','admin'] block, immediately after the 'Outstanding' link.

Route: analytics.top10_per_area_view  (/build-quality, @require_team_lead)
Placement: option 1 (visible to team_lead/manager/admin - matches decorator).

RUN ON: MACBOOK
    cd ~/Documents/GitHub/inspections-pwa && python3 add_build_quality_nav.py

Assert-guarded: aborts if anchor is missing, not unique, or link already present.
"""
import io, sys

PATH = "app/templates/base.html"

ANCHOR = '                        <a href="{{ url_for(\'analytics.outstanding_items_view\') }}" class="text-xs text-gray-300 hover:text-white">Outstanding</a>'
NEWLINK = '                        <a href="{{ url_for(\'analytics.top10_per_area_view\') }}" class="text-xs text-gray-300 hover:text-white">Build Quality</a>'

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# Guard 1: link not already present (idempotent)
if "top10_per_area_view" in src:
    sys.exit("ABORT: 'top10_per_area_view' already referenced in base.html. No change made.")

# Guard 2: anchor exists exactly once
n = src.count(ANCHOR)
if n != 1:
    sys.exit("ABORT: anchor 'Outstanding' line found %d times (expected exactly 1). No change made." % n)

# Replace: anchor -> anchor + newline + new link
new_src = src.replace(ANCHOR, ANCHOR + "\n" + NEWLINK, 1)

# Guard 3: exactly one line added, nothing else moved
if new_src.count("\n") != src.count("\n") + 1:
    sys.exit("ABORT: line count delta != 1. No change written.")
if "top10_per_area_view" not in new_src:
    sys.exit("ABORT: new link not present after replace. No change written.")

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(new_src)

print("OK: Build Quality nav link added after Outstanding in", PATH)
print("Verify with: grep -n 'top10_per_area_view' app/templates/base.html")
