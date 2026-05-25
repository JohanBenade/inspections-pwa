"""
v322 Patch C - app/templates/analytics/site_meeting_brief.html
Section 04 (Defect Pool) relocates to Page 2 (gets its own page).

Two changes in one block:
  1. Add page-break-before: always to the section wrapper (forces Page 2)
  2. Bump SVG height 150px -> 300px (the "enlarged" part of the spec)
  3. Replace stale comment "<!-- Page footer scope text -->"

Section order stays the same in source - just adds a page-break.
Section 05 (Zones) still has its own page-break so it lands on Page 3.
"""
import io

path = 'app/templates/analytics/site_meeting_brief.html'
with io.open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_block = """    <!-- Page footer scope text -->
    <div class="section">
        <div class="section-header">
            <span class="section-number">04</span>
            <span class="section-title">Defect Pool</span>
        </div>

        {% if svg_open %}
        <svg viewBox="0 0 {{ chart_w + 20 }} {{ chart_h + 30 }}" xmlns="http://www.w3.org/2000/svg"
             style="width: 100%; height: 150px; margin: 0 auto 4px auto; display: block;\""""

new_block = """    <!-- SECTION 04: DEFECT POOL (Page 2, enlarged) - v322 -->
    <div class="section" style="page-break-before: always; break-before: page;">
        <div class="section-header">
            <span class="section-number">04</span>
            <span class="section-title">Defect Pool</span>
        </div>

        {% if svg_open %}
        <svg viewBox="0 0 {{ chart_w + 20 }} {{ chart_h + 30 }}" xmlns="http://www.w3.org/2000/svg"
             style="width: 100%; height: 300px; margin: 0 auto 4px auto; display: block;\""""

assert old_block in content, "PATCH C MATCH FAILED: Section 04 opening block"
assert content.count(old_block) == 1, "PATCH C NOT UNIQUE"
content = content.replace(old_block, new_block)

with io.open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('PATCH v322c APPLIED: site_meeting_brief.html - Section 04 Defect Pool now on Page 2, SVG enlarged to 300px')
