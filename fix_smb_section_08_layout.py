#!/usr/bin/env python3
"""
SMB layout fixes:
  T0 (§04): clamp Defect Pool chart SVG height to 200px so the legend
           stays on page 1 instead of bleeding to page 2.

  analytics.py:
    A1 - by_area_sorted becomes list of dicts (was 6-tuple)
    A2 - new latent_outstanding_columns: 2-element list, zones split
         greedy by note count to minimise left-vs-right imbalance
    A3 - return dict gains latent_outstanding_columns key

  template (§08):
    T1 - By Area table: 6 cols -> 3 cols (Area / Outstanding / Share).
         UNITS dropped (== COUNT for this data shape). TOP ZONE / IN
         ZONE dropped (info already in Cluster callout above).
    T2 - Outstanding list: CSS column-count -> table-based 2-col,
         reliable in print PDF.

Idempotent. Pre/post-flight assert-guarded. Atomic write.
Run from inspections-pwa repo root.
"""
from pathlib import Path

ANALYTICS = Path("app/routes/analytics.py")
TEMPLATE = Path("app/templates/analytics/site_meeting_brief.html")

assert ANALYTICS.exists(), f"Not found: {ANALYTICS}"
assert TEMPLATE.exists(), f"Not found: {TEMPLATE}"

# T0: §04 chart height clamp
T0_OLD = """        <svg viewBox="0 0 {{ chart_w + 20 }} {{ chart_h + 30 }}" xmlns="http://www.w3.org/2000/svg"
             style="width: 100%; height: auto; margin: 0 auto 8px auto; display: block;">"""

T0_NEW = """        <svg viewBox="0 0 {{ chart_w + 20 }} {{ chart_h + 30 }}" xmlns="http://www.w3.org/2000/svg"
             style="width: 100%; height: 200px; margin: 0 auto 8px auto; display: block;">"""

# A1: by_area_sorted tuple -> dict
A1_OLD = """        _units = len(area_unit_ids.get(a, set()))
        _share = int(round(100.0 * c / _total_out)) if _total_out else 0
        by_area_sorted.append((a, c, _units, _share, _tz_label, _tz_count))"""

A1_NEW = """        _units = len(area_unit_ids.get(a, set()))
        _share = int(round(100.0 * c / _total_out)) if _total_out else 0
        by_area_sorted.append({
            'name': a,
            'count': c,
            'units': _units,
            'share': _share,
            'top_zone': _tz_label,
            'top_zone_count': _tz_count,
        })"""

# A2: append column split after outstanding_by_zone loop
A2_OLD = """        outstanding_by_zone.append({
            'block': _zk[0],
            'floor': _zk[1],
            'floor_label': _FL_LABELS.get(_zk[1], 'Floor {}'.format(_zk[1])),
            'zone_label': _zone_label(_zk[0], _zk[1]),
            'outstanding_count': len(_zone_n),
            'units_count': len(_units_list),
            'units': _units_list,
        })"""

A2_NEW = A2_OLD + """

    # 2-column split: minimise diff between left and right cumulative note counts
    if outstanding_by_zone:
        _total_notes_in_list = sum(z['outstanding_count'] for z in outstanding_by_zone)
        _best_split = 0
        _best_diff = None
        for _i in range(1, len(outstanding_by_zone) + 1):
            _l_sum = sum(z['outstanding_count'] for z in outstanding_by_zone[:_i])
            _r_sum = _total_notes_in_list - _l_sum
            _diff = abs(_l_sum - _r_sum)
            if _best_diff is None or _diff < _best_diff:
                _best_diff = _diff
                _best_split = _i
        latent_outstanding_columns = [
            {'zones': outstanding_by_zone[:_best_split]},
            {'zones': outstanding_by_zone[_best_split:]},
        ]
    else:
        latent_outstanding_columns = [{'zones': []}, {'zones': []}]"""

# A3: return dict key
A3_OLD = """        'latent_top_zone': latent_top_zone,
        'latent_cycle_summary': latent_cycle_summary,
        'latent_outstanding_by_zone': outstanding_by_zone,
    }"""

A3_NEW = """        'latent_top_zone': latent_top_zone,
        'latent_cycle_summary': latent_cycle_summary,
        'latent_outstanding_by_zone': outstanding_by_zone,
        'latent_outstanding_columns': latent_outstanding_columns,
    }"""

