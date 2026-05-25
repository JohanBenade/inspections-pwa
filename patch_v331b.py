"""
patch_v331b.py - insert new section "06 Units Certified by Zone" into SMB
                  and renumber existing sections 06->07, 07->08, 08->09

Four edits in one logical change (template-only):
  1. INSERT new section markup between end-of-section-05 and start-of-Trade
  2. RENUMBER existing 06 Defects by Trade   -> 07
  3. RENUMBER existing 07 Worst Units        -> 08
  4. RENUMBER existing 08 Latent Defects     -> 09

Template path is discovered via glob to avoid hardcoding.

Run:  python3 patch_v331b.py
"""

import glob

candidates = glob.glob('app/templates/**/site_meeting_brief.html', recursive=True)
assert len(candidates) == 1, "Expected exactly one template, got: {}".format(candidates)
PATH = candidates[0]

with open(PATH, 'r') as f:
    content = f.read()

# --- EDIT 1: insert new section 06 (Units Certified by Zone) ---
# Anchor on the transition from end of section 05 (Defects by Zone) into
# the start of the existing Trade section. New markup gets inserted between.

OLD_1 = """        {% endif %}
    </div>

    {% if by_trade %}"""

NEW_SECTION = """        {% endif %}
    </div>

    {% if cert_zone_grid and cert_zone_grid.blocks %}
    <div class="section section-tight" style="margin-bottom: 18px; page-break-before: always; break-before: page;">
        <div class="section-header">
            <span class="section-number">06</span>
            <span class="section-title">Units Certified by Zone</span>
        </div>

        <div style="display: grid; grid-template-columns: 60px repeat({{ cert_zone_grid.floors|length }}, 1fr); gap: 4px;">
            <div></div>
            {% for fl in cert_zone_grid.floors %}
            <div style="text-align: center; font-size: 8px; font-weight: 600; color: #9A9A9A; letter-spacing: 0.8px; text-transform: uppercase; padding-bottom: 3px;">{{ floor_labels.get(fl, fl) }}</div>
            {% endfor %}

            {% for block in cert_zone_grid.blocks %}
            <div style="display: flex; align-items: center; font-size: 9px; font-weight: 600; color: #1A1A1A;">{{ block }}</div>
            {% for fl in cert_zone_grid.floors %}
            {% set cz = cert_zone_grid.data.get((block, fl), None) %}
            {% if cz is none %}
            <div style="background: #F5F3EE; border: 1px solid #DCD7CB; border-radius: 5px; padding: 7px 5px; text-align: center; min-height: 80px; display: flex; align-items: center; justify-content: center;">
                <span style="font-size: 8px; color: #BFBDB8;">&mdash;</span>
            </div>
            {% elif cz.cert_stage == 'none' %}
            <div style="background: #ECEAE5; border: 1px solid #DCD7CB; border-radius: 5px; padding: 7px 5px; text-align: center; min-height: 80px; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                <div style="font-size: 9px; font-weight: 600; color: #9A9A9A;">{{ cz.total_units }} units</div>
                <div style="margin-top: 4px; font-size: 8px; color: #9A9A9A;">awaiting</div>
            </div>
            {% elif cz.cert_stage == 'partial' %}
            <div style="background: #FAEEDA; border: 1px solid #DCD7CB; border-radius: 5px; padding: 7px 5px; text-align: center; min-height: 80px;">
                <div style="font-size: 9px; font-weight: 600; color: #9A9A9A;">{{ cz.total_units }} units</div>
                <div style="margin-top: 4px; font-size: 14px; font-weight: 600; color: #1A1A1A;">{{ cz.certified_count }} / {{ cz.total_units }}</div>
                <div style="margin-top: 4px; height: 4px; background: #DCD7CB; border-radius: 2px; overflow: hidden;">
                    <div style="width: {{ cz.certified_pct }}%; height: 100%; background: #5F8838;"></div>
                </div>
                <div style="margin-top: 5px; font-size: 8px; color: #1A1A1A; line-height: 1.3;">{{ cz.certified_units_display }}</div>
            </div>
            {% elif cz.cert_stage == 'all' %}
            <div style="background: #E9EED7; border: 1px solid #DCD7CB; border-radius: 5px; padding: 7px 5px; text-align: center; min-height: 80px;">
                <div style="font-size: 9px; font-weight: 600; color: #9A9A9A;">{{ cz.total_units }} units</div>
                <div style="margin-top: 4px; font-size: 14px; font-weight: 600; color: #5F8838;">{{ cz.certified_count }} / {{ cz.total_units }}</div>
                <div style="margin-top: 4px; height: 4px; background: #DCD7CB; border-radius: 2px; overflow: hidden;">
                    <div style="width: 100%; height: 100%; background: #5F8838;"></div>
                </div>
                <div style="margin-top: 5px; font-size: 8px; color: #5F8838; line-height: 1.3; font-weight: 600;">{{ cz.certified_units_display }}</div>
            </div>
            {% endif %}
            {% endfor %}
            {% endfor %}
        </div>

        <!-- Legend -->
        <div style="margin-top: 5px; display: flex; flex-wrap: wrap; gap: 12px; font-size: 9px; color: #6B6B6B;">
            <span><span style="display: inline-block; width: 10px; height: 10px; border-radius: 2px; background: #ECEAE5; border: 1px solid #DCD7CB; margin-right: 4px; vertical-align: middle;"></span>Awaiting certification</span>
            <span><span style="display: inline-block; width: 10px; height: 10px; border-radius: 2px; background: #FAEEDA; border: 1px solid #DCD7CB; margin-right: 4px; vertical-align: middle;"></span>Partial (in progress)</span>
            <span><span style="display: inline-block; width: 10px; height: 10px; border-radius: 2px; background: #E9EED7; border: 1px solid #DCD7CB; margin-right: 4px; vertical-align: middle;"></span>All certified</span>
        </div>
    </div>
    {% endif %}

    {% if by_trade %}"""

