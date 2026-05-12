#!/usr/bin/env python3
"""
build_smb_section_03.py
=======================
Add SMB §03 Latent Defects to the Site Meeting Brief.

Touches two files in one atomic commit:

  app/routes/analytics.py
    - Inserts _build_brief_latent(tenant_id, snap_str, prev_cutoff_str)
      just before _build_brief_by_trade(...)  (sibling helper family).
    - Wires both site_meeting_brief_view() and site_meeting_brief_pdf()
      to call _build_brief_latent() and encode_latent_photos() after the
      existing _build_brief_by_trade() call.

  app/templates/analytics/site_meeting_brief.html
    - §01 status-strip: appends a header line summarising project-wide
      latent counts (rendered only if total_identified > 0).
    - Inserts new §03 LATENT DEFECTS block after §02 De-snag Results,
      before the existing FORTNIGHT MOVEMENT section.
    - Renumbers section-number spans: 03→04, 04→05, 05→06, 06→07, 07→08.

Transactional pattern:
  1. Read both files.
  2. Run all pre-flight assertions (anchors exist, are unique, not already-applied).
  3. Compute new contents in memory.
  4. Run all post-flight assertions.
  5. ONLY THEN write both files.

If any assertion fails, no writes happen. Re-run after fixing the source.

Idempotency guard: refuses to run if _build_brief_latent or
SECTION 03: LATENT DEFECTS already present.
"""
from pathlib import Path
import re

# ============================================================================
# FILES
# ============================================================================

ANALYTICS = Path("app/routes/analytics.py")
TEMPLATE  = Path("app/templates/analytics/site_meeting_brief.html")

# ============================================================================
# ANALYTICS.PY — new function (inserted before _build_brief_by_trade)
# ============================================================================

