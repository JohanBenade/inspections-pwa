#!/usr/bin/env python3
"""
SMB tweaks:
  - Chart SVG height: 200px -> 150px (frees space for legend paragraph
    on page 1, currently bleeds to page 2).
  - OUTSTANDING - BY ZONE: page-break-before: always so it starts on
    its own fresh page, separate from §08 header / KPI / By Area.
"""
from pathlib import Path

TEMPLATE = Path("app/templates/analytics/site_meeting_brief.html")
assert TEMPLATE.exists(), f"Not found: {TEMPLATE}"

# CHART HEIGHT: 200 -> 150
H_OLD = """        <svg viewBox="0 0 {{ chart_w + 20 }} {{ chart_h + 30 }}" xmlns="http://www.w3.org/2000/svg"
             style="width: 100%; height: 200px; margin: 0 auto 8px auto; display: block;">"""

H_NEW = """        <svg viewBox="0 0 {{ chart_w + 20 }} {{ chart_h + 30 }}" xmlns="http://www.w3.org/2000/svg"
             style="width: 100%; height: 150px; margin: 0 auto 4px auto; display: block;">"""

# OUTSTANDING wrapper: add page-break-before
P_OLD = """        <div style="margin-top: 12px;">
            <div style="font-size: 9px; font-weight: 600; color: #9A9A9A; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px;">Outstanding &mdash; by zone</div>"""

P_NEW = """        <div style="margin-top: 12px; page-break-before: always; padding-top: 8px;">
            <div style="font-size: 9px; font-weight: 600; color: #9A9A9A; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px;">Outstanding &mdash; by zone</div>"""


def main():
    t = TEMPLATE.read_text()

    h_done = 'height: 150px; margin: 0 auto 4px auto' in t
    p_done = 'page-break-before: always; padding-top: 8px;">\n            <div style="font-size: 9px; font-weight: 600; color: #9A9A9A; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px;">Outstanding' in t

    if h_done and p_done:
        print("[NO-OP] Already applied.")
        raise SystemExit(0)

    assert H_OLD in t, "Chart height anchor missing - was previous fix applied?"
    assert t.count(H_OLD) == 1, f"Chart anchor not unique (count={t.count(H_OLD)})"
    assert P_OLD in t, "OUTSTANDING wrapper anchor missing"
    assert t.count(P_OLD) == 1, f"OUTSTANDING anchor not unique (count={t.count(P_OLD)})"

    t_new = t.replace(H_OLD, H_NEW).replace(P_OLD, P_NEW)

    assert 'height: 150px; margin: 0 auto 4px auto' in t_new, "chart height not applied"
    assert 'height: 200px; margin: 0 auto 8px auto' not in t_new, "old chart height still present"
    assert 'page-break-before: always; padding-top: 8px;">' in t_new, "page-break not applied"

    TEMPLATE.write_text(t_new)
    print("[OK] Chart height -> 150px, OUTSTANDING gets page-break-before.")
    print("Verify: git --no-pager diff --stat")


if __name__ == "__main__":
    main()
