#!/usr/bin/env python3
"""Step 7: Photos for latent defect notes.

Touches three files:
  1. requirements.txt                              — add pillow-heif
  2. app/routes/approvals.py                       — imports + helper + 3 new routes + 3 route mods
  3. app/templates/approvals/unit_latent.html      — multipart form, file input,
                                                     photo grid, Add Photo modal,
                                                     Lightbox, JS wiring

Idempotent: top-level idempotency asserts abort cleanly on re-run.
All find/replace targets are anchored with `assert count == 1` for unique-match safety.
Run from repo root: python3 step7_photos.py
"""
import os
import sys


# ====================================================================
# EDIT 1: requirements.txt
# ====================================================================
REQ_PATH = 'requirements.txt'
print('Editing', REQ_PATH)
with open(REQ_PATH) as f:
    req = f.read()

assert 'pillow-heif' not in req, 'requirements.txt already has pillow-heif (idempotent abort)'
assert 'playwright==1.44.0' in req, 'Expected anchor "playwright==1.44.0" missing in requirements.txt'

req_new = req.rstrip() + '\npillow-heif==0.18.0\n'


# ====================================================================
# EDIT 2: app/routes/approvals.py
# ====================================================================
APP_PATH = 'app/routes/approvals.py'
print('Editing', APP_PATH)
with open(APP_PATH) as f:
    src = f.read()

# Idempotency
assert 'def upload_note_photo' not in src, 'approvals.py already has upload_note_photo (idempotent abort)'
assert 'def serve_note_photo' not in src, 'approvals.py already has serve_note_photo'
assert 'pillow_heif' not in src, 'approvals.py already imports pillow_heif'

# --- 2a: imports (add after sanitize import)
imports_old = 'from app.utils.sanitize import sanitize_note_html'
imports_new = '''from app.utils.sanitize import sanitize_note_html
import shutil
from werkzeug.utils import secure_filename
from flask import send_from_directory
from PIL import Image, ImageOps
import pillow_heif
pillow_heif.register_heif_opener()'''
assert src.count(imports_old) == 1, '2a: imports_old not unique (count={})'.format(src.count(imports_old))
src = src.replace(imports_old, imports_new)

# --- 2b: unit_latent — add photo query, pass to template
unit_latent_old = '''    area_templates = query_db("""
        SELECT id, area_name, area_order
        FROM area_template
        WHERE tenant_id = ? AND unit_type = ?
        ORDER BY area_order
    """, [tenant_id, unit['unit_type']])

    return render_template('approvals/unit_latent.html',
        unit=unit,
        inspection=inspection,
        cycle_id=cycle_id,
        cycle_number=inspection['cycle_number'],
        latent_notes=latent_notes,
        area_templates=area_templates)'''

unit_latent_new = '''    area_templates = query_db("""
        SELECT id, area_name, area_order
        FROM area_template
        WHERE tenant_id = ? AND unit_type = ?
        ORDER BY area_order
    """, [tenant_id, unit['unit_type']])

    # Fetch photos for all notes in one query (avoid N+1)
    photos_by_note = {}
    if latent_notes:
        note_ids = [n['id'] for n in latent_notes]
        placeholders = ','.join('?' * len(note_ids))
        photo_rows = query_db(
            "SELECT id, latent_area_note_id, original_filename, display_order "
            "FROM latent_photo WHERE latent_area_note_id IN ({}) AND tenant_id = ? "
            "ORDER BY latent_area_note_id, display_order".format(placeholders),
            note_ids + [tenant_id])
        for p in photo_rows:
            photos_by_note.setdefault(p['latent_area_note_id'], []).append(p)

    return render_template('approvals/unit_latent.html',
        unit=unit,
        inspection=inspection,
        cycle_id=cycle_id,
        cycle_number=inspection['cycle_number'],
        latent_notes=latent_notes,
        area_templates=area_templates,
        photos_by_note=photos_by_note)'''
assert src.count(unit_latent_old) == 1, '2b: unit_latent_old not unique (count={})'.format(src.count(unit_latent_old))
src = src.replace(unit_latent_old, unit_latent_new)