# Raw string (r'''...''') so the inner triple-double-quoted SQL docstrings
# don't clash with the outer wrapper.
NEW_LATENT_FUNCTION = r'''def _build_brief_latent(tenant_id, snap_str, prev_cutoff_str):
    """Brief s3: project-wide latent defects with fortnight-aware split.

    Returns:
      latent_notes_list: combined outstanding (oldest first) +
        rectified-this-fortnight (most recent first). Each note carries
        unit_number, block, floor, area_display_name, age_days,
        is_rectified, created_at_fmt, rectified_at_fmt, photos.
      latent_brief_summary: dict with outstanding_count, affected_units_count,
        rectified_this_fortnight_count, rectified_to_date_count,
        oldest_days_open, total_identified.
      latent_zone_grid: {blocks, floors, data} for outstanding-only spatial.
      latent_by_area: list of (area_name, count) tuples, outstanding only,
        sorted by count desc.

    Predicates (snap-frozen):
      existing at snap        : n.created_at <= snap_str
      outstanding at snap     : n.rectified_at IS NULL OR n.rectified_at > snap_str
      rectified at snap       : n.rectified_at <= snap_str
      rectified this fortnight: prev_cutoff_str < n.rectified_at <= snap_str
    """
    import datetime

    rows = query_db("""
        SELECT n.id, n.unit_id, n.cycle_id, n.cycle_number, n.note_html,
               n.area_template_id, n.area_name_override, n.created_at,
               n.rectified_at_cycle_number, n.rectified_at,
               at.area_name, at.area_order,
               u.unit_number, u.block, u.floor
        FROM latent_area_note n
        LEFT JOIN area_template at ON n.area_template_id = at.id
        JOIN unit_real u ON n.unit_id = u.id
        WHERE n.tenant_id = ?
          AND n.created_at <= ?
          AND u.unit_number NOT LIKE 'TEST%'
        ORDER BY n.created_at
    """, [tenant_id, snap_str])

    if not rows:
        return {
            'latent_notes_list': [],
            'latent_brief_summary': {
                'outstanding_count': 0,
                'affected_units_count': 0,
                'rectified_this_fortnight_count': 0,
                'rectified_to_date_count': 0,
                'oldest_days_open': 0,
                'total_identified': 0,
            },
            'latent_zone_grid': {'blocks': [], 'floors': [], 'data': {}},
            'latent_by_area': [],
        }

    snap_dt = datetime.datetime.strptime(snap_str, '%Y-%m-%d %H:%M:%S')

    def _fmt_date(iso):
        if not iso or len(iso) < 10:
            return ''
        return '{}.{}.{}'.format(iso[8:10], iso[5:7], iso[:4])

    outstanding = []
    rectified_fortnight = []
    rectified_to_date_count = 0
    outstanding_unit_ids = set()
    zone_outstanding = {}
    area_outstanding = {}
    blocks_seen = set()
    floors_seen = set()

    for r in rows:
        n = dict(r)
        rectified_at = n.get('rectified_at')
        is_rectified_at_snap = bool(rectified_at and rectified_at <= snap_str)
        is_rectified_this_fortnight = bool(
            rectified_at and prev_cutoff_str < rectified_at <= snap_str
        )
        area_display = (
            n.get('area_name') or n.get('area_name_override') or 'Other'
        )

        if is_rectified_at_snap:
            rectified_to_date_count += 1
            if is_rectified_this_fortnight:
                n['is_rectified'] = True
                n['created_at_fmt'] = _fmt_date(n.get('created_at'))
                n['rectified_at_fmt'] = _fmt_date(rectified_at)
                n['area_display_name'] = area_display
                n['age_days'] = 0
                rectified_fortnight.append(n)
        else:
            outstanding_unit_ids.add(n['unit_id'])
            zone_outstanding[(n['block'], n['floor'])] = (
                zone_outstanding.get((n['block'], n['floor']), 0) + 1
            )
            blocks_seen.add(n['block'])
            floors_seen.add(n['floor'])
            area_outstanding[area_display] = (
                area_outstanding.get(area_display, 0) + 1
            )
            n['is_rectified'] = False
            n['created_at_fmt'] = _fmt_date(n.get('created_at'))
            n['rectified_at_fmt'] = None
            n['area_display_name'] = area_display
            try:
                created_dt = datetime.datetime.strptime(
                    n['created_at'][:19], '%Y-%m-%d %H:%M:%S'
                )
                n['age_days'] = (snap_dt - created_dt).days
            except Exception:
                n['age_days'] = 0
            outstanding.append(n)

    outstanding.sort(key=lambda x: -x['age_days'])
    rectified_fortnight.sort(
        key=lambda x: x.get('rectified_at') or '', reverse=True
    )
    visible_notes = outstanding + rectified_fortnight

    if visible_notes:
        note_ids = [n['id'] for n in visible_notes]
        placeholders = ','.join('?' * len(note_ids))
        photo_rows = query_db("""
            SELECT id, latent_area_note_id, file_path, mime_type,
                   display_order, original_filename
            FROM latent_photo
            WHERE tenant_id = ? AND latent_area_note_id IN ({})
            ORDER BY latent_area_note_id, display_order
        """.format(placeholders), [tenant_id] + note_ids)
        photos_by_note = {}
        for p in photo_rows:
            pd = dict(p)
            photos_by_note.setdefault(pd['latent_area_note_id'], []).append(pd)
        for n in visible_notes:
            n['photos'] = photos_by_note.get(n['id'], [])

    oldest_days = max((n['age_days'] for n in outstanding), default=0)
    by_area_sorted = sorted(
        area_outstanding.items(), key=lambda x: x[1], reverse=True
    )

    return {
        'latent_notes_list': visible_notes,
        'latent_brief_summary': {
            'outstanding_count': len(outstanding),
            'affected_units_count': len(outstanding_unit_ids),
            'rectified_this_fortnight_count': len(rectified_fortnight),
            'rectified_to_date_count': rectified_to_date_count,
            'oldest_days_open': oldest_days,
            'total_identified': len(outstanding) + rectified_to_date_count,
        },
        'latent_zone_grid': {
            'blocks': sorted(blocks_seen),
            'floors': sorted(floors_seen),
            'data': zone_outstanding,
        },
        'latent_by_area': by_area_sorted,
    }


'''  # NEW_LATENT_FUNCTION ends with trailing blank line so it lands cleanly before _build_brief_by_trade