assert OLD_1 in content, "EDIT 1 anchor not found (end-of-section-05 transition)"
assert content.count(OLD_1) == 1, "EDIT 1 anchor not unique"
content = content.replace(OLD_1, NEW_SECTION)

# --- EDIT 2: renumber existing 06 Defects by Trade -> 07 ---
OLD_2 = """            <span class="section-number">06</span>
            <span class="section-title">Defects by Trade</span>"""
NEW_2 = """            <span class="section-number">07</span>
            <span class="section-title">Defects by Trade</span>"""

assert OLD_2 in content, "EDIT 2 anchor not found (Defects by Trade header)"
assert content.count(OLD_2) == 1, "EDIT 2 anchor not unique"
content = content.replace(OLD_2, NEW_2)

# --- EDIT 3: renumber existing 07 Worst Units -> 08 ---
OLD_3 = """                <span class="section-number">07</span>
                <span class="section-title">Worst Units</span>"""
NEW_3 = """                <span class="section-number">08</span>
                <span class="section-title">Worst Units</span>"""

assert OLD_3 in content, "EDIT 3 anchor not found (Worst Units header)"
assert content.count(OLD_3) == 1, "EDIT 3 anchor not unique"
content = content.replace(OLD_3, NEW_3)

# --- EDIT 4: renumber existing 08 Latent Defects -> 09 ---
OLD_4 = """                <span class="section-number">08</span>
                <span class="section-title">Latent Defects</span>"""
NEW_4 = """                <span class="section-number">09</span>
                <span class="section-title">Latent Defects</span>"""

assert OLD_4 in content, "EDIT 4 anchor not found (Latent Defects header)"
assert content.count(OLD_4) == 1, "EDIT 4 anchor not unique"
content = content.replace(OLD_4, NEW_4)

with open(PATH, 'w') as f:
    f.write(content)

print("v331b applied to {}:".format(PATH))
print("  - new section 06 'Units Certified by Zone' inserted")
print("  - Defects by Trade   renumbered 06 -> 07")
print("  - Worst Units        renumbered 07 -> 08")
print("  - Latent Defects     renumbered 08 -> 09")
print("")
print("Verify:")
print("  grep -n 'section-number' {} | head -10".format(PATH))
print("  grep -n 'Units Certified by Zone' {}".format(PATH))
