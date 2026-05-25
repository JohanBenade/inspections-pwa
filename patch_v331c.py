"""
patch_v331c.py - trim SMB pages 6-7: remove the per-unit "OUTSTANDING - by zone"
                  detail list inside section 09 (Latent Defects).

Keeps everything strategic on page 5:
  - 3 rate cards (Outstanding / Affected Units / Oldest Open)
  - Concentration callout
  - Distribution by Zone grid (block x floor)
  - By Area table
  - Cycle-age footer note
  - Rectified This Fortnight block (auto-shown when count > 0)

Removes only the two-column per-unit-listing block that produced pp.6-7.

Run:  python3 patch_v331c.py
"""

import glob

candidates = glob.glob('app/templates/**/site_meeting_brief.html', recursive=True)
assert len(candidates) == 1, "Expected exactly one template, got: {}".format(candidates)
PATH = candidates[0]

with open(PATH, 'r') as f:
    content = f.read()

# --- DELETE the per-unit Outstanding-by-zone list ---
# Anchor: starts with the page-break div header for "Outstanding - by zone"
# and ends after the closing </table></div> block (just before the
# "Rectified This Fortnight" section).
#
# Boundaries verified against template L917-946:
#   start: <div style="margin-top: 12px; page-break-before: always; ...
#   end:   </table>\n        </div>  (the latent_outstanding_columns block)

OLD = """        <div style="margin-top: 12px; page-break-before: always; padding-top: 8px;">
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
        </div>
"""

assert OLD in content, "DELETE anchor not found (per-unit latent list)"
assert content.count(OLD) == 1, "DELETE anchor not unique"

# Replace with empty string (deletion)
content = content.replace(OLD, "")

with open(PATH, 'w') as f:
    f.write(content)

print("v331c applied to {}:".format(PATH))
print("  - per-unit 'Outstanding - by zone' detail list removed")
print("  - Page 5 strategic roll-ups retained (3 rate cards, concentration,")
print("    zone-grid, area-table, cycle-age footer)")
print("  - Rectified This Fortnight block retained (auto-shows when relevant)")
print("")
print("Expected report length after deploy: 7 pages -> 5 pages")
print("")
print("Verify:")
print("  grep -c 'latent_outstanding_columns' {}".format(PATH))
print("  # expected: 0")
