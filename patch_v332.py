"""
patch_v332.py - reorder SMB sections: move "Units Certified by Zone"
                from current position 06 (after Defects by Zone) up to 04
                (before Defect Pool). Story arc now: status -> certified
                spatial story -> defect detail.

Four edits in one logical change (template-only):
  1. CUT current cert_zone_grid block from between sec-05 and Trade section
  2. PASTE it before sec-04 Defect Pool, renumbered as 04
  3. RENUMBER Defect Pool     04 -> 05
  4. RENUMBER Defects by Zone 05 -> 06

Sections 07/08/09 (Trade / Worst Units / Latent) unchanged.

Run:  python3 patch_v332.py
"""

import glob

candidates = glob.glob('app/templates/**/site_meeting_brief.html', recursive=True)
assert len(candidates) == 1, "Expected exactly one template, got: {}".format(candidates)
PATH = candidates[0]

with open(PATH, 'r') as f:
    content = f.read()

# --- The cert_zone_grid block exactly as v331b inserted it (section-number 06) ---
CUT_BLOCK = """    {% if cert_zone_grid and cert_zone_grid.blocks %}
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

"""

# Block to paste in new location - same content but section-number 04
INSERT_BLOCK = CUT_BLOCK.replace(
    '<span class="section-number">06</span>',
    '<span class="section-number">04</span>',
)

# --- EDIT 1: cut the current cert_zone_grid block ---
assert CUT_BLOCK in content, "EDIT 1 anchor not found (cert_zone_grid block as inserted by v331b)"
assert content.count(CUT_BLOCK) == 1, "EDIT 1 anchor not unique"
content = content.replace(CUT_BLOCK, "")

# --- EDIT 2: paste the renumbered block before the Defect Pool comment ---
OLD_2 = "    <!-- SECTION 04: DEFECT POOL (Page 2, enlarged) - v322 -->"
NEW_2 = INSERT_BLOCK + OLD_2

assert OLD_2 in content, "EDIT 2 anchor not found (Defect Pool comment)"
assert content.count(OLD_2) == 1, "EDIT 2 anchor not unique"
content = content.replace(OLD_2, NEW_2)

# --- EDIT 3: renumber Defect Pool 04 -> 05 ---
OLD_3 = """            <span class="section-number">04</span>
            <span class="section-title">Defect Pool</span>"""
NEW_3 = """            <span class="section-number">05</span>
            <span class="section-title">Defect Pool</span>"""

assert OLD_3 in content, "EDIT 3 anchor not found (Defect Pool header)"
assert content.count(OLD_3) == 1, "EDIT 3 anchor not unique"
content = content.replace(OLD_3, NEW_3)

# --- EDIT 4: renumber Defects by Zone 05 -> 06 ---
OLD_4 = """            <span class="section-number">05</span>
            <span class="section-title">Defects by Zone</span>"""
NEW_4 = """            <span class="section-number">06</span>
            <span class="section-title">Defects by Zone</span>"""

assert OLD_4 in content, "EDIT 4 anchor not found (Defects by Zone header)"
assert content.count(OLD_4) == 1, "EDIT 4 anchor not unique"
content = content.replace(OLD_4, NEW_4)

with open(PATH, 'w') as f:
    f.write(content)

print("v332 applied to {}:".format(PATH))
print("  - Units Certified by Zone cut from old position (was section 06)")
print("  - Pasted before Defect Pool as section 04")
print("  - Defect Pool      renumbered 04 -> 05")
print("  - Defects by Zone  renumbered 05 -> 06")
print("")
print("Final section order: 01 02 03 04(Certified) 05(Pool) 06(Zone) 07 08 09")
print("")
print("Verify:")
print("  grep -n 'section-number' {} | head -12".format(PATH))
print("  grep -n 'Units Certified by Zone' {}".format(PATH))