# --- 2c: add_area_note — save photos + amended flash
add_note_old = """    log_audit(db, tenant_id, 'latent_area_note', note_id, 'created',
              new_value=note_html,
              user_id=session['user_id'], user_name=session['user_name'])

    db.commit()
    flash('Latent defect note added.', 'success')
    return redirect(url_for('approvals.unit_latent',
                            cycle_id=cycle_id, unit_id=unit_id))"""

add_note_new = """    log_audit(db, tenant_id, 'latent_area_note', note_id, 'created',
              new_value=note_html,
              user_id=session['user_id'], user_name=session['user_name'])

    # Save any uploaded photos (multipart form field 'photos')
    photo_files = request.files.getlist('photos')
    saved_count, rejected = _save_photos_for_note(
        db, tenant_id, note_id, photo_files, now,
        session['user_id'], session['user_name'])

    db.commit()

    msg = 'Latent defect note added.'
    if saved_count:
        msg += ' {} photo(s) attached.'.format(saved_count)
    if rejected:
        msg += ' Rejected: ' + ', '.join(rejected) + '.'
    flash(msg, 'success')
    return redirect(url_for('approvals.unit_latent',
                            cycle_id=cycle_id, unit_id=unit_id))"""
assert src.count(add_note_old) == 1, '2c: add_note_old not unique (count={})'.format(src.count(add_note_old))
src = src.replace(add_note_old, add_note_new)

# --- 2d: delete_area_note — cascade photos
del_note_old = '''    old_html = note['note_html']

    # Hard delete
    db.execute("""
        DELETE FROM latent_area_note
        WHERE id = ? AND tenant_id = ?
    """, [note_id, tenant_id])

    log_audit(db, tenant_id, 'latent_area_note', note_id, 'deleted',
              old_value=old_html, new_value=None,
              user_id=session['user_id'], user_name=session['user_name'])'''

del_note_new = '''    old_html = note['note_html']

    # Cascade delete: gather photos, remove files + dir, then DB rows
    photos = query_db("""
        SELECT id, file_path FROM latent_photo
        WHERE latent_area_note_id = ? AND tenant_id = ?
    """, [note_id, tenant_id])
    photo_count = len(photos) if photos else 0

    for p in (photos or []):
        try:
            if p['file_path'] and os.path.exists(p['file_path']):
                os.remove(p['file_path'])
        except Exception:
            pass

    photo_dir = os.path.join(PHOTO_BASE_DIR, note_id)
    try:
        if os.path.isdir(photo_dir):
            shutil.rmtree(photo_dir)
    except Exception:
        pass

    if photo_count:
        db.execute("""
            DELETE FROM latent_photo
            WHERE latent_area_note_id = ? AND tenant_id = ?
        """, [note_id, tenant_id])

    # Hard delete (note row)
    db.execute("""
        DELETE FROM latent_area_note
        WHERE id = ? AND tenant_id = ?
    """, [note_id, tenant_id])

    audit_old = old_html
    if photo_count:
        audit_old += ' [cascaded {} photo(s)]'.format(photo_count)

    log_audit(db, tenant_id, 'latent_area_note', note_id, 'deleted',
              old_value=audit_old, new_value=None,
              user_id=session['user_id'], user_name=session['user_name'])'''
assert src.count(del_note_old) == 1, '2d: del_note_old not unique (count={})'.format(src.count(del_note_old))
src = src.replace(del_note_old, del_note_new)

# --- 2e: insert constants + helper + 3 new routes BEFORE edit_defect route
new_routes_old = """    db.commit()
    flash('Latent defect re-opened.', 'success')
    return redirect(url_for('approvals.unit_latent',
                            cycle_id=cycle_id, unit_id=unit_id))


@approvals_bp.route('/<cycle_id>/edit-defect', methods=['POST'])"""

