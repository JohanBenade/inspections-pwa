"""
Patch: Combined Report v2
- Remove Inspector column from Unit Summary Table
- Replace signature block to match Phase 1 report (single Prepared by, no Raubex)
- Replace footer to match Phase 1 report (thick border, Generated date, disclaimer)
- Update CSS to match Phase 1 visual style
"""
import os

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    'app', 'templates', 'analytics', 'report_combined.html')

with open(FILE, 'r') as f:
    content = f.read()

original = content  # keep backup for verification

# ============================================================
# 1. REMOVE INSPECTOR COLUMN - HEADER
# ============================================================
old_th = '        <th>Inspector</th>\n'
if old_th in content:
    content = content.replace(old_th, '', 1)
    print('[OK] Removed Inspector <th>')
else:
    print('[WARN] Inspector <th> not found')

# ============================================================
# 2. REMOVE INSPECTOR COLUMN - DATA ROW
# ============================================================
old_td = '        <td>{{ u.inspector_name }}</td>\n'
if old_td in content:
    content = content.replace(old_td, '', 1)
    print('[OK] Removed Inspector <td>')
else:
    print('[WARN] Inspector <td> not found')

# ============================================================
# 3. REPLACE SIGNATURE BLOCK (table -> simple div, matching Phase 1)
# ============================================================
old_sig = """    <table class="sig-table">
    <tr>
        <td class="sig-cell">
            <div style="margin-bottom: 4px; font-size: 10px; color: #9A9A9A; text-transform: uppercase; letter-spacing: 1px;">Prepared by</div>
            {% if sig_b64 %}
            <img src="data:image/png;base64,{{ sig_b64 }}" alt="Signature" class="sig-image">
            {% endif %}
            <div class="sig-line">
                <div class="sig-name">Kevin Coetzee</div>
                <div class="sig-company">Monograph Architects</div>
                <div class="sig-title">PrArch, MD</div>
                <div class="sig-date">{{ report_date }}</div>
            </div>
        </td>
        <td class="sig-cell">
            <div style="margin-bottom: 4px; font-size: 10px; color: #9A9A9A; text-transform: uppercase; letter-spacing: 1px;">Acknowledged by</div>
            <div class="sig-line" style="margin-top: 90px;">
                <div class="sig-name">________________________</div>
                <div class="sig-company">Raubex Building</div>
                <div class="sig-date">Date: _______________</div>
            </div>
        </td>
    </tr>
    </table>"""

new_sig = """<div class="signature-block">
    <div class="sig-label">Prepared by</div>
    <div class="sig-line">
        <span class="sig-name">Kevin Coetzee</span>
    </div>
    <div class="sig-company">PrArch, MD</div>
    <div class="sig-company">Monograph Architects</div>
    <div class="sig-date">{{ report_date }}</div>
</div>"""

if old_sig in content:
    content = content.replace(old_sig, new_sig, 1)
    print('[OK] Replaced signature block (Phase 1 pattern)')
else:
    print('[WARN] Signature block not found - check whitespace')

# ============================================================
# 4. REPLACE FOOTER (match Phase 1 exactly)
# ============================================================
old_footer = """<div class="report-footer clearfix">
    <div class="footer-left">
        {% if logo_b64 %}
        <img src="data:image/jpeg;base64,{{ logo_b64 }}" class="footer-logo" alt="Monograph">
        {% endif %}
        Power Park Student Housing - Phase 3 | Combined Report | {{ report_date }}
    </div>
    <div class="footer-right">
        inspections.archpractice.co.za
    </div>
</div>
</div><!-- /.page -->
</body>
</html>"""

new_footer = """<div class="report-footer clearfix">
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
</html>"""

if old_footer in content:
    content = content.replace(old_footer, new_footer, 1)
    print('[OK] Replaced footer (Phase 1 pattern + disclaimer)')
else:
    print('[WARN] Footer block not found - check whitespace')

# ============================================================
# 5. UPDATE CSS - Replace sig CSS + footer CSS to match Phase 1
# ============================================================

# 5a. Replace sig CSS
old_sig_css = """.sig-table { width: 100%; border-collapse: collapse; margin-top: 40px; }
.sig-cell { width: 50%; vertical-align: top; padding: 0; }
.sig-line { border-top: 1px solid #0A0A0A; padding-top: 6px; margin-top: 40px; width: 85%; }
.sig-name { font-weight: 600; font-size: 12px; color: #0A0A0A; }
.sig-company { font-size: 10px; color: #6B6B6B; margin-top: 1px; }
.sig-title { font-size: 10px; color: #9A9A9A; margin-top: 1px; }
.sig-date { font-size: 10px; color: #9A9A9A; margin-top: 6px; }
.sig-image { height: 50px; width: auto; margin-bottom: -10px; }"""

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
.sig-date { font-size: 10px; color: #9A9A9A; }"""

if old_sig_css in content:
    content = content.replace(old_sig_css, new_sig_css, 1)
    print('[OK] Replaced signature CSS (Phase 1 pattern)')
else:
    print('[WARN] Signature CSS not found')

# 5b. Replace footer CSS
old_footer_css = """.report-footer {
    margin-top: 30px;
    padding-top: 12px;
    border-top: 1px solid #E5E5E5;
    font-size: 9px;
    color: #9A9A9A;
}
.report-footer::after { content: ""; display: table; clear: both; }
.footer-left { float: left; }
.footer-right { float: right; text-align: right; }
.footer-logo { height: 16px; width: auto; vertical-align: middle; margin-right: 6px; }"""

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
}"""

if old_footer_css in content:
    content = content.replace(old_footer_css, new_footer_css, 1)
    print('[OK] Replaced footer CSS (Phase 1 pattern + disclaimer)')
else:
    print('[WARN] Footer CSS not found')

# ============================================================
# WRITE
# ============================================================
if content != original:
    with open(FILE, 'w') as f:
        f.write(content)
    print(f'\n[DONE] File updated: {FILE}')
    print(f'  Original: {len(original)} chars')
    print(f'  Updated:  {len(content)} chars')
else:
    print('\n[ERROR] No changes made - all patterns failed to match')
