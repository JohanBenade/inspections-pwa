#!/usr/bin/env python3
"""
Step 8: Latent defects + photos in the per-unit de-snag PDF.

Touches:
  - app/services/pdf_generator.py : _fetch_latent_for_pdf helper,
                                    encode_latent_photos helper, get_defects_data
                                    return adds latent_* fields,
                                    generate_defects_pdf calls encoder
  - app/routes/pdf.py             : view_defects_html imports + calls encoder
  - app/templates/pdf/defects_list.html :
                                    Rectification Summary footer line
                                    (C2+ only, when latent exist),
                                    new "Addendum: Latent Defects Identified"
                                    block between Kevin's sign-off and
                                    existing Excluded Items addendum

Run from repo root:
    python3 step8_pdf_latent.py

Idempotent: bails cleanly if already applied.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
GEN_FILE = os.path.join(ROOT, 'app', 'services', 'pdf_generator.py')
ROUTE_FILE = os.path.join(ROOT, 'app', 'routes', 'pdf.py')
TPL_FILE = os.path.join(ROOT, 'app', 'templates', 'pdf', 'defects_list.html')

for f in (GEN_FILE, ROUTE_FILE, TPL_FILE):
    if not os.path.exists(f):
        print('ERROR: file not found: ' + f)
        print('Run from repo root: ~/Documents/GitHub/inspections-pwa/')
        sys.exit(1)

with open(GEN_FILE, 'r', encoding='utf-8') as fh:
    gen_content = fh.read()
with open(ROUTE_FILE, 'r', encoding='utf-8') as fh:
    route_content = fh.read()
with open(TPL_FILE, 'r', encoding='utf-8') as fh:
    tpl_content = fh.read()

# ---------------- Idempotency ----------------
if '_fetch_latent_for_pdf' in gen_content:
    print('Already applied: _fetch_latent_for_pdf found in pdf_generator.py. Nothing to do.')
    sys.exit(0)
if 'Latent Defects Identified' in tpl_content:
    print('Partial state: latent addendum in template but helper missing in pdf_generator.py. Manual review needed.')
    sys.exit(1)

# ============================================================
# pdf_generator.py - 3 edits
# ============================================================

# Edit G1: get_defects_data return - splat in latent fields
gen_return_anchor = """        'exclusion_notes_html': exclusion_notes_html,
        'excluded_items_by_area': excluded_items_by_area
    }"""
assert gen_content.count(gen_return_anchor) == 1, 'gen_return_anchor count != 1'

gen_return_new = """        'exclusion_notes_html': exclusion_notes_html,
        'excluded_items_by_area': excluded_items_by_area,
        **_fetch_latent_for_pdf(tenant_id, unit_id)
    }"""

# Edit G2: Insert helpers before generate_defects_pdf
gen_helpers_anchor = """def generate_defects_pdf(tenant_id, unit_id, cycle_id=None):
    \"\"\"Generate a defects list PDF for a unit.\"\"\""""
assert gen_content.count(gen_helpers_anchor) == 1, 'gen_helpers_anchor count != 1'

gen_helpers_new = '''def _fetch_latent_for_pdf(tenant_id, unit_id):
    """Fetch latent area notes + photos for a unit, formatted for PDF/HTML rendering.

    Unit-scoped (all cycles). Returns:
        {'latent_notes_list': [dict, ...],
         'latent_summary': {'total': N, 'outstanding': X, 'rectified': Y}}

    Each note dict carries: id, unit_id, cycle_id, cycle_number, note_html,
    created_at, rectified_at, rectified_at_cycle_number, area_display_name,
    created_at_fmt (DD.MM.YYYY), rectified_at_fmt (DD.MM.YYYY or None),
    photos: [dict, ...] with file_path + mime_type (raw; src added by
    encode_latent_photos).
    """
    latent_rows = query_db("""
        SELECT n.id, n.unit_id, n.cycle_id, n.cycle_number, n.note_html,
               n.area_template_id, n.area_name_override, n.created_at,
               n.rectified_at_cycle_number, n.rectified_at,
               at.area_name, at.area_order
        FROM latent_area_note n
        LEFT JOIN area_template at ON n.area_template_id = at.id
        WHERE n.unit_id = ? AND n.tenant_id = ?
        ORDER BY n.cycle_number, COALESCE(at.area_order, 999), n.created_at
    """, [unit_id, tenant_id])

    if not latent_rows:
        return {
            'latent_notes_list': [],
            'latent_summary': {'total': 0, 'outstanding': 0, 'rectified': 0}
        }

    note_ids = [r['id'] for r in latent_rows]
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

    def _fmt_date(iso):
        if not iso or len(iso) < 10:
            return ''
        return '{}.{}.{}'.format(iso[8:10], iso[5:7], iso[:4])

    notes_list = []
    outstanding = 0
    rectified = 0
    for r in latent_rows:
        n = dict(r)
        n['created_at_fmt'] = _fmt_date(n.get('created_at'))
        if n.get('rectified_at_cycle_number'):
            n['rectified_at_fmt'] = _fmt_date(n.get('rectified_at'))
            rectified += 1
        else:
            n['rectified_at_fmt'] = None
            outstanding += 1
        n['area_display_name'] = (
            n.get('area_name')
            or n.get('area_name_override')
            or 'Other'
        )
        n['photos'] = photos_by_note.get(n['id'], [])
        notes_list.append(n)

    return {
        'latent_notes_list': notes_list,
        'latent_summary': {
            'total': len(notes_list),
            'outstanding': outstanding,
            'rectified': rectified
        }
    }


def encode_latent_photos(data):
    """Mutate data dict in place: add 'src' base64 data URI to each photo.

    Both HTML preview and PDF generation use base64 - keeps Playwright simple
    (no HTTP round-trip to auth-protected serve_note_photo route).
    """
    import base64
    for note in data.get('latent_notes_list', []):
        for photo in note.get('photos', []):
            file_path = photo.get('file_path')
            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        b64 = base64.b64encode(f.read()).decode()
                    mime = photo.get('mime_type') or 'image/jpeg'
                    photo['src'] = 'data:{};base64,{}'.format(mime, b64)
                except Exception:
                    photo['src'] = ''
            else:
                photo['src'] = ''


def generate_defects_pdf(tenant_id, unit_id, cycle_id=None):
    """Generate a defects list PDF for a unit."""'''