new_routes_new = '''    db.commit()
    flash('Latent defect re-opened.', 'success')
    return redirect(url_for('approvals.unit_latent',
                            cycle_id=cycle_id, unit_id=unit_id))


# ============================================================
# Photo upload / delete / serve for latent notes (Step 7)
# ============================================================

PHOTO_BASE_DIR = '/var/data/photos'
PHOTO_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
PHOTO_MAX_WIDTH = 1200
PHOTO_JPEG_QUALITY = 85


def _save_photos_for_note(db, tenant_id, note_id, files, now, user_id, user_name):
    """Save uploaded photo files for a latent note.

    Compresses to JPEG max 1200px wide, quality 85. EXIF orientation respected.
    Caller commits the db transaction. Returns (saved_count, rejected_filenames_list).
    Per-file errors are caught and reported via the rejected list — never raised.
    """
    if not files:
        return 0, []

    photo_dir = os.path.join(PHOTO_BASE_DIR, note_id)
    os.makedirs(photo_dir, exist_ok=True)

    max_order_row = query_db("""
        SELECT COALESCE(MAX(display_order), -1) AS max_o FROM latent_photo
        WHERE latent_area_note_id = ? AND tenant_id = ?
    """, [note_id, tenant_id], one=True)
    next_order = (max_order_row['max_o'] if max_order_row else -1) + 1

    saved = 0
    rejected = []
    for f in files:
        if not f or not f.filename:
            continue
        original_filename = secure_filename(f.filename) or 'photo'

        # Size check
        f.stream.seek(0, 2)
        size = f.stream.tell()
        f.stream.seek(0)
        if size == 0:
            continue
        if size > PHOTO_MAX_FILE_SIZE:
            rejected.append(original_filename + ' (>10MB)')
            continue

        # Open with Pillow (HEIC via registered opener)
        try:
            img = Image.open(f.stream)
            img.load()
        except Exception:
            rejected.append(original_filename + ' (invalid image)')
            continue

        # EXIF orientation
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # Strip alpha to RGB (JPEG has no alpha channel)
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode == 'P':
            img = img.convert('RGBA')
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Resize if wider than max
        if img.width > PHOTO_MAX_WIDTH:
            ratio = PHOTO_MAX_WIDTH / float(img.width)
            new_h = int(img.height * ratio)
            img = img.resize((PHOTO_MAX_WIDTH, new_h), Image.LANCZOS)

        # Save as JPEG
        photo_id = generate_id()
        file_path = os.path.join(photo_dir, photo_id + '.jpg')
        img.save(file_path, 'JPEG', quality=PHOTO_JPEG_QUALITY, optimize=True)
        compressed_size = os.path.getsize(file_path)

        db.execute("""
            INSERT INTO latent_photo
            (id, tenant_id, latent_area_note_id, file_path, mime_type, file_size,
             original_filename, display_order, uploaded_by, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [photo_id, tenant_id, note_id, file_path, 'image/jpeg',
              compressed_size, original_filename, next_order,
              user_id, now])

        log_audit(db, tenant_id, 'latent_photo', photo_id, 'created',
                  new_value='note_id={}; size={}'.format(note_id, compressed_size),
                  user_id=user_id, user_name=user_name)

        next_order += 1
        saved += 1

    return saved, rejected


@approvals_bp.route('/<cycle_id>/unit/<unit_id>/latent/<note_id>/photo/upload', methods=['POST'])
@require_team_lead_only
def upload_note_photo(cycle_id, unit_id, note_id):
    """Upload one or more photos to a latent area note (TL desktop, C2+ only).

    Rejects when the note is currently rectified (force re-open first).
    Multipart form field: 'photos' (multiple).
    """
    tenant_id = session['tenant_id']
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    unit = query_db("""
        SELECT id FROM unit
        WHERE id = ? AND tenant_id = ?
    """, [unit_id, tenant_id], one=True)
    if not unit:
        abort(404)

    inspection = query_db("""
        SELECT id, cycle_number FROM inspection
        WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?
    """, [unit_id, cycle_id, tenant_id], one=True)
    if not inspection:
        abort(404)

    if inspection['cycle_number'] == 1:
        flash('Latent defects do not apply at C1.', 'warning')
        return redirect(url_for('certification.my_reviews'))

    note = query_db("""
        SELECT id, rectified_at_cycle_number FROM latent_area_note
        WHERE id = ? AND unit_id = ? AND tenant_id = ?
    """, [note_id, unit_id, tenant_id], one=True)
    if not note:
        abort(404)

    if note['rectified_at_cycle_number'] is not None:
        flash('Re-open this note before adding photos.', 'warning')
        return redirect(url_for('approvals.unit_latent',
                                cycle_id=cycle_id, unit_id=unit_id))

    photo_files = request.files.getlist('photos')
    if not photo_files or all((not f or not f.filename) for f in photo_files):
        flash('Please select at least one photo.', 'error')
        return redirect(url_for('approvals.unit_latent',
                                cycle_id=cycle_id, unit_id=unit_id))

    saved_count, rejected = _save_photos_for_note(
        db, tenant_id, note_id, photo_files, now,
        session['user_id'], session['user_name'])

    db.commit()

    msg_parts = []
    if saved_count:
        msg_parts.append('{} photo(s) added'.format(saved_count))
    if rejected:
        msg_parts.append('Rejected: ' + ', '.join(rejected))
    flash(' | '.join(msg_parts) if msg_parts else 'No photos saved.',
          'success' if saved_count else 'error')
    return redirect(url_for('approvals.unit_latent',
                            cycle_id=cycle_id, unit_id=unit_id))


@approvals_bp.route('/<cycle_id>/unit/<unit_id>/latent/<note_id>/photo/<photo_id>/delete', methods=['POST'])
@require_team_lead_only
def delete_note_photo(cycle_id, unit_id, note_id, photo_id):
    """Delete a single photo (TL desktop, C2+ only).

    Rejects when the parent note is rectified (force re-open first).
    Removes file from disk + DB row.
    """
    tenant_id = session['tenant_id']
    db = get_db()

    unit = query_db("""
        SELECT id FROM unit
        WHERE id = ? AND tenant_id = ?
    """, [unit_id, tenant_id], one=True)
    if not unit:
        abort(404)

    inspection = query_db("""
        SELECT id, cycle_number FROM inspection
        WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?
    """, [unit_id, cycle_id, tenant_id], one=True)
    if not inspection:
        abort(404)

    if inspection['cycle_number'] == 1:
        flash('Latent defects do not apply at C1.', 'warning')
        return redirect(url_for('certification.my_reviews'))

    note = query_db("""
        SELECT id, rectified_at_cycle_number FROM latent_area_note
        WHERE id = ? AND unit_id = ? AND tenant_id = ?
    """, [note_id, unit_id, tenant_id], one=True)
    if not note:
        abort(404)

    if note['rectified_at_cycle_number'] is not None:
        flash('Re-open the note before deleting photos.', 'warning')
        return redirect(url_for('approvals.unit_latent',
                                cycle_id=cycle_id, unit_id=unit_id))

    photo = query_db("""
        SELECT id, file_path, original_filename FROM latent_photo
        WHERE id = ? AND latent_area_note_id = ? AND tenant_id = ?
    """, [photo_id, note_id, tenant_id], one=True)
    if not photo:
        abort(404)

    try:
        if photo['file_path'] and os.path.exists(photo['file_path']):
            os.remove(photo['file_path'])
    except Exception:
        pass  # best effort; DB row will still go

    db.execute("""
        DELETE FROM latent_photo
        WHERE id = ? AND tenant_id = ?
    """, [photo_id, tenant_id])

    log_audit(db, tenant_id, 'latent_photo', photo_id, 'deleted',
              old_value='note_id={}; file={}'.format(note_id, photo['original_filename'] or ''),
              user_id=session['user_id'], user_name=session['user_name'])

    db.commit()
    flash('Photo deleted.', 'success')
    return redirect(url_for('approvals.unit_latent',
                            cycle_id=cycle_id, unit_id=unit_id))


@approvals_bp.route('/<cycle_id>/unit/<unit_id>/latent/<note_id>/photo/<photo_id>')
@require_team_lead_only
def serve_note_photo(cycle_id, unit_id, note_id, photo_id):
    """Serve a single photo file.

    Tenant + unit + note scope check before send_from_directory.
    Permissive (no C1 guard) since this is read-only and matches the page's auth.
    """
    tenant_id = session['tenant_id']

    photo = query_db("""
        SELECT p.id, p.file_path, p.mime_type
        FROM latent_photo p
        JOIN latent_area_note n ON p.latent_area_note_id = n.id
        WHERE p.id = ?
          AND p.latent_area_note_id = ?
          AND p.tenant_id = ?
          AND n.unit_id = ?
    """, [photo_id, note_id, tenant_id, unit_id], one=True)
    if not photo:
        abort(404)

    if not photo['file_path'] or not os.path.exists(photo['file_path']):
        abort(404)

    directory = os.path.dirname(photo['file_path'])
    filename = os.path.basename(photo['file_path'])
    return send_from_directory(directory, filename, mimetype=photo['mime_type'])


@approvals_bp.route('/<cycle_id>/edit-defect', methods=['POST'])'''
assert src.count(new_routes_old) == 1, '2e: new_routes_old not unique (count={})'.format(src.count(new_routes_old))
src = src.replace(new_routes_old, new_routes_new)


