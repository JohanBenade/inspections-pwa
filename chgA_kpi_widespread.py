#!/usr/bin/env python3
"""
Change A - Top 10 report, Section 01, 4th KPI card.
Clarify the 94%: it is a units-affected prevalence rate.

  Label:  Worst Defect            -> Most Widespread Defect
  Value:  94%                     -> 94% <suffix>of units</suffix>
  Meta:   item name (unchanged)

Reuses the existing .kpi-tile-suffix span (same styling as card 1's "of 190").

RUN ON: MACBOOK
    cd ~/Documents/GitHub/inspections-pwa && python3 chgA_kpi_widespread.py

Assert-guarded: aborts unless each anchor is found exactly once.
"""
import io, sys

PATH = "app/templates/analytics/top_10_per_area.html"

OLD_LABEL = '<div class="kpi-tile-label">Worst Defect</div>'
NEW_LABEL = '<div class="kpi-tile-label">Most Widespread Defect</div>'

OLD_VALUE = '<div class="kpi-tile-value">{% if project_top10 %}{{ project_top10[0].rate }}%{% else %}&mdash;{% endif %}</div>'
NEW_VALUE = '<div class="kpi-tile-value">{% if project_top10 %}{{ project_top10[0].rate }}%<span class="kpi-tile-suffix"> of units</span>{% else %}&mdash;{% endif %}</div>'

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# Idempotency guard
if "Most Widespread Defect" in src:
    sys.exit("ABORT: 'Most Widespread Defect' already present. No change made.")

for label, anchor in (("LABEL", OLD_LABEL), ("VALUE", OLD_VALUE)):
    n = src.count(anchor)
    if n != 1:
        sys.exit("ABORT: %s anchor found %d times (expected 1). No change made." % (label, n))

new_src = src.replace(OLD_LABEL, NEW_LABEL, 1).replace(OLD_VALUE, NEW_VALUE, 1)

if "Most Widespread Defect" not in new_src or "of units</span>" not in new_src:
    sys.exit("ABORT: replacement verification failed. No change written.")

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(new_src)

print("OK: KPI card 4 updated in", PATH)
print("Verify: grep -n 'Most Widespread\\|of units' app/templates/analytics/top_10_per_area.html")