# ============================================================================
# ANALYTICS.PY — route handler update (applies to both view and pdf)
# ============================================================================

A_FUNC_ANCHOR = "def _build_brief_by_trade(tenant_id, snap_str, prev_cutoff_str):"

A_ROUTE_OLD = (
    "    data.update(_build_brief_by_trade(_tenant, data['snapshot_str'], _prev_cutoff))"
)
A_ROUTE_NEW = (
    "    data.update(_build_brief_by_trade(_tenant, data['snapshot_str'], _prev_cutoff))\n"
    "    data.update(_build_brief_latent(_tenant, data['snapshot_str'], _prev_cutoff))\n"
    "    from app.services.pdf_generator import encode_latent_photos\n"
    "    encode_latent_photos(data)"
)

# ============================================================================
# TEMPLATE — §01 status-strip extra line
# ============================================================================

T_HEADER_OLD = (
    "                Inspection scope: 454 items per unit &middot; project exclusion list of 55 items applied.\n"
    "            </div>"
)
T_HEADER_NEW = (
    "                Inspection scope: 454 items per unit &middot; project exclusion list of 55 items applied.\n"
    "            </div>\n"
    "            {% if latent_brief_summary and latent_brief_summary.total_identified > 0 %}\n"
    "            <div class=\"line\" style=\"color: #6B6B6B; font-size: 12px;\">\n"
    "                <span class=\"num\">{{ latent_brief_summary.total_identified }}</span> latent defects identified during de-snag (<span class=\"num\">{{ latent_brief_summary.affected_units_count }}</span> units affected, <span class=\"num\">{{ latent_brief_summary.rectified_to_date_count }}</span> rectified to date).\n"
    "            </div>\n"
    "            {% endif %}"
)

# ============================================================================
# TEMPLATE — §03 LATENT DEFECTS insertion (before existing FORTNIGHT MOVEMENT)
# ============================================================================

T_S03_OLD = (
    "    {% endif %}\n"
    "\n"
    "    <!-- SECTION 04: FORTNIGHT MOVEMENT -->"
)