# ====================================================================
# EDIT 3: app/templates/approvals/unit_latent.html
# ====================================================================
TPL_PATH = 'app/templates/approvals/unit_latent.html'
print('Editing', TPL_PATH)
with open(TPL_PATH) as f:
    tpl = f.read()

# Idempotency
assert 'addPhotoModal' not in tpl, 'unit_latent.html already has addPhotoModal (idempotent abort)'
assert 'photos_by_note' not in tpl, 'unit_latent.html already references photos_by_note'

# --- 3a: enctype on Add Note form
enc_old = '''        <form id="addNoteForm" method="POST"
              action="{{ url_for('approvals.add_area_note', cycle_id=cycle_id, unit_id=unit.id) }}">'''
enc_new = '''        <form id="addNoteForm" method="POST" enctype="multipart/form-data"
              action="{{ url_for('approvals.add_area_note', cycle_id=cycle_id, unit_id=unit.id) }}">'''
assert tpl.count(enc_old) == 1, '3a: enc_old not unique (count={})'.format(tpl.count(enc_old))
tpl = tpl.replace(enc_old, enc_new)

# --- 3b: file input inside Add Note modal (after Quill, before submit footer)
file_input_old = '''                <!-- Quill rich-text editor -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
                    <div id="quillEditor" style="height: 200px; background: white;"></div>
                    <input type="hidden" name="note_html" id="noteHtmlInput">
                </div>
            </div>'''
