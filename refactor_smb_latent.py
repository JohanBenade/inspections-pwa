#!/usr/bin/env python3
"""
SMB Latent Defects refactor (single atomic commit):

  1. analytics.py: enrich _build_brief_latent so latent_by_area carries
     (area, count, affected_units, share_pct) instead of just (area, count).

  2. site_meeting_brief.html:
       a. Extract the current SECTION 03 LATENT DEFECTS block.
       b. Modify the extracted block:
            - section number 03 -> 08
            - SECTION 03 comment -> SECTION 08 comment
            - by-area table: add header row + Affected Units + Share columns
            - drop photo rendering in outstanding cards
            - drop photo rendering in rectified cards
       c. Remove the block from its current §03 position.
       d. Renumber the remaining sections back to their original numbers:
            §04 Fortnight Movement -> §03
            §05 Defect Pool        -> §04
            §06 Defects by Zone    -> §05
            §07 Defects by Trade   -> §06
            §08 Worst Units        -> §07
       e. Insert the modified Latent Defects block as new §08, just before
          the container-close </div> at end of body.
       f. Update the report subtitle: add a second smaller italic line with
          the scope qualifier.

Pre-flight asserts every anchor. Post-flight asserts every replacement
landed. Idempotency: aborts cleanly with [NO-OP] if SECTION 03 marker
is already gone.

Run from inspections-pwa repo root.
"""
from pathlib import Path

ANALYTICS = Path("app/routes/analytics.py")
TEMPLATE = Path("app/templates/analytics/site_meeting_brief.html")

assert ANALYTICS.exists(), f"Not found: {ANALYTICS}"
assert TEMPLATE.exists(), f"Not found: {TEMPLATE}"

# ============================================================================
# PART A - analytics.py: enrich latent_by_area
# ============================================================================

A1_OLD = """    outstanding_unit_ids = set()
    zone_outstanding = {}
    area_outstanding = {}
    blocks_seen = set()
    floors_seen = set()"""

A1_NEW = """    outstanding_unit_ids = set()
    zone_outstanding = {}
    area_outstanding = {}
    area_unit_ids = {}
    blocks_seen = set()
    floors_seen = set()"""

A2_OLD = """            area_outstanding[area_display] = (
                area_outstanding.get(area_display, 0) + 1
            )"""

A2_NEW = """            area_outstanding[area_display] = (
                area_outstanding.get(area_display, 0) + 1
            )
            area_unit_ids.setdefault(area_display, set()).add(n['unit_id'])"""

A3_OLD = """    by_area_sorted = sorted(
        area_outstanding.items(), key=lambda x: x[1], reverse=True
    )"""

A3_NEW = """    _total_out = len(outstanding)
    by_area_sorted = sorted(
        [
            (a, c, len(area_unit_ids.get(a, set())),
             int(round(100.0 * c / _total_out)) if _total_out else 0)
            for a, c in area_outstanding.items()
        ],
        key=lambda x: -x[1],
    )"""

# ============================================================================
# PART B - template: anchors for extract / remove / insert
# ============================================================================

S03_START = "    <!-- SECTION 03: LATENT DEFECTS -->"
S04_START = "    <!-- SECTION 04: FORTNIGHT MOVEMENT -->"

# Renumber back (mirror of build_smb_section_03.py's RENUMBERS list)
# §03-§06 spans use 12-space indent; §07 (Worst Units) has 16-space indent.
RENUMBERS = [
    ('<span class="section-number">04</span>\n            <span class="section-title">Fortnight Movement',
     '<span class="section-number">03</span>\n            <span class="section-title">Fortnight Movement'),
    ('<span class="section-number">05</span>\n            <span class="section-title">Defect Pool',
     '<span class="section-number">04</span>\n            <span class="section-title">Defect Pool'),
    ('<span class="section-number">06</span>\n            <span class="section-title">Defects by Zone',
     '<span class="section-number">05</span>\n            <span class="section-title">Defects by Zone'),
    ('<span class="section-number">07</span>\n            <span class="section-title">Defects by Trade',
     '<span class="section-number">06</span>\n            <span class="section-title">Defects by Trade'),
    ('<span class="section-number">08</span>\n                <span class="section-title">Worst Units',
     '<span class="section-number">07</span>\n                <span class="section-title">Worst Units'),
]

