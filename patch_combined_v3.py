"""
Patch: Combined Report v3 - LINE-NUMBER BASED
Verified from Render console output 09 Feb 2026.

Changes:
1. Delete line 714: <th>Inspector</th>
2. Delete line 732: <td>{{ u.inspector_name }}</td>
3. Replace lines 341-348: sig CSS -> Phase 1 sig CSS
4. Replace lines 351-361: footer CSS -> Phase 1 footer CSS + disclaimer CSS
5. Replace lines 745-771: signature HTML -> Phase 1 signature HTML
6. Replace lines 773-end: footer HTML -> Phase 1 footer HTML + disclaimer

Working BOTTOM-UP to preserve line numbers.
"""
import os

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'app', 'templates', 'analytics', 'report_combined.html')

with open(FILE, 'r') as f:
    lines = f.readlines()

total = len(lines)
print(f'File: {FILE}')
print(f'Total lines: {total}')

# ============================================================
# SAFETY: Verify key lines before changing anything
# ============================================================
errors = []

def check(line_num, expected_fragment):
    """Verify line content before editing. line_num is 1-indexed."""
    idx = line_num - 1
    if idx >= len(lines):
        errors.append(f'Line {line_num}: OUT OF RANGE (file has {len(lines)} lines)')
        return False
    actual = lines[idx].strip()
    if expected_fragment not in actual:
        errors.append(f'Line {line_num}: Expected "{expected_fragment}" but got "{actual}"')
        return False
    return True

check(714, '<th>Inspector</th>')
check(732, 'u.inspector_name')
check(341, '.sig-table')
check(351, '.report-footer')
check(745, 'SIGNATURE BLOCK')
check(774, 'report-footer clearfix')

if errors:
    print('\n!!! SAFETY CHECK FAILED !!!')
    for e in errors:
        print(f'  {e}')
    print('\nABORTING - line numbers do not match. File may have shifted.')
    exit(1)

print('All safety checks passed.\n')

# ============================================================
# WORK BOTTOM-UP (highest line numbers first)
# ============================================================

# --- 6. REPLACE FOOTER HTML (line 773 to end of file) ---
# Find actual end: search for </html>
end_idx = len(lines)  # will replace from 773 to end

new_footer_html = """<!-- ============ FOOTER ============ -->
<div class="report-footer clearfix">
    <div class="footer-left">
        {% if logo_b64 %}
        <img src="data:image/jpeg;base64,{{ logo_b64 }}" alt="Monograph" style="height: 24px; width: auto;">
        {% else %}
        <span class="logo-fallback" style="font-size: 16px;">MONOGRAPH</span>
        {% endif %}
        <div style="font-size: 9px; color: #9A9A9A; margin-top: 4px;">
            Power Park Student Housing - Phase 3 &middot; Combined Report
        </div>
    </div>
    <div class="footer-right">
        Generated {{ report_date }}
    </div>
</div>
<div class="footer-disclaimer">
    This report is generated from live inspection data. All figures are as recorded at time of generation.
    For queries, contact Monograph Architects.
</div>
</div><!-- /.page -->
</body>
</html>
"""

# Line 773 = index 772
lines[772:end_idx] = [new_footer_html]
print(f'[OK] Replaced footer HTML (line 773 to end)')

# --- 5. REPLACE SIGNATURE HTML (lines 745-771) ---
new_sig_html = """<!-- ============ SIGNATURE BLOCK ============ -->
<div class="signature-block">
    <div class="sig-label">Prepared by</div>
    <div class="sig-line">
        <span class="sig-name">Kevin Coetzee</span>
    </div>
    <div class="sig-company">PrArch, MD</div>
    <div class="sig-company">Monograph Architects</div>
    <div class="sig-date">{{ report_date }}</div>
</div>

"""

# Lines 745-771 = indices 744-770 (inclusive), plus blank line 772
lines[744:772] = [new_sig_html]
print(f'[OK] Replaced signature HTML (lines 745-772)')

# --- 4. DELETE INSPECTOR DATA CELL (line 732) ---
del lines[731]  # index 731 = line 732
print(f'[OK] Deleted inspector <td> (line 732)')

# --- 3. DELETE INSPECTOR HEADER (line 714) ---
del lines[713]  # index 713 = line 714
print(f'[OK] Deleted inspector <th> (line 714)')

# --- 2. REPLACE FOOTER CSS (lines 351-361) ---
new_footer_css = """.report-footer {
    margin-top: 28px;
    padding-top: 14px;
    border-top: 3px solid #0A0A0A;
    page-break-inside: avoid;
}
.report-footer::after { content: ""; display: table; clear: both; }
.footer-left { float: left; }
.footer-right { float: right; text-align: right; font-size: 9px; color: #9A9A9A; line-height: 1.7; }
.footer-disclaimer {
    margin-top: 14px;
    padding: 8px 12px;
    background: #F5F3EE;
    font-size: 9px;
    color: #9A9A9A;
    text-align: center;
    letter-spacing: 0.3px;
}
"""

# Lines 351-361 = indices 350-360 (inclusive)
lines[350:361] = [new_footer_css]
print(f'[OK] Replaced footer CSS (lines 351-361)')

# --- 1. REPLACE SIGNATURE CSS (lines 341-348) ---
new_sig_css = """.signature-block {
    margin-top: 40px;
    page-break-inside: avoid;
}
.sig-label {
    font-size: 10px;
    color: #9A9A9A;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
}
.sig-line { border-bottom: 1px solid #1A1A1A; padding-bottom: 3px; margin-bottom: 3px; }
.sig-name { font-size: 12px; font-weight: 500; color: #0A0A0A; }
.sig-company { font-size: 10px; color: #6B6B6B; }
.sig-date { font-size: 10px; color: #9A9A9A; }
"""

# Lines 341-348 = indices 340-347 (inclusive)
lines[340:348] = [new_sig_css]
print(f'[OK] Replaced signature CSS (lines 341-348)')

# ============================================================
# WRITE
# ============================================================
with open(FILE, 'w') as f:
    f.writelines(lines)

new_total = sum(1 for line in open(FILE))
print(f'\n[DONE] Written: {new_total} lines (was {total})')

# ============================================================
# VERIFY
# ============================================================
with open(FILE, 'r') as f:
    content = f.read()

checks = {
    'Inspector th GONE': '<th>Inspector</th>' not in content,
    'inspector_name GONE': 'u.inspector_name' not in content,
    'sig-table GONE': '.sig-table' not in content,
    'Raubex GONE': 'Raubex' not in content,
    'Acknowledged GONE': 'Acknowledged' not in content,
    'signature-block EXISTS': '.signature-block' in content,
    'sig-label EXISTS': '.sig-label' in content,
    'footer-disclaimer EXISTS': '.footer-disclaimer' in content,
    'border-top: 3px EXISTS': 'border-top: 3px solid #0A0A0A' in content,
    'Prepared by EXISTS': 'Prepared by' in content,
}

print('\n=== VERIFICATION ===')
all_ok = True
for name, passed in checks.items():
    status = 'PASS' if passed else 'FAIL'
    if not passed:
        all_ok = False
    print(f'  [{status}] {name}')

if all_ok:
    print('\nAll checks passed. Ready to commit.')
else:
    print('\nSOME CHECKS FAILED - review before committing.')