file_input_new = '''                <!-- Quill rich-text editor -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
                    <div id="quillEditor" style="height: 200px; background: white;"></div>
                    <input type="hidden" name="note_html" id="noteHtmlInput">
                </div>
                <!-- Photos (optional) -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Photos (optional)</label>
                    <input type="file" name="photos" multiple accept="image/*"
                           class="block w-full text-sm text-gray-700">
                    <p class="text-xs text-gray-500 mt-1">Max 10MB per file. Supports JPEG, PNG, HEIC.</p>
                </div>
            </div>'''
assert tpl.count(file_input_old) == 1, '3b: file_input_old not unique'
tpl = tpl.replace(file_input_old, file_input_new)

# --- 3c: photo grid in note card (after status badge, before buttons row)
photo_grid_old = '''                {% endif %}
                </div>

                <div class="mt-2 flex justify-end gap-3 items-center">'''
photo_grid_new = '''                {% endif %}
                </div>

                {# Photos grid #}
                {% set photos = photos_by_note.get(n.id, []) %}
                {% if photos %}
                <div class="mt-3 grid grid-cols-3 sm:grid-cols-4 gap-2">
                    {% for p in photos %}
                    <div class="relative group">
                        <img src="{{ url_for('approvals.serve_note_photo', cycle_id=cycle_id, unit_id=unit.id, note_id=n.id, photo_id=p.id) }}"
                             alt="{{ p.original_filename or 'Photo' }}"
                             class="w-full h-24 object-cover rounded cursor-pointer border border-gray-200"
                             onclick="openLightbox(this.src)">
                        {% if not n.rectified_at_cycle_number %}
                        <form method="POST"
                              action="{{ url_for('approvals.delete_note_photo', cycle_id=cycle_id, unit_id=unit.id, note_id=n.id, photo_id=p.id) }}"
                              class="absolute top-1 right-1 m-0"
                              onsubmit="return confirm('Delete this photo?');">
                            <button type="submit"
                                    class="bg-red-600 hover:bg-red-700 text-white rounded-full w-5 h-5 text-xs leading-none flex items-center justify-center"
                                    title="Delete photo">&times;</button>
                        </form>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
                {% endif %}

                <div class="mt-2 flex justify-end gap-3 items-center">'''