# End-of-document anchor (Worst Units close + container close + body close)
END_ANCHOR = """    </div>

</div>

</body>"""

# ============================================================================
# PART C - in-block modifications applied to the extracted latent block
# ============================================================================

# C1: section markers / number
C1_OLD = "<!-- SECTION 03: LATENT DEFECTS -->"
C1_NEW = "<!-- SECTION 08: LATENT DEFECTS -->"

C2_OLD = '<span class="section-number">03</span>'
C2_NEW = '<span class="section-number">08</span>'

# C3: by-area table - 2 cols -> 4 cols with header row
C3_OLD = """            <table style="width: 60%; border-collapse: collapse; font-size: 10px; font-feature-settings: 'lnum' 1, 'tnum' 1;">
                <tbody>
                    {% for area, cnt in latent_by_area %}
                    <tr>
                        <td style="padding: 4px 8px; border-bottom: 1px solid #F0EEEA; font-weight: 600;">{{ area }}</td>
                        <td style="text-align: right; padding: 4px 8px; border-bottom: 1px solid #F0EEEA; font-weight: 700; color: #C44D3F;">{{ cnt }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>"""

C3_NEW = """            <table style="width: 100%; border-collapse: collapse; font-size: 10px; font-feature-settings: 'lnum' 1, 'tnum' 1; table-layout: fixed;">
                <thead>
                    <tr>
                        <th style="text-align: left; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1;">Area</th>
                        <th style="text-align: right; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1; width: 70px;">Count</th>
                        <th style="text-align: right; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1; width: 120px;">Affected units</th>
                        <th style="text-align: right; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1; width: 70px;">Share</th>
                    </tr>
                </thead>
                <tbody>
                    {% for area, cnt, affected, share in latent_by_area %}
                    <tr>
                        <td style="padding: 4px 8px; border-bottom: 1px solid #F0EEEA; font-weight: 600;">{{ area }}</td>
                        <td style="text-align: right; padding: 4px 8px; border-bottom: 1px solid #F0EEEA; font-weight: 700; color: #C44D3F;">{{ cnt }}</td>
                        <td style="text-align: right; padding: 4px 8px; border-bottom: 1px solid #F0EEEA;">{{ affected }}</td>
                        <td style="text-align: right; padding: 4px 8px; border-bottom: 1px solid #F0EEEA;">{{ share }}%</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>"""

# C4: outstanding card photo removal
# Combine description line + photo block as anchor so the description's
# margin-bottom conditional is also cleaned up.
C4_OLD = """                <div style="font-size: 10px; line-height: 1.4; color: #1A1A1A; margin-bottom: {% if note.photos %}6px{% else %}0{% endif %};">{{ note.note_html | safe }}</div>
                {% if note.photos %}
                <table style="border-collapse: collapse;">
                    {% for p in note.photos %}
                    {% if loop.index0 % 3 == 0 %}<tr>{% endif %}
                    <td style="padding: 0 4px 4px 0; vertical-align: top;">
                        {% if p.src %}
                        <img src="{{ p.src }}" style="width: 90px; height: auto; display: block; border: 1px solid #ddd;">
                        {% endif %}
                    </td>
                    {% if loop.index % 3 == 0 or loop.last %}</tr>{% endif %}
                    {% endfor %}
                </table>
                {% endif %}"""

C4_NEW = """                <div style="font-size: 10px; line-height: 1.4; color: #1A1A1A; margin-bottom: 0;">{{ note.note_html | safe }}</div>"""

# C5: rectified card photo removal
C5_OLD = """                {% if note.photos %}
                <table style="border-collapse: collapse; margin-top: 4px;">
                    {% for p in note.photos %}
                    {% if loop.index0 % 3 == 0 %}<tr>{% endif %}
                    <td style="padding: 0 4px 4px 0; vertical-align: top;">
                        {% if p.src %}
                        <img src="{{ p.src }}" style="width: 60px; height: auto; display: block; border: 1px solid #ddd;">
                        {% endif %}
                    </td>
                    {% if loop.index % 3 == 0 or loop.last %}</tr>{% endif %}
                    {% endfor %}
                </table>
                {% endif %}
"""

C5_NEW = ""

# ============================================================================
# PART D - subtitle: add second smaller italic qualifier line
# ============================================================================

SUBTITLE_OLD = '        <div class="report-subtitle">Power Park Student Housing &mdash; Phase 3 &mdash; 191 four-bed Units</div>'