# Build the §03 block as a single string. Use double-quoted f-strings would
# clash with Jinja braces, so just use a triple-quoted raw r-string.
T_S03_BLOCK = r"""    <!-- SECTION 03: LATENT DEFECTS -->
    {% if latent_brief_summary %}
    <div class="section" style="margin-bottom: 18px; page-break-before: always; break-before: page;">
        <div class="section-header" style="display: flex; justify-content: space-between; align-items: baseline;">
            <div>
                <span class="section-number">03</span>
                <span class="section-title">Latent Defects</span>
            </div>
            {% if latent_brief_summary.outstanding_count > 0 or latent_brief_summary.rectified_this_fortnight_count > 0 %}
            <div style="font-size: 10px; color: #5F5E5A; font-feature-settings: 'lnum' 1, 'tnum' 1;">
                <span style="color: #C44D3F; font-weight: 600;">{{ latent_brief_summary.outstanding_count }}</span> outstanding &middot;
                <span style="color: #4A7C59; font-weight: 600;">{{ latent_brief_summary.rectified_this_fortnight_count }}</span> rectified this fortnight &middot;
                {{ latent_brief_summary.rectified_to_date_count }} rectified to date
            </div>
            {% endif %}
        </div>

        <p style="font-size: 10px; font-style: italic; color: #6B6B6B; margin: 0 0 12px 0;">Defects identified by team leads during de-snagging. Recorded for rectification during the contract period.</p>

        {% if latent_brief_summary.outstanding_count == 0 and latent_brief_summary.rectified_this_fortnight_count == 0 %}
        <div class="trend-placeholder">No latent defects identified this fortnight.</div>
        {% else %}

        {% if latent_brief_summary.outstanding_count > 0 %}
        <div class="rate-cards" style="grid-template-columns: 1fr 1fr 1fr;">
            <div class="rate-card">
                <div class="label">Outstanding</div>
                <div class="value" style="color: #C44D3F;">{{ latent_brief_summary.outstanding_count }}</div>
            </div>
            <div class="rate-card">
                <div class="label">Affected Units</div>
                <div class="value">{{ latent_brief_summary.affected_units_count }}</div>
            </div>
            <div class="rate-card">
                <div class="label">Oldest Open</div>
                <div class="value">{{ latent_brief_summary.oldest_days_open }}<span style="font-size: 11px; font-weight: 400; color: #6B6B6B; margin-left: 4px;">days</span></div>
            </div>
        </div>
        {% endif %}

        {% if latent_zone_grid and latent_zone_grid.blocks %}
        <div style="margin-top: 14px;">
            <div style="font-size: 9px; font-weight: 600; color: #9A9A9A; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 6px;">Distribution by Zone (outstanding)</div>
            <div style="display: grid; grid-template-columns: 60px repeat({{ latent_zone_grid.floors|length }}, 1fr); gap: 4px;">
                <div></div>
                {% for fl in latent_zone_grid.floors %}
                <div style="text-align: center; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 0.8px; text-transform: uppercase; padding-bottom: 3px;">{{ floor_labels.get(fl, fl) }}</div>
                {% endfor %}
                {% for block in latent_zone_grid.blocks %}
                <div style="display: flex; align-items: center; font-size: 9px; font-weight: 600; color: #1A1A1A;">{{ block }}</div>
                {% for fl in latent_zone_grid.floors %}
                {% set cnt = latent_zone_grid.data.get((block, fl), 0) %}
                <div style="background: {% if cnt > 0 %}#FBE8E5{% else %}#F5F3EE{% endif %}; border: 1px solid #DCD7CB; border-radius: 5px; padding: 10px 5px; text-align: center; min-height: 44px; display: flex; align-items: center; justify-content: center;">
                    {% if cnt > 0 %}
                    <span style="font-size: 15px; font-weight: 700; color: #C44D3F;">{{ cnt }}</span>
                    {% else %}
                    <span style="font-size: 10px; color: #BFBDB8;">&mdash;</span>
                    {% endif %}
                </div>
                {% endfor %}
                {% endfor %}
            </div>
        </div>
        {% endif %}

        {% if latent_by_area %}
        <div style="margin-top: 14px;">
            <div style="font-size: 9px; font-weight: 600; color: #9A9A9A; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 4px;">By Area (outstanding)</div>
            <table style="width: 60%; border-collapse: collapse; font-size: 10px; font-feature-settings: 'lnum' 1, 'tnum' 1;">
                <tbody>
                    {% for area, cnt in latent_by_area %}
                    <tr>
                        <td style="padding: 4px 8px; border-bottom: 1px solid #F0EEEA; font-weight: 600;">{{ area }}</td>
                        <td style="text-align: right; padding: 4px 8px; border-bottom: 1px solid #F0EEEA; font-weight: 700; color: #C44D3F;">{{ cnt }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}

        {% if latent_brief_summary.outstanding_count > 0 %}
        <div style="margin-top: 16px;">
            <div style="font-size: 9px; font-weight: 600; color: #9A9A9A; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px;">Outstanding ({{ latent_brief_summary.outstanding_count }}) &mdash; oldest first</div>
            {% for note in latent_notes_list %}
            {% if not note.is_rectified %}
            <div style="margin-bottom: 12px; padding: 8px 10px; border-left: 2px solid #C44D3F; background: #FAFAF8; page-break-inside: avoid; break-inside: avoid-page;">
                <div style="font-size: 10px; color: #1A1A1A; margin-bottom: 4px;">
                    <span style="font-weight: 700;">Unit {{ note.unit_number }}</span>
                    <span style="color: #9A9A9A;"> &middot; </span>
                    <span style="font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">{{ note.area_display_name }}</span>
                    <span style="color: #9A9A9A;"> &middot; </span>
                    <span>C{{ note.cycle_number }}</span>
                    <span style="color: #9A9A9A;"> &middot; </span>
                    <span style="color: #C44D3F; font-weight: 600;">{{ note.age_days }} days open</span>
                </div>
                <div style="font-size: 10px; line-height: 1.4; color: #1A1A1A; margin-bottom: {% if note.photos %}6px{% else %}0{% endif %};">{{ note.note_html | safe }}</div>
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
                {% endif %}
            </div>
            {% endif %}
            {% endfor %}
        </div>
        {% endif %}

        {% if latent_brief_summary.rectified_this_fortnight_count > 0 %}
        <div style="margin-top: 16px;">
            <div style="font-size: 9px; font-weight: 600; color: #9A9A9A; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px;">Rectified This Fortnight ({{ latent_brief_summary.rectified_this_fortnight_count }})</div>
            {% for note in latent_notes_list %}
            {% if note.is_rectified %}
            <div style="margin-bottom: 8px; padding: 6px 10px; border-left: 2px solid #4A7C59; background: #F7FBF7; page-break-inside: avoid; break-inside: avoid-page;">
                <div style="font-size: 10px; color: #1A1A1A;">
                    <span style="font-weight: 700;">Unit {{ note.unit_number }}</span>
                    <span style="color: #9A9A9A;"> &middot; </span>
                    <span style="font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">{{ note.area_display_name }}</span>
                    <span style="color: #9A9A9A;"> &middot; </span>
                    <span style="color: #4A7C59; font-weight: 600;">Rectified C{{ note.rectified_at_cycle_number }} ({{ note.rectified_at_fmt }})</span>
                </div>
                {% if note.photos %}
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
            </div>
            {% endif %}
            {% endfor %}
        </div>
        {% endif %}

        {% endif %}
    </div>
    {% endif %}

    <!-- SECTION 04: FORTNIGHT MOVEMENT -->"""