assert tpl.count(photo_grid_old) == 1, '3c: photo_grid_old not unique (count={})'.format(tpl.count(photo_grid_old))
tpl = tpl.replace(photo_grid_old, photo_grid_new)

# --- 3d: "+ Add Photo" button before Edit in outstanding state
add_photo_btn_old = '''                    {% else %}
                    {# Outstanding state: Edit + Delete + Mark Rectified #}
                    <button type="button"
                            class="js-edit-note text-xs text-blue-600 hover:text-blue-800"
                            data-edit-url="{{ url_for('approvals.edit_area_note', cycle_id=cycle_id, unit_id=unit.id, note_id=n.id) }}"
                            data-note-html="{{ n.note_html|e }}">
                        Edit
                    </button>'''
add_photo_btn_new = '''                    {% else %}
                    {# Outstanding state: Add Photo + Edit + Delete + Mark Rectified #}
                    <button type="button"
                            class="js-add-photo text-xs text-gray-600 hover:text-gray-800"
                            data-upload-url="{{ url_for('approvals.upload_note_photo', cycle_id=cycle_id, unit_id=unit.id, note_id=n.id) }}">
                        + Add Photo
                    </button>
                    <button type="button"
                            class="js-edit-note text-xs text-blue-600 hover:text-blue-800"
                            data-edit-url="{{ url_for('approvals.edit_area_note', cycle_id=cycle_id, unit_id=unit.id, note_id=n.id) }}"
                            data-note-html="{{ n.note_html|e }}">
                        Edit
                    </button>'''
assert tpl.count(add_photo_btn_old) == 1, '3d: add_photo_btn_old not unique'
tpl = tpl.replace(add_photo_btn_old, add_photo_btn_new)

# --- 3e: Add Photo Modal + Lightbox before Quill JS script
modals_old = '''<!-- Quill JS + modal handlers -->
<script src="https://cdn.quilljs.com/1.3.7/quill.min.js"></script>'''
modals_new = '''<!-- Add Photo Modal -->
<div id="addPhotoModal" class="hidden fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
    <div class="bg-white rounded-lg shadow-xl max-w-md w-full">
        <form id="addPhotoForm" method="POST" action="" enctype="multipart/form-data">
            <div class="p-4 border-b">
                <h3 class="text-lg font-semibold text-gray-900">Add photo(s)</h3>
            </div>
            <div class="p-4">
                <input type="file" name="photos" id="addPhotoFileInput" multiple accept="image/*"
                       class="block w-full text-sm text-gray-700" required>
                <p class="text-xs text-gray-500 mt-1">Max 10MB per file. Supports JPEG, PNG, HEIC.</p>
            </div>
            <div class="p-4 border-t bg-gray-50 flex justify-end gap-2">
                <button type="button" onclick="closeAddPhotoModal()"
                        class="px-4 py-2 text-sm border border-gray-300 rounded-md bg-white hover:bg-gray-50">
                    Cancel
                </button>
                <button type="submit"
                        class="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-md font-medium">
                    Upload
                </button>
            </div>
        </form>
    </div>
</div>

<!-- Lightbox -->
<div id="lightbox" class="hidden fixed inset-0 bg-black bg-opacity-90 z-[60] flex items-center justify-center p-4" onclick="closeLightbox()">
    <img id="lightboxImg" src="" alt="" class="max-h-full max-w-full object-contain">
    <button type="button" class="absolute top-4 right-4 text-white text-3xl leading-none hover:text-gray-300"
            onclick="event.stopPropagation(); closeLightbox();">&times;</button>
</div>

<!-- Quill JS + modal handlers -->
<script src="https://cdn.quilljs.com/1.3.7/quill.min.js"></script>'''
assert tpl.count(modals_old) == 1, '3e: modals_old not unique'
tpl = tpl.replace(modals_old, modals_new)

