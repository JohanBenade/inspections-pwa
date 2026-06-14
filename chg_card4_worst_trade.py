#!/usr/bin/env python3
"""
Replace KPI card 4 in the Top-10 build-quality report.

OLD: "Most Widespread Defect" -> points at a bare item word ("finish"), which
     is too thin to stand alone (duplicate item labels across rooms, no trade
     context). Low signal for a Raubex reader.

NEW: "Worst Trade" -> binds to trade_accountability[0] (already sorted
     worst-first by units-affected, analytics.py L8196). A trade name is
     actionable; the meta names the trade + unit count so the % is unambiguous.

  Label:  Worst Trade
  Value:  NN% of units            (trade_accountability[0].rate)
  Meta:   TRADE - N units affected (trade_accountability[0].trade / .units)

RUN ON: MACBOOK
    cd ~/Documents/GitHub/inspections-pwa && python3 chg_card4_worst_trade.py

Assert-guarded: aborts unless the old card block is found exactly once.
"""
import io, sys

PATH = "app/templates/analytics/top_10_per_area.html"

OLD = (
    '            <div class="kpi-tile" style="border-bottom: 4px solid #4A7C59;">\n'
    '                <div class="kpi-tile-label">Most Widespread Defect</div>\n'
    '                <div class="kpi-tile-value">{% if project_top10 %}{{ project_top10[0].rate }}%<span class="kpi-tile-suffix"> of units</span>{% else %}&mdash;{% endif %}</div>\n'
    '                <div class="kpi-tile-meta">{% if project_top10 %}{{ project_top10[0].item }}{% else %}no data{% endif %}</div>\n'
    '            </div>'
)

NEW = (
    '            <div class="kpi-tile" style="border-bottom: 4px solid #4A7C59;">\n'
    '                <div class="kpi-tile-label">Worst Trade</div>\n'
    '                <div class="kpi-tile-value">{% if trade_accountability %}{{ trade_accountability[0].rate }}%<span class="kpi-tile-suffix"> of units</span>{% else %}&mdash;{% endif %}</div>\n'
    '                <div class="kpi-tile-meta">{% if trade_accountability %}{{ trade_accountability[0].trade }} &middot; {{ trade_accountability[0].units }} units affected{% else %}no data{% endif %}</div>\n'
    '            </div>'
)

with io.open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

if "Worst Trade" in src:
    sys.exit("ABORT: 'Worst Trade' card already present. No change made.")

n = src.count(OLD)
if n != 1:
    sys.exit("ABORT: old card-4 block found %d times (expected 1). No change made." % n)

new_src = src.replace(OLD, NEW, 1)

if "Worst Trade" not in new_src or "trade_accountability[0].rate" not in new_src:
    sys.exit("ABORT: replacement verification failed. No change written.")

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(new_src)

print("OK: KPI card 4 replaced with Worst Trade in", PATH)
print("Verify: grep -n 'Worst Trade\\|trade_accountability\\[0\\]' app/templates/analytics/top_10_per_area.html")