SUBTITLE_NEW = '''        <div class="report-subtitle">Power Park Student Housing &mdash; Phase 3 &mdash; 191 four-bed Units</div>
        <div class="report-subtitle" style="font-size: 10px; color: #9A9A9A; margin-top: 1px; font-style: italic; letter-spacing: 0.3px;">Scope: dwelling units only &mdash; other and external areas are excluded.</div>'''


# ============================================================================
# MAIN
# ============================================================================

def main():
    a = ANALYTICS.read_text()
    t = TEMPLATE.read_text()

    # ---- IDEMPOTENCY GUARD ----
    if S03_START not in t and "<!-- SECTION 08: LATENT DEFECTS -->" in t:
        print("[NO-OP] Latent block already at §08. Files unchanged.")
        raise SystemExit(0)

    # ---- PRE-FLIGHT: analytics.py ----
    assert A1_OLD in a, "A1 anchor missing"
    assert a.count(A1_OLD) == 1, f"A1 anchor not unique (count={a.count(A1_OLD)})"
    assert A2_OLD in a, "A2 anchor missing"
    assert a.count(A2_OLD) == 1, f"A2 anchor not unique (count={a.count(A2_OLD)})"
    assert A3_OLD in a, "A3 anchor missing"
    assert a.count(A3_OLD) == 1, f"A3 anchor not unique (count={a.count(A3_OLD)})"

    assert "area_unit_ids" not in a, "area_unit_ids already present in analytics.py"

    # ---- PRE-FLIGHT: template ----
    assert S03_START in t, "SECTION 03 LATENT DEFECTS marker missing"
    assert t.count(S03_START) == 1, f"SECTION 03 marker not unique (count={t.count(S03_START)})"
    assert S04_START in t, "SECTION 04 FORTNIGHT MOVEMENT marker missing"
    assert t.count(S04_START) == 1, f"SECTION 04 marker not unique"

    for i, (old, new) in enumerate(RENUMBERS, 1):
        assert old in t, f"RENUMBER {i} anchor missing: number ending span pattern not found"
        assert t.count(old) == 1, f"RENUMBER {i} not unique (count={t.count(old)})"

    assert END_ANCHOR in t, "END anchor (</div>\\n\\n</div>\\n\\n</body>) missing"
    assert t.count(END_ANCHOR) == 1, f"END anchor not unique (count={t.count(END_ANCHOR)})"

    assert SUBTITLE_OLD in t, "Subtitle anchor missing"
    assert t.count(SUBTITLE_OLD) == 1, f"Subtitle not unique (count={t.count(SUBTITLE_OLD)})"

    # ---- EXTRACT latent block ----
    start_idx = t.index(S03_START)
    end_idx = t.index(S04_START)
    assert start_idx < end_idx, "S03 marker appears after S04 marker (unexpected)"
    latent_block = t[start_idx:end_idx]

    # Validate the extracted block has the things we're about to mutate
    assert C1_OLD in latent_block, "C1 anchor (SECTION 03 comment) missing in extracted block"
    assert C2_OLD in latent_block, "C2 anchor (section-number 03) missing in extracted block"
    assert C3_OLD in latent_block, "C3 anchor (2-col by-area table) missing in extracted block"
    assert C4_OLD in latent_block, "C4 anchor (outstanding card desc+photos) missing in extracted block"
    assert C5_OLD in latent_block, "C5 anchor (rectified card photos) missing in extracted block"

    # ---- BUILD new §08 block in memory ----
    new_block = latent_block
    new_block = new_block.replace(C1_OLD, C1_NEW)
    new_block = new_block.replace(C2_OLD, C2_NEW)
    new_block = new_block.replace(C3_OLD, C3_NEW)
    new_block = new_block.replace(C4_OLD, C4_NEW)
    new_block = new_block.replace(C5_OLD, C5_NEW)

    # The extracted block ends with two trailing newlines (the blank line
    # before SECTION 04). Strip them so the insertion at end is clean.
    new_block_trimmed = new_block.rstrip("\n")

    # ---- APPLY template transforms in memory ----
    # 1. Remove latent block from §03 position
    t_new = t.replace(latent_block, "")

    # 2. Renumber sections 04..08 -> 03..07
    for old, new in RENUMBERS:
        t_new = t_new.replace(old, new)

    # 3. Insert new §08 block before container close
    end_replacement = "    </div>\n\n" + new_block_trimmed + "\n\n</div>\n\n</body>"
    t_new = t_new.replace(END_ANCHOR, end_replacement)

    # 4. Subtitle two-line update
    t_new = t_new.replace(SUBTITLE_OLD, SUBTITLE_NEW)

    # ---- APPLY analytics.py transforms in memory ----
    a_new = a
    a_new = a_new.replace(A1_OLD, A1_NEW)
    a_new = a_new.replace(A2_OLD, A2_NEW)
    a_new = a_new.replace(A3_OLD, A3_NEW)

    # ---- POST-FLIGHT: template ----
    assert "<!-- SECTION 03: LATENT DEFECTS -->" not in t_new, (
        "SECTION 03 marker still present (should be gone)"
    )
    assert "<!-- SECTION 08: LATENT DEFECTS -->" in t_new, (
        "SECTION 08 marker missing (should have been inserted)"
    )
    assert t_new.count("<!-- SECTION 08: LATENT DEFECTS -->") == 1, (
        "SECTION 08 marker not unique"
    )

    # Section title numbering checks (each title appears exactly once with new number)
    expected_renumbered = [
        ('section-number">03</span>\n            <span class="section-title">Fortnight Movement', 1),
        ('section-number">04</span>\n            <span class="section-title">Defect Pool', 1),
        ('section-number">05</span>\n            <span class="section-title">Defects by Zone', 1),
        ('section-number">06</span>\n            <span class="section-title">Defects by Trade', 1),
        ('section-number">07</span>\n                <span class="section-title">Worst Units', 1),
        ('section-number">08</span>\n                <span class="section-title">Latent Defects', 1),
    ]
    for needle, expected_count in expected_renumbered:
        actual = t_new.count(needle)
        assert actual == expected_count, (
            f"Renumber post-flight: expected {expected_count} occurrence(s) "
            f"of {needle!r}, found {actual}"
        )

    # By-area new shape
    assert "{% for area, cnt, affected, share in latent_by_area %}" in t_new, (
        "Enriched by-area for-loop missing in template"
    )
    assert "{% for area, cnt in latent_by_area %}" not in t_new, (
        "Old 2-tuple by-area for-loop still present"
    )

    # Photos removed in §08 block
    assert "{% if note.photos %}" not in t_new, (
        "Photo conditionals still present in template"
    )
    assert "encode_latent_photos" not in t_new, (
        "encode_latent_photos reference in template (unexpected)"
    )

    # Subtitle has both lines
    assert "Scope: dwelling units only" in t_new, "New subtitle qualifier missing"
    assert t_new.count('class="report-subtitle"') == 2, (
        f"Expected 2 report-subtitle divs, got {t_new.count('class=\"report-subtitle\"')}"
    )

    # ---- POST-FLIGHT: analytics.py ----
    assert "area_unit_ids = {}" in a_new, "area_unit_ids init missing"
    assert "area_unit_ids.setdefault(area_display, set()).add(n['unit_id'])" in a_new, (
        "area_unit_ids increment missing"
    )
    assert "_total_out = len(outstanding)" in a_new, "_total_out denom missing"
    assert "int(round(100.0 * c / _total_out))" in a_new, "Share computation missing"
    assert "area_outstanding.items(), key=lambda x: x[1], reverse=True" not in a_new, (
        "Old by_area_sorted still present"
    )

    # ---- WRITE ----
    ANALYTICS.write_text(a_new)
    TEMPLATE.write_text(t_new)

    print("[OK] SMB Latent Defects refactor applied.")
    print()
    print("Changes:")
    print(f"  - {ANALYTICS}: enriched latent_by_area (now 4-tuple)")
    print(f"  - {TEMPLATE}:")
    print(f"      * latent block moved from §03 to §08 (end of doc)")
    print(f"      * sections 04..08 renumbered back to 03..07")
    print(f"      * by-area table: header row + 4 columns (Area, Count, Affected units, Share)")
    print(f"      * photos removed (outstanding + rectified cards)")
    print(f"      * subtitle: added scope qualifier on second line")
    print()
    print("Verify: git --no-pager diff app/routes/analytics.py app/templates/analytics/site_meeting_brief.html")
    print("Deploy when Alex is paused (single commit).")


if __name__ == "__main__":
    main()