T_S03_NEW = (
    "    {% endif %}\n"
    "\n"
    + T_S03_BLOCK
)

# ============================================================================
# TEMPLATE — section-number renumber pairs (03→04, 04→05, 05→06, 06→07, 07→08)
# ============================================================================

# §03-§06 spans use 12-space indent (the section-title line continues the indent).
# §07 has 16-space indent because it's nested inside an extra <div> wrapper.
RENUMBERS = [
    (
        '<span class="section-number">03</span>\n'
        '            <span class="section-title">Fortnight Movement',
        '<span class="section-number">04</span>\n'
        '            <span class="section-title">Fortnight Movement',
    ),
    (
        '<span class="section-number">04</span>\n'
        '            <span class="section-title">Defect Pool',
        '<span class="section-number">05</span>\n'
        '            <span class="section-title">Defect Pool',
    ),
    (
        '<span class="section-number">05</span>\n'
        '            <span class="section-title">Defects by Zone',
        '<span class="section-number">06</span>\n'
        '            <span class="section-title">Defects by Zone',
    ),
    (
        '<span class="section-number">06</span>\n'
        '            <span class="section-title">Defects by Trade',
        '<span class="section-number">07</span>\n'
        '            <span class="section-title">Defects by Trade',
    ),
    (
        '<span class="section-number">07</span>\n'
        '                <span class="section-title">Worst Units',
        '<span class="section-number">08</span>\n'
        '                <span class="section-title">Worst Units',
    ),
]

# ============================================================================
# MAIN
# ============================================================================

