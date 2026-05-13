#!/usr/bin/env python3
"""
SMB §08 UX upgrade — single atomic commit.

analytics.py changes (_build_brief_latent):
  - Track area-zone counts during the loop.
  - Compute top zone per area for enriched By Area table.
  - Compute overall top zone (cluster callout).
  - Compute cycle/age summary for section-level statement.
  - Build outstanding-by-zone-and-unit nested structure for new list display.
  - latent_by_area shape: (area, count, units, share_pct, top_zone_label, top_zone_count)
  - New return keys: latent_top_zone, latent_cycle_summary, latent_outstanding_by_zone.

site_meeting_brief.html changes:
  - Subtitle qualifier polish: append " from analytics".
  - Cluster callout box inserted between KPI band and Distribution by Zone grid.
  - By Area table widened to 6 columns: Area, Count, Units, Share, Top zone, In zone.
  - Outstanding list block replaced with new 2-column zone-grouped per-unit structure.
  - Section-level cycle summary line (replaces per-card 0-days / Cx repetition).
  - Old per-note "Outstanding — oldest first" cards removed.

Idempotent. Pre-flight asserts every anchor. Post-flight asserts every replacement.
File written only if all asserts pass.

Run from inspections-pwa repo root.
"""
from pathlib import Path

ANALYTICS = Path("app/routes/analytics.py")
TEMPLATE = Path("app/templates/analytics/site_meeting_brief.html")

assert ANALYTICS.exists(), f"Not found: {ANALYTICS}"
assert TEMPLATE.exists(), f"Not found: {TEMPLATE}"

# ============================================================================
# ANALYTICS.PY — three anchors
# ============================================================================

A1_OLD = """    outstanding_unit_ids = set()
    zone_outstanding = {}
    area_outstanding = {}
    area_unit_ids = {}
    blocks_seen = set()
    floors_seen = set()"""

A1_NEW = """    outstanding_unit_ids = set()
    zone_outstanding = {}
    area_outstanding = {}
    area_unit_ids = {}
    area_zone_counts = {}
    blocks_seen = set()
    floors_seen = set()"""

A2_OLD = """            area_outstanding[area_display] = (
                area_outstanding.get(area_display, 0) + 1
            )
            area_unit_ids.setdefault(area_display, set()).add(n['unit_id'])"""

A2_NEW = """            area_outstanding[area_display] = (
                area_outstanding.get(area_display, 0) + 1
            )
            area_unit_ids.setdefault(area_display, set()).add(n['unit_id'])
            _azk = (n['block'], n['floor'])
            _azc = area_zone_counts.setdefault(area_display, {})
            _azc[_azk] = _azc.get(_azk, 0) + 1"""

# Replace the aggregate block (by_area_sorted + adjacents) with the full
# enriched aggregate logic.
A3_OLD = """    _total_out = len(outstanding)
    by_area_sorted = sorted(
        [
            (a, c, len(area_unit_ids.get(a, set())),
             int(round(100.0 * c / _total_out)) if _total_out else 0)
            for a, c in area_outstanding.items()
        ],
        key=lambda x: -x[1],
    )"""