# --- 3f: JS wiring inside IIFE (Add Photo + Escape handler)
js_old = """    // === DELETE MODAL ===
    // Wire up Delete buttons -- set form action + show area name + open confirm modal
    document.querySelectorAll('.js-delete-note').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var deleteUrl = this.dataset.deleteUrl;
            var areaName = this.dataset.areaName;
            document.getElementById('deleteNoteForm').action = deleteUrl;
            document.getElementById('deleteAreaName').textContent = areaName;
            document.getElementById('deleteNoteModal').classList.remove('hidden');
        });
    });
})();"""
js_new = """    // === DELETE MODAL ===
    // Wire up Delete buttons -- set form action + show area name + open confirm modal
    document.querySelectorAll('.js-delete-note').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var deleteUrl = this.dataset.deleteUrl;
            var areaName = this.dataset.areaName;
            document.getElementById('deleteNoteForm').action = deleteUrl;
            document.getElementById('deleteAreaName').textContent = areaName;
            document.getElementById('deleteNoteModal').classList.remove('hidden');
        });
    });

    // === ADD PHOTO MODAL ===
    // Wire up '+ Add Photo' buttons on note cards
    document.querySelectorAll('.js-add-photo').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var uploadUrl = this.dataset.uploadUrl;
            document.getElementById('addPhotoForm').action = uploadUrl;
            document.getElementById('addPhotoFileInput').value = '';
            document.getElementById('addPhotoModal').classList.remove('hidden');
        });
    });

    // ESC closes lightbox
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeLightbox();
    });
})();"""
assert tpl.count(js_old) == 1, '3f: js_old not unique'
tpl = tpl.replace(js_old, js_new)

# --- 3g: global close helpers (after closeDeleteModal)
helpers_old = """function closeDeleteModal() {
    document.getElementById('deleteNoteModal').classList.add('hidden');
}
</script>"""
helpers_new = """function closeDeleteModal() {
    document.getElementById('deleteNoteModal').classList.add('hidden');
}

function closeAddPhotoModal() {
    document.getElementById('addPhotoModal').classList.add('hidden');
    document.getElementById('addPhotoFileInput').value = '';
}

function openLightbox(url) {
    document.getElementById('lightboxImg').src = url;
    document.getElementById('lightbox').classList.remove('hidden');
}

function closeLightbox() {
    document.getElementById('lightbox').classList.add('hidden');
    document.getElementById('lightboxImg').src = '';
}
</script>"""
assert tpl.count(helpers_old) == 1, '3g: helpers_old not unique'
tpl = tpl.replace(helpers_old, helpers_new)


# ====================================================================
# WRITE all files
# ====================================================================
print('All asserts passed. Writing files...')

with open(REQ_PATH, 'w') as f:
    f.write(req_new)
print('  wrote', REQ_PATH)

with open(APP_PATH, 'w') as f:
    f.write(src)
print('  wrote', APP_PATH)

with open(TPL_PATH, 'w') as f:
    f.write(tpl)
print('  wrote', TPL_PATH)

print('')
print('SUCCESS. Verify with:')
print('  grep -c pillow-heif requirements.txt')
print('  grep -cE "def upload_note_photo|def delete_note_photo|def serve_note_photo" app/routes/approvals.py')
print('  grep -cE "addPhotoModal|photos_by_note|openLightbox" app/templates/approvals/unit_latent.html')
