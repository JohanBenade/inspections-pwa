"""
v322 Patch D - app/templates/analytics/site_meeting_brief.html
Section 02 (De-snag Results) vocabulary updates.

Per v313 spec: drop CLEAR concept entirely from unit context, replace with CERTIFIED.
The defect-flow word "cleared" in Fortnight Movement ledger STAYS - that's defect lifecycle,
not unit state. Only edit unit-facing text.

Four targeted replaces:
  1. Label: "Unit Clearance" -> "Unit Certification"
  2. Bar text: "{{ fully_cleared }} clear" -> "{{ fully_cleared }} certified"
  3. Bar total: "{{ u_open }} open" -> "{{ u_open }} in de-snag", "All clear" -> "All certified"
  4. Insert cohort subtitle below Section 02 header
"""
import io

path = 'app/templates/analytics/site_meeting_brief.html'
with io.open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# --- Change 1: rate-card label ---
old1 = '<div class="label">Unit Clearance</div>'
new1 = '<div class="label">Unit Certification</div>'
assert old1 in content, "PATCH D.1 MATCH FAILED: Unit Clearance label"
assert content.count(old1) == 1, "PATCH D.1 NOT UNIQUE"
content = content.replace(old1, new1)

# --- Change 2: bar-green text in unit bar (NOT defect bar) ---
old2 = '<div class="bar-green" style="width: {{ u_green_pct }}%;">{{ desnag.fully_cleared }} clear</div>'
new2 = '<div class="bar-green" style="width: {{ u_green_pct }}%;">{{ desnag.fully_cleared }} certified</div>'
assert old2 in content, "PATCH D.2 MATCH FAILED: bar-green clear text"
assert content.count(old2) == 1, "PATCH D.2 NOT UNIQUE"
content = content.replace(old2, new2)

# --- Change 3: bar-total in unit bar ("open" -> "in de-snag", "All clear" -> "All certified") ---
old3 = '<span class="bar-total" style="color: {% if u_open > 0 %}#C44D3F{% else %}#4A7C59{% endif %};">{% if u_open > 0 %}{{ u_open }} open{% else %}All clear{% endif %}</span>'
new3 = '<span class="bar-total" style="color: {% if u_open > 0 %}#C44D3F{% else %}#4A7C59{% endif %};">{% if u_open > 0 %}{{ u_open }} in de-snag{% else %}All certified{% endif %}</span>'
assert old3 in content, "PATCH D.3 MATCH FAILED: unit bar-total text"
assert content.count(old3) == 1, "PATCH D.3 NOT UNIQUE"
content = content.replace(old3, new3)

# --- Change 4: Insert cohort subtitle below Section 02 header ---
old4 = """        <div class="section-header">
            <span class="section-number">02</span>
            <span class="section-title">De-snag Results</span>
        </div>

        <div class="rate-cards">"""

new4 = """        <div class="section-header">
            <span class="section-number">02</span>
            <span class="section-title">De-snag Results</span>
        </div>

        <!-- v322: cohort subtitle -->
        <div style="font-size: 10px; color: #6B6B6B; margin-bottom: 10px; letter-spacing: 0.3px;">
            De-snag cohort: <span style="font-weight: 600; color: #1A1A1A;">{{ desnag.count }}</span> of <span style="font-weight: 600; color: #1A1A1A;">{{ kpi.units_inspected }}</span> inspected units &middot; <span style="font-weight: 600; color: #1A1A1A;">{{ kpi.units_inspected - desnag.count }}</span> still at first inspection
        </div>

        <div class="rate-cards">"""

assert old4 in content, "PATCH D.4 MATCH FAILED: Section 02 header + rate-cards block"
assert content.count(old4) == 1, "PATCH D.4 NOT UNIQUE"
content = content.replace(old4, new4)

with io.open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('PATCH v322d APPLIED: site_meeting_brief.html - Section 02 vocabulary (Unit Certification + certified + in de-snag + cohort subtitle)')