A3_NEW = """    _FL_LABELS = {0: 'Ground Floor', 1: '1st Floor', 2: '2nd Floor', 3: '3rd Floor'}

    def _zone_label(blk, fl):
        return '{} / {}'.format(blk, _FL_LABELS.get(fl, 'Floor {}'.format(fl)))

    _total_out = len(outstanding)

    # Enriched by-area: (area, count, units, share_pct, top_zone_label, top_zone_count)
    by_area_sorted = []
    for a, c in sorted(area_outstanding.items(), key=lambda x: -x[1]):
        zc = area_zone_counts.get(a, {})
        if zc:
            _tz, _tc = max(zc.items(), key=lambda kv: kv[1])
            _tz_label = _zone_label(_tz[0], _tz[1])
            _tz_count = _tc
        else:
            _tz_label = ''
            _tz_count = 0
        _units = len(area_unit_ids.get(a, set()))
        _share = int(round(100.0 * c / _total_out)) if _total_out else 0
        by_area_sorted.append((a, c, _units, _share, _tz_label, _tz_count))

    # Overall top zone (cluster callout)
    if zone_outstanding and _total_out:
        _top_z, _top_c = max(zone_outstanding.items(), key=lambda kv: kv[1])
        latent_top_zone = {
            'block': _top_z[0],
            'floor': _top_z[1],
            'floor_label': _FL_LABELS.get(_top_z[1], 'Floor {}'.format(_top_z[1])),
            'count': _top_c,
            'pct': int(round(100.0 * _top_c / _total_out)),
            'label': _zone_label(_top_z[0], _top_z[1]),
        }
    else:
        latent_top_zone = None

    # Cycle / age summary (drives section-level statement)
    _cycles = set(n.get('cycle_number') for n in outstanding if n.get('cycle_number') is not None)
    latent_cycle_summary = {
        'all_same_cycle': len(_cycles) == 1,
        'one_cycle': next(iter(_cycles)) if len(_cycles) == 1 else None,
        'all_zero_days': oldest_days == 0,
        'oldest_days': oldest_days,
    } if outstanding else None

    # Outstanding grouped by zone -> units -> notes (for 2-column list)
    _zone_notes = {}
    for n in outstanding:
        _zone_notes.setdefault((n['block'], n['floor']), []).append(n)
    outstanding_by_zone = []
    for _zk in sorted(_zone_notes.keys(), key=lambda x: (x[0], x[1])):
        _zone_n = _zone_notes[_zk]
        _unit_n = {}
        for _n in _zone_n:
            _unit_n.setdefault(_n['unit_number'], []).append(_n)
        _units_list = []
        for _un in sorted(_unit_n.keys()):
            _unotes = _unit_n[_un]
            _unotes.sort(key=lambda x: (x.get('area_order') or 999, x.get('area_display_name') or ''))
            _units_list.append({
                'unit_number': _un,
                'notes': [{
                    'area_display_name': _x.get('area_display_name'),
                    'note_html': _x.get('note_html'),
                } for _x in _unotes],
            })
        outstanding_by_zone.append({
            'block': _zk[0],
            'floor': _zk[1],
            'floor_label': _FL_LABELS.get(_zk[1], 'Floor {}'.format(_zk[1])),
            'zone_label': _zone_label(_zk[0], _zk[1]),
            'outstanding_count': len(_zone_n),
            'units_count': len(_units_list),
            'units': _units_list,
        })"""

# Need oldest_days BEFORE the aggregate block. Verify current order: currently
# `oldest_days = max(...)` appears IMMEDIATELY before `_total_out = ...`.
# Our A3 uses oldest_days, so it must remain in scope.

A4_OLD = """        'latent_by_area': by_area_sorted,
    }"""

A4_NEW = """        'latent_by_area': by_area_sorted,
        'latent_top_zone': latent_top_zone,
        'latent_cycle_summary': latent_cycle_summary,
        'latent_outstanding_by_zone': outstanding_by_zone,
    }"""


# ============================================================================
# TEMPLATE — five anchors
# ============================================================================

# T1: subtitle qualifier polish
T1_OLD = ('<div class="report-subtitle" style="font-size: 10px; color: #9A9A9A; '
          'margin-top: 1px; font-style: italic; letter-spacing: 0.3px;">'
          'Scope: dwelling units only &mdash; other and external areas are excluded.</div>')

T1_NEW = ('<div class="report-subtitle" style="font-size: 10px; color: #9A9A9A; '
          'margin-top: 1px; font-style: italic; letter-spacing: 0.3px;">'
          'Scope: dwelling units only &mdash; other and external areas are excluded from analytics.</div>')

# T2: cluster callout — insert BEFORE the Distribution by Zone grid in §08
T2_OLD = "        {% if latent_zone_grid and latent_zone_grid.blocks %}"

T2_NEW = """        {% if latent_top_zone %}
        <div style="margin-top: 14px; padding: 8px 12px; background: #F8F4ED; border-left: 3px solid #C8963E; font-size: 10px; color: #1A1A1A;">
            <span style="font-weight: 700; color: #C8963E; text-transform: uppercase; letter-spacing: 0.8px; font-size: 9px;">Concentration:</span>
            <span style="font-weight: 600;">{{ latent_top_zone.label }}</span>
            <span style="color: #6B6B6B;">({{ latent_top_zone.count }} of {{ latent_brief_summary.outstanding_count }}, {{ latent_top_zone.pct }}%)</span>
            <span style="color: #6B6B6B;"> &mdash; recommend focused remediation visit.</span>
        </div>
        {% endif %}

        {% if latent_zone_grid and latent_zone_grid.blocks %}"""