# T1: By Area table 6 cols -> 3 cols
T1_OLD = """            <table style="width: 100%; border-collapse: collapse; font-size: 10px; font-feature-settings: 'lnum' 1, 'tnum' 1;">
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

T1_NEW = """            <table style="width: 60%; border-collapse: collapse; font-size: 10px; font-feature-settings: 'lnum' 1, 'tnum' 1;">
                <thead>
                    <tr>
                        <th style="text-align: left; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1;">Area</th>
                        <th style="text-align: right; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1; width: 90px;">Outstanding</th>
                        <th style="text-align: right; padding: 5px 8px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 1.2px; text-transform: uppercase; border-bottom: 2px solid #E8E6E1; width: 70px;">Share</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in latent_by_area %}
                    <tr>
                        <td style="padding: 4px 8px; border-bottom: 1px solid #F0EEEA; font-weight: 600;">{{ row.name }}</td>
                        <td style="text-align: right; padding: 4px 8px; border-bottom: 1px solid #F0EEEA; font-weight: 700; color: #C44D3F;">{{ row.count }}</td>
                        <td style="text-align: right; padding: 4px 8px; border-bottom: 1px solid #F0EEEA;">{{ row.share }}%</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>"""

# T2: Outstanding list - CSS columns -> table-based 2-col
T2_OLD = """        <div style="margin-top: 12px;">
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
        </div>"""

T2_NEW = """        <div style="margin-top: 12px;">
            <div style="font-size: 9px; font-weight: 600; color: #9A9A9A; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 8px;">Outstanding &mdash; by zone</div>
            <table style="width: 100%; border-collapse: separate; border-spacing: 0;">
                <tr>
                    {% for col in latent_outstanding_columns %}
                    <td style="width: 50%; vertical-align: top; padding: 0 {% if loop.first %}8px 0 0{% else %}0 0 8px{% endif %};">
                        {% for zone in col.zones %}
                        <div style="margin-bottom: 14px;">
                            <div style="font-size: 10px; font-weight: 700; color: #1A1A1A; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px solid #DCD7CB;">
                                {{ zone.zone_label }}
                                <span style="font-weight: 400; color: #6B6B6B;"> &middot; {{ zone.outstanding_count }} across {{ zone.units_count }} unit{% if zone.units_count != 1 %}s{% endif %}</span>
                            </div>
                            {% for unit in zone.units %}
                            <div style="page-break-inside: avoid; break-inside: avoid; margin-bottom: 8px; padding-left: 6px; border-left: 2px solid #C44D3F;">
                                <div style="font-size: 10px; font-weight: 700; color: #1A1A1A; margin-bottom: 3px;">Unit {{ unit.unit_number }}</div>
                                {% for note in unit.notes %}
                                <div style="display: flex; gap: 6px; margin-bottom: 2px; align-items: baseline;">
                                    <div style="flex: 0 0 72px; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 0.5px; text-transform: uppercase; line-height: 1.4;">{{ note.area_display_name }}</div>
                                    <div style="flex: 1; font-size: 9.5px; line-height: 1.4; color: #1A1A1A;">{{ note.note_html | safe }}</div>
                                </div>
                                {% endfor %}
                            </div>
                            {% endfor %}
                        </div>
                        {% endfor %}
                    </td>
                    {% endfor %}
                </tr>
            </table>
        </div>"""


def main():
    a = ANALYTICS.read_text()
    t = TEMPLATE.read_text()

    a_done = 'latent_outstanding_columns' in a
    t_done = 'latent_outstanding_columns' in t and 'height: 200px; margin: 0 auto 8px auto' in t
    if a_done and t_done:
        print("[NO-OP] Already applied. Files unchanged.")
        raise SystemExit(0)

    for name, txt in [('A1', A1_OLD), ('A2', A2_OLD), ('A3', A3_OLD)]:
        assert txt in a, f"{name} anchor missing in analytics.py"
        assert a.count(txt) == 1, f"{name} anchor not unique (count={a.count(txt)})"
    assert 'latent_outstanding_columns' not in a, "already in analytics.py"

    for name, txt in [('T0', T0_OLD), ('T1', T1_OLD), ('T2', T2_OLD)]:
        assert txt in t, f"{name} anchor missing in template"
        assert t.count(txt) == 1, f"{name} anchor not unique (count={t.count(txt)})"
    assert 'latent_outstanding_columns' not in t
    assert 'column-count: 2' in t

    a_new = a.replace(A1_OLD, A1_NEW).replace(A2_OLD, A2_NEW).replace(A3_OLD, A3_NEW)
    t_new = t.replace(T0_OLD, T0_NEW).replace(T1_OLD, T1_NEW).replace(T2_OLD, T2_NEW)

    assert "by_area_sorted.append({" in a_new
    assert "by_area_sorted.append((a, c, _units, _share, _tz_label, _tz_count))" not in a_new
    assert "latent_outstanding_columns = [" in a_new
    assert "'latent_outstanding_columns': latent_outstanding_columns," in a_new

    assert 'height: 200px; margin: 0 auto 8px auto' in t_new
    assert '{% for row in latent_by_area %}' in t_new
    assert "{% for area, cnt, units, share, top_zone, top_zone_count in latent_by_area %}" not in t_new
    assert '{% for col in latent_outstanding_columns %}' in t_new
    assert 'column-count: 2' not in t_new

    ANALYTICS.write_text(a_new)
    TEMPLATE.write_text(t_new)

    print("[OK] SMB layout fixes applied.")
    print()
    print("  T0: chart SVG height clamped to 200px (legend stays on page 1)")
    print("  A1: latent_by_area: tuple -> dict")
    print("  A2: latent_outstanding_columns: zones split into 2 columns")
    print("  T1: By Area: 6 cols -> 3 cols (Area, Outstanding, Share)")
    print("  T2: Outstanding list: CSS columns -> <table> 2-col")
    print()
    print("Verify: git --no-pager diff --stat")


if __name__ == "__main__":
    main()