# Edit G3: generate_defects_pdf - call encoder after data fetch
gen_pdf_anchor = """    data = get_defects_data(tenant_id, unit_id, cycle_id)
    if not data:
        return None

    static_folder = current_app.static_folder"""
assert gen_content.count(gen_pdf_anchor) == 1, 'gen_pdf_anchor count != 1'

gen_pdf_new = """    data = get_defects_data(tenant_id, unit_id, cycle_id)
    if not data:
        return None

    encode_latent_photos(data)

    static_folder = current_app.static_folder"""

# ============================================================
# pdf.py - 2 edits in view_defects_html
# ============================================================

# Edit R1: extend the local import
route_import_anchor = """    from app.services.pdf_generator import get_defects_data"""
assert route_content.count(route_import_anchor) == 1, 'route_import_anchor count != 1'

route_import_new = """    from app.services.pdf_generator import get_defects_data, encode_latent_photos"""

# Edit R2: call encoder after get_defects_data
route_call_anchor = """    data = get_defects_data(tenant_id, unit_id, cycle_id)
    if not data:
        abort(404)

    return render_template("""
assert route_content.count(route_call_anchor) == 1, 'route_call_anchor count != 1'

route_call_new = """    data = get_defects_data(tenant_id, unit_id, cycle_id)
    if not data:
        abort(404)

    encode_latent_photos(data)

    return render_template("""

# ============================================================
# defects_list.html - 2 insertions
# ============================================================

# Edit T1: Latent footer line in C2+ Rectification Summary box
tpl_footer_anchor = '''            {% if excluded_items_by_area %}
            <div style="border-top: 1px dashed #ccc; margin-top: 8px; padding-top: 6px; font-size: 9pt; color: #666;">Excluded from inspection: {{ summary.excluded }} items not yet assessed</div>
            {% endif %}
            {% if is_certified %}'''
assert tpl_content.count(tpl_footer_anchor) == 1, 'tpl_footer_anchor count != 1'

tpl_footer_new = '''            {% if excluded_items_by_area %}
            <div style="border-top: 1px dashed #ccc; margin-top: 8px; padding-top: 6px; font-size: 9pt; color: #666;">Excluded from inspection: {{ summary.excluded }} items not yet assessed</div>
            {% endif %}
            {% if latent_summary and latent_summary.total > 0 %}
            <div style="border-top: 1px dashed #ccc; margin-top: 8px; padding-top: 6px; font-size: 9pt; color: #666;">Latent defects to date: {{ latent_summary.total }} ({{ latent_summary.outstanding }} outstanding, {{ latent_summary.rectified }} rectified)</div>
            {% endif %}
            {% if is_certified %}'''

# Edit T2: Latent addendum block between Kevin's signature and Excluded Items
tpl_addendum_anchor = '''            <p class="signatory-title">PrArch; MD</p>
        </div>
    </div>

    {% if excluded_items_by_area %}'''
assert tpl_content.count(tpl_addendum_anchor) == 1, 'tpl_addendum_anchor count != 1'