# T3: By Area table — 4-col -> 6-col (Area, Count, Units, Share, Top zone, In zone)
T3_OLD = """            <table style="width: 100%; border-collapse: collapse; font-size: 10px; font-feature-settings: 'lnum' 1, 'tnum' 1; table-layout: fixed;">
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

T3_NEW = """            <table style="width: 100%; border-collapse: collapse; font-size: 10px; font-feature-settings: 'lnum' 1, 'tnum' 1;">
                <thead>
                    <tr>
                        <th style="text-align: left; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1;">Area</th>
                        <th style="text-align: right; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1; width: 55px;">Count</th>
                        <th style="text-align: right; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1; width: 55px;">Units</th>
                        <th style="text-align: right; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1; width: 55px;">Share</th>
                        <th style="text-align: left; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1;">Top zone</th>
                        <th style="text-align: right; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1; width: 60px;">In zone</th>
                    </tr>
                </thead>
                <tbody>
                    {% for area, cnt, units, share, top_zone, top_zone_count in latent_by_area %}
                    <tr>
                        <td style="padding: 4px 8px; border-bottom: 1px solid #F0EEEA; font-weight: 600;">{{ area }}</td>
                        <td style="text-align: right; padding: 4px 8px; border-bottom: 1px solid #F0EEEA; font-weight: 700; color: #C44D3F;">{{ cnt }}</td>
                        <td style="text-align: right; padding: 4px 8px; border-bottom: 1px solid #F0EEEA;">{{ units }}</td>
                        <td style="text-align: right; padding: 4px 8px; border-bottom: 1px solid #F0EEEA;">{{ share }}%</td>
                        <td style="padding: 4px 8px; border-bottom: 1px solid #F0EEEA; color: #6B6B6B;">{{ top_zone }}</td>
                        <td style="text-align: right; padding: 4px 8px; border-bottom: 1px solid #F0EEEA; color: #6B6B6B;">{{ top_zone_count }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>"""

# T4: Outstanding list block — replace flat oldest-first with cycle summary + 2-col zone-grouped
T4_OLD = """        {% if latent_brief_summary.outstanding_count > 0 %}
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
                <div style="font-size: 10px; line-height: 1.4; color: #1A1A1A; margin-bottom: 0;">{{ note.note_html | safe }}</div>
            </div>
            {% endif %}
            {% endfor %}
        </div>
        {% endif %}"""

T4_NEW = """        {% if latent_brief_summary.outstanding_count > 0 %}
        {% if latent_cycle_summary %}
        <div style="margin-top: 14px; font-size: 10px; color: #6B6B6B; font-style: italic;">
            All {{ latent_brief_summary.outstanding_count }} {% if latent_cycle_summary.all_zero_days %}identified this fortnight{% else %}up to {{ latent_cycle_summary.oldest_days }} days old{% endif %}{% if latent_cycle_summary.all_same_cycle %} &middot; current de-snag cycle (C{{ latent_cycle_summary.one_cycle }}){% endif %}.
        </div>
        {% endif %}
        <div style="margin-top: 12px;">
            <div style="font-size: 9px; font-weight: 600; color: #9A9A9A; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px;">Outstanding &mdash; by zone</div>
            <div style="column-count: 2; column-gap: 16px; column-rule: 1px solid #E8E6E1;">
                {% for zone in latent_outstanding_by_zone %}
                <div style="break-inside: avoid; page-break-inside: avoid; margin-bottom: 14px;">
                    <div style="font-size: 10px; font-weight: 700; color: #1A1A1A; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #DCD7CB;">
                        {{ zone.zone_label }}
                        <span style="font-weight: 400; color: #6B6B6B;"> &middot; {{ zone.outstanding_count }} across {{ zone.units_count }} unit{% if zone.units_count != 1 %}s{% endif %}</span>
                    </div>
                    {% for unit in zone.units %}
                    <div style="break-inside: avoid; page-break-inside: avoid; margin-bottom: 8px; padding-left: 6px; border-left: 2px solid #C44D3F;">
                        <div style="font-size: 10px; font-weight: 700; color: #1A1A1A; margin-bottom: 3px;">Unit {{ unit.unit_number }}</div>
                        {% for note in unit.notes %}
                        <div style="display: flex; gap: 6px; margin-bottom: 2px; align-items: baseline;">
                            <div style="flex: 0 0 76px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 0.5px; text-transform: uppercase; line-height: 1.4;">{{ note.area_display_name }}</div>
                            <div style="flex: 1; font-size: 9.5px; line-height: 1.4; color: #1A1A1A;">{{ note.note_html | safe }}</div>
                        </div>
                        {% endfor %}
                    </div>
                    {% endfor %}
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}"""


# ============================================================================
# MAIN
# ============================================================================

def main():
    a = ANALYTICS.read_text()
    t = TEMPLATE.read_text()

    # ---- IDEMPOTENCY ----
    if 'latent_outstanding_by_zone' in a and 'latent_outstanding_by_zone' in t:
        print("[NO-OP] §08 UX upgrade already applied. Files unchanged.")
        raise SystemExit(0)

    # ---- PRE-FLIGHT: analytics.py ----
    for name, txt in [('A1', A1_OLD), ('A2', A2_OLD), ('A3', A3_OLD), ('A4', A4_OLD)]:
        assert txt in a, f"{name} anchor missing in analytics.py"
        assert a.count(txt) == 1, f"{name} anchor not unique (count={a.count(txt)})"

    assert 'area_zone_counts' not in a, "area_zone_counts already in analytics.py"
    assert 'latent_outstanding_by_zone' not in a, "latent_outstanding_by_zone already present"

    # ---- PRE-FLIGHT: template ----
    for name, txt in [('T1', T1_OLD), ('T2', T2_OLD), ('T3', T3_OLD), ('T4', T4_OLD)]:
        assert txt in t, f"{name} anchor missing in template"
        assert t.count(txt) == 1, f"{name} anchor not unique (count={t.count(txt)})"

    assert 'latent_outstanding_by_zone' not in t, "latent_outstanding_by_zone already in template"
    assert 'latent_top_zone' not in t, "latent_top_zone already in template"

    # ---- APPLY (in memory) ----
    a_new = a
    a_new = a_new.replace(A1_OLD, A1_NEW)
    a_new = a_new.replace(A2_OLD, A2_NEW)
    a_new = a_new.replace(A3_OLD, A3_NEW)
    a_new = a_new.replace(A4_OLD, A4_NEW)

    t_new = t
    t_new = t_new.replace(T1_OLD, T1_NEW)
    t_new = t_new.replace(T2_OLD, T2_NEW)
    t_new = t_new.replace(T3_OLD, T3_NEW)
    t_new = t_new.replace(T4_OLD, T4_NEW)

    # ---- POST-FLIGHT: analytics.py ----
    assert 'area_zone_counts' in a_new, "area_zone_counts missing post-apply"
    assert 'area_zone_counts.setdefault(area_display, {})' in a_new, "area_zone_counts increment missing"
    assert 'latent_top_zone' in a_new, "latent_top_zone missing in return"
    assert 'latent_cycle_summary' in a_new, "latent_cycle_summary missing in return"
    assert 'latent_outstanding_by_zone' in a_new, "latent_outstanding_by_zone missing in return"
    assert "by_area_sorted.append((a, c, _units, _share, _tz_label, _tz_count))" in a_new, \
        "Enriched by_area_sorted append missing"

    # ---- POST-FLIGHT: template ----
    assert 'excluded from analytics' in t_new, "Subtitle qualifier polish not applied"
    assert '{% if latent_top_zone %}' in t_new, "Cluster callout conditional missing"
    assert 'Concentration:' in t_new, "Concentration text missing"
    assert '{% for area, cnt, units, share, top_zone, top_zone_count in latent_by_area %}' in t_new, \
        "Enriched by-area for-loop missing"
    assert '{% for area, cnt, affected, share in latent_by_area %}' not in t_new, \
        "Old 4-tuple by-area for-loop still present"
    assert 'latent_outstanding_by_zone' in t_new, "Outstanding by-zone iteration missing"
    assert '{% for zone in latent_outstanding_by_zone %}' in t_new, \
        "outstanding_by_zone for-loop missing"
    # The rectified-this-fortnight section ALSO iterates latent_notes_list,
    # so we expect the count of this for-loop to drop from 2 to 1, not 0.
    _flat_loop_count = t_new.count('{% for note in latent_notes_list %}')
    assert _flat_loop_count == 1, (
        f"Expected exactly 1 remaining `for note in latent_notes_list` loop "
        f"(rectified section). Got {_flat_loop_count}."
    )

    # ---- WRITE ----
    ANALYTICS.write_text(a_new)
    TEMPLATE.write_text(t_new)

    print("[OK] SMB §08 UX upgrade applied.")
    print()
    print("analytics.py: enriched _build_brief_latent")
    print("  - area_zone_counts tracking")
    print("  - latent_top_zone (cluster)")
    print("  - latent_cycle_summary")
    print("  - latent_outstanding_by_zone (nested zone -> units -> notes)")
    print("  - latent_by_area now 6-tuple")
    print()
    print("template (§08):")
    print("  - subtitle qualifier polished")
    print("  - cluster callout box (above zone grid)")
    print("  - By Area: 6 columns including Top zone + In zone")
    print("  - section-level cycle summary line")
    print("  - outstanding list: 2-column zone-grouped per-unit blocks")
    print()
    print("Verify: git --no-pager diff --stat")


if __name__ == "__main__":
    main()
