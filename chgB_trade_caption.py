#!/usr/bin/env python3
"""
Change B - Top 10 report, Section 06 (Trade Accountability) caption.
Clarify the loose word "room" by naming the four areas explicitly.

  OLD: All room defects rolled up by trade discipline, ranked by units affected ...
  NEW: Defects from all four areas - Kitchen, Bathroom, Lounge, Bedrooms - rolled up
       by trade discipline, ranked by units affected ...

Matches the file's exact two-line layout and the &mdash; entities.

RUN ON: MACBOOK
    cd ~/Documents/GitHub/inspections-pwa && python3 chgB_trade_caption.py

Assert-guarded: aborts unless the anchor is found exactly once.
"""
import io, sys

PATH = "app/templates/analytics/top_10_per_area.html"

OLD = (
    "            All room defects rolled up by trade discipline, ranked by units affected &mdash; the subcontractors whose work most consistently\n"
    "            fell short at hand-over, and therefore who to brief hardest before the next phase."
)
NEW = (
    "            Defects from all four areas &mdash; Kitchen, Bathroom, Lounge, Bedrooms &mdash; rolled up by trade discipline, ranked by units\n"
    "            affected &mdash; the subcontractors whose work most consistently fell short at hand-over, and therefore who to brief hardest\n"
    "            before the next phase."
)

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

if "Defects from all four areas" in src:
    sys.exit("ABORT: new caption already present. No change made.")

n = src.count(OLD)
if n != 1:
    sys.exit("ABORT: caption anchor found %d times (expected 1). No change made." % n)

new_src = src.replace(OLD, NEW, 1)

if "Defects from all four areas" not in new_src:
    sys.exit("ABORT: replacement verification failed. No change written.")

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(new_src)

print("OK: Trade Accountability caption updated in", PATH)
print("Verify: grep -n 'four areas\\|room defects' app/templates/analytics/top_10_per_area.html")