tpl_addendum_new = '''            <p class="signatory-title">PrArch; MD</p>
        </div>
    </div>

    {% if latent_notes_list %}
    <div style="margin-top: 30px; page-break-before: auto;">
        <div class="defects-header-title"><span>Addendum: Latent Defects Identified ({{ latent_summary.total }})</span></div>
        <p style="font-size: 8pt; font-style: italic; color: #666; margin: 4px 0 12px 0;">Defects identified by the team lead during cycle reviews. These fall outside the inspection scope but are recorded for rectification during the contract period.</p>
        {% for note in latent_notes_list %}
        <div class="no-break" style="margin-bottom: 14px;">
            <div class="area-title" style="margin-bottom: 4px;"><span>{{ note.area_display_name }} &mdash; Identified at C{{ note.cycle_number }} ({{ note.created_at_fmt }})</span></div>
            <div class="rich-text" style="margin-left: 12px; margin-bottom: 6px;">{{ note.note_html | safe }}</div>
            {% if note.photos %}
            <table style="margin-left: 12px; margin-bottom: 6px; border-collapse: collapse;">
                {% for p in note.photos %}
                {% if loop.index0 % 3 == 0 %}<tr>{% endif %}
                <td style="padding: 0 6px 6px 0; vertical-align: top;">
                    {% if p.src %}
                    <img src="{{ p.src }}" style="width: 180px; height: auto; display: block; border: 1px solid #ddd;">
                    {% endif %}
                </td>
                {% if loop.index % 3 == 0 or loop.last %}</tr>{% endif %}
                {% endfor %}
            </table>
            {% endif %}
            <div style="margin-left: 12px; font-size: 9pt;">
                {% if note.rectified_at_cycle_number %}
                <span style="font-weight: 400;">Status:</span> <span style="color: #228B22; font-weight: 400;">Rectified at C{{ note.rectified_at_cycle_number }} ({{ note.rectified_at_fmt }})</span>
                {% else %}
                <span style="font-weight: 400;">Status:</span> <span style="color: #cc0000; font-weight: 400;">Outstanding</span>
                {% endif %}
            </div>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {% if excluded_items_by_area %}'''

# ============================================================
# Apply all edits in memory
# ============================================================
gen_new = gen_content
gen_new = gen_new.replace(gen_return_anchor, gen_return_new, 1)
gen_new = gen_new.replace(gen_helpers_anchor, gen_helpers_new, 1)
gen_new = gen_new.replace(gen_pdf_anchor, gen_pdf_new, 1)

route_new = route_content
route_new = route_new.replace(route_import_anchor, route_import_new, 1)
route_new = route_new.replace(route_call_anchor, route_call_new, 1)

tpl_new = tpl_content
tpl_new = tpl_new.replace(tpl_footer_anchor, tpl_footer_new, 1)
tpl_new = tpl_new.replace(tpl_addendum_anchor, tpl_addendum_new, 1)

# Post-apply sanity checks
assert 'def _fetch_latent_for_pdf' in gen_new
assert 'def encode_latent_photos' in gen_new
assert '**_fetch_latent_for_pdf(tenant_id, unit_id)' in gen_new
assert 'encode_latent_photos(data)' in gen_new  # appears in both gen + route
assert 'get_defects_data, encode_latent_photos' in route_new
assert 'Latent Defects Identified' in tpl_new
assert 'Latent defects to date' in tpl_new
assert 'latent_summary.total' in tpl_new
assert 'note.area_display_name' in tpl_new
assert 'data:{};base64' in gen_new
# Confirm encoder is called in both paths
assert route_new.count('encode_latent_photos(data)') == 1
assert gen_new.count('encode_latent_photos(data)') == 2  # def signature + standalone call

# ============================================================
# Write
# ============================================================
with open(GEN_FILE, 'w', encoding='utf-8') as fh:
    fh.write(gen_new)
with open(ROUTE_FILE, 'w', encoding='utf-8') as fh:
    fh.write(route_new)
with open(TPL_FILE, 'w', encoding='utf-8') as fh:
    fh.write(tpl_new)

print('OK Step 8 applied.')
print('  pdf_generator.py   : +{} lines'.format(gen_new.count(chr(10)) - gen_content.count(chr(10))))
print('  pdf.py             : +{} lines'.format(route_new.count(chr(10)) - route_content.count(chr(10))))
print('  defects_list.html  : +{} lines'.format(tpl_new.count(chr(10)) - tpl_content.count(chr(10))))
print('')
print('Verify with:')
print('  grep -cE "_fetch_latent_for_pdf|encode_latent_photos" app/services/pdf_generator.py')
print('  grep -c "encode_latent_photos" app/routes/pdf.py')
print('  grep -cE "Latent Defects Identified|Latent defects to date" app/templates/pdf/defects_list.html')
print('')
print('Expected: 4+, 2, 2')
print('')
print('Then commit and push:')
print('  git add -A')
print('  git commit -m "Step 8: latent defects + photos in per-unit de-snag PDF"')
print('  git push')