def main():
    assert ANALYTICS.exists(), f"Not found: {ANALYTICS}"
    assert TEMPLATE.exists(), f"Not found: {TEMPLATE}"

    a = ANALYTICS.read_text()
    t = TEMPLATE.read_text()

    # ---- PRE-FLIGHT: analytics.py ----
    assert A_FUNC_ANCHOR in a, f"Function anchor not found: {A_FUNC_ANCHOR!r}"
    assert a.count(A_FUNC_ANCHOR) == 1, (
        f"Function anchor not unique (count={a.count(A_FUNC_ANCHOR)})"
    )
    assert a.count(A_ROUTE_OLD) == 2, (
        f"Expected 2 occurrences of route anchor, found {a.count(A_ROUTE_OLD)}"
    )

    # Idempotency guards
    assert '_build_brief_latent' not in a, (
        "_build_brief_latent already in analytics.py -- already applied? Run "
        "`git status` and `grep -n _build_brief_latent app/routes/analytics.py`."
    )
    assert 'encode_latent_photos(data)' not in a, (
        "encode_latent_photos(data) already wired -- already applied?"
    )

    # ---- PRE-FLIGHT: template ----
    assert T_HEADER_OLD in t, "Status-strip header anchor missing in template"
    assert t.count(T_HEADER_OLD) == 1, (
        f"Status-strip anchor count = {t.count(T_HEADER_OLD)}, expected 1"
    )
    assert T_S03_OLD in t, "Section-03 insertion anchor missing in template"
    assert t.count(T_S03_OLD) == 1, (
        f"Section-03 anchor count = {t.count(T_S03_OLD)}, expected 1"
    )
    for i, (old, _new) in enumerate(RENUMBERS, 1):
        assert old in t, f"RENUMBER {i} anchor missing: {old!r}"
        assert t.count(old) == 1, (
            f"RENUMBER {i} not unique (count={t.count(old)}): {old!r}"
        )

    # Idempotency guards
    assert 'latent_brief_summary' not in t, (
        "latent_brief_summary already in template -- already applied?"
    )
    assert '<!-- SECTION 03: LATENT DEFECTS -->' not in t, (
        "SECTION 03 marker already present -- already applied?"
    )

    # ---- APPLY (in memory) ----
    a_new = a.replace(A_FUNC_ANCHOR, NEW_LATENT_FUNCTION + A_FUNC_ANCHOR)
    a_new = a_new.replace(A_ROUTE_OLD, A_ROUTE_NEW)

    t_new = t.replace(T_HEADER_OLD, T_HEADER_NEW)
    t_new = t_new.replace(T_S03_OLD, T_S03_NEW)
    for old, new in RENUMBERS:
        t_new = t_new.replace(old, new)

    # ---- POST-FLIGHT: analytics.py ----
    assert 'def _build_brief_latent(' in a_new, "Function not inserted"
    assert a_new.count('def _build_brief_latent(') == 1, (
        "Function inserted multiple times -- abort"
    )
    assert a_new.count('_build_brief_latent(_tenant') == 2, (
        f"Expected _build_brief_latent called from 2 routes, "
        f"got {a_new.count('_build_brief_latent(_tenant')}"
    )
    assert a_new.count('encode_latent_photos(data)') == 2, (
        f"Expected encode_latent_photos(data) in 2 routes, "
        f"got {a_new.count('encode_latent_photos(data)')}"
    )

    # ---- POST-FLIGHT: template ----
    assert 'latent_brief_summary' in t_new, "latent_brief_summary missing from template"
    assert '<!-- SECTION 03: LATENT DEFECTS -->' in t_new, (
        "SECTION 03 marker not inserted"
    )
    for i, (old, new) in enumerate(RENUMBERS, 1):
        assert old not in t_new, f"RENUMBER {i} old still present"
        assert new in t_new, f"RENUMBER {i} new not present"

    # Verify the new §03 Latent Defects section landed correctly
    assert (
        '<span class="section-number">03</span>\n'
        '                <span class="section-title">Latent Defects</span>'
    ) in t_new, "New §03 Latent Defects span pair not in expected form"

    # ---- WRITE ----
    ANALYTICS.write_text(a_new)
    TEMPLATE.write_text(t_new)

    # ---- SUMMARY ----
    print("OK: SMB §03 Latent Defects build applied.\n")
    print("Files changed:")
    print(f"  - {ANALYTICS}  ({a.count(chr(10))} -> {a_new.count(chr(10))} lines, +{a_new.count(chr(10)) - a.count(chr(10))})")
    print(f"  - {TEMPLATE}   ({t.count(chr(10))} -> {t_new.count(chr(10))} lines, +{t_new.count(chr(10)) - t.count(chr(10))})")
    print()
    print("Section numbers after renumber:")
    for m in re.finditer(
        r'<span class="section-number">(\d+)</span>\s*\n\s*<span class="section-title">([^<]+)</span>',
        t_new,
    ):
        print(f"  §{m.group(1)}  {m.group(2).strip()}")


if __name__ == "__main__":
    main()
