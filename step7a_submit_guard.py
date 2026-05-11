#!/usr/bin/env python3
"""
Step 7a: Submit-guard hotfix for unit_latent.html

Bug fixed:
  Add Note form (and other forms) on the latent unit page are double-submittable.
  A multipart upload with 3 photos takes ~5 seconds; user clicks Save twice
  during the wait; both POSTs land on separate Gunicorn workers; each creates
  its own note + photos. Result: duplicate note rows with identical content
  and duplicate photo files. Confirmed in v291 thread on Unit 253 (BATHROOM
  note duplicated, IDs 3d704c94 + 702dfa51).

Fix:
  1. Add data-loading-text attributes to 4 modal submit buttons (Save note,
     Save changes, Delete, Upload).
  2. Inject preventDoubleSubmit() helper at end of existing IIFE.
  3. Apply the helper to every <form> on the page.

Behaviour:
  - First submit click: button greys out (opacity 0.6, disabled, cursor
    not-allowed) and text changes to "Saving..." / "Uploading..." /
    "Deleting...". Form submits normally.
  - Second submit click during the wait: e.preventDefault() blocks it.
  - If another handler already cancelled the submit (e.g. window.confirm
    returned false on the per-photo delete x button), the guard short-circuits
    via e.defaultPrevented so the user can try again.

Idempotent: re-running detects the 'preventDoubleSubmit' marker and exits.
"""

import sys
from pathlib import Path

TEMPLATE = Path("app/templates/approvals/unit_latent.html")

if not TEMPLATE.exists():
    print(f"ERROR: {TEMPLATE} not found. Run from repo root.")
    sys.exit(1)

content = TEMPLATE.read_text()

# Idempotency check
if "preventDoubleSubmit" in content:
    print("Step 7a already applied (preventDoubleSubmit marker found). No-op.")
    sys.exit(0)

# ---- Anchor 1: Add Note "Save note" button ----
old_1 = '''                <button type="submit"
                        class="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-md font-medium">
                    Save note
                </button>'''
new_1 = '''                <button type="submit"
                        data-loading-text="Saving..."
                        class="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-md font-medium">
                    Save note
                </button>'''
assert old_1 in content, "Anchor 1 (Save note button) not found"
assert content.count(old_1) == 1, f"Anchor 1 count != 1 (got {content.count(old_1)})"
content = content.replace(old_1, new_1)
print("  [1/5] Add Note 'Save note' -> data-loading-text added")

# ---- Anchor 2: Edit Note "Save changes" button ----
old_2 = '''                <button type="submit"
                        class="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-md font-medium">
                    Save changes
                </button>'''
new_2 = '''                <button type="submit"
                        data-loading-text="Saving..."
                        class="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-md font-medium">
                    Save changes
                </button>'''
assert old_2 in content, "Anchor 2 (Save changes button) not found"
assert content.count(old_2) == 1, f"Anchor 2 count != 1 (got {content.count(old_2)})"
content = content.replace(old_2, new_2)
print("  [2/5] Edit Note 'Save changes' -> data-loading-text added")

# ---- Anchor 3: Delete Confirm "Delete" button ----
old_3 = '''                <button type="submit"
                        class="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-md font-medium">
                    Delete
                </button>'''
new_3 = '''                <button type="submit"
                        data-loading-text="Deleting..."
                        class="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-md font-medium">
                    Delete
                </button>'''
assert old_3 in content, "Anchor 3 (Delete confirm button) not found"
assert content.count(old_3) == 1, f"Anchor 3 count != 1 (got {content.count(old_3)})"
content = content.replace(old_3, new_3)
print("  [3/5] Delete Confirm 'Delete' -> data-loading-text added")

# ---- Anchor 4: Add Photo "Upload" button ----
old_4 = '''                <button type="submit"
                        class="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-md font-medium">
                    Upload
                </button>'''
new_4 = '''                <button type="submit"
                        data-loading-text="Uploading..."
                        class="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-md font-medium">
                    Upload
                </button>'''
assert old_4 in content, "Anchor 4 (Upload button) not found"
assert content.count(old_4) == 1, f"Anchor 4 count != 1 (got {content.count(old_4)})"
content = content.replace(old_4, new_4)
print("  [4/5] Add Photo 'Upload' -> data-loading-text added")

# ---- Anchor 5: IIFE closer (insert submit-guard logic before })(); ----
old_5 = '''    // ESC closes lightbox
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeLightbox();
    });
})();'''
new_5 = '''    // ESC closes lightbox
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeLightbox();
    });

    // === SUBMIT GUARD ===
    // Prevents double-submission on slow forms (multipart uploads especially).
    // Applied to every <form> on this page.
    function preventDoubleSubmit(form) {
        form.addEventListener('submit', function(e) {
            // If another handler already cancelled the submit (e.g. confirm
            // dialog returned false), don't lock -- user can try again.
            if (e.defaultPrevented) return;
            if (form.dataset.submitting === '1') {
                e.preventDefault();
                return false;
            }
            form.dataset.submitting = '1';
            var btn = form.querySelector('button[type="submit"]');
            if (btn) {
                btn.disabled = true;
                btn.style.opacity = '0.6';
                btn.style.cursor = 'not-allowed';
                if (btn.dataset.loadingText) {
                    btn.dataset.originalText = btn.textContent;
                    btn.textContent = btn.dataset.loadingText;
                }
            }
        });
    }
    document.querySelectorAll('form').forEach(preventDoubleSubmit);
})();'''
assert old_5 in content, "Anchor 5 (IIFE closer with ESC handler) not found"
assert content.count(old_5) == 1, f"Anchor 5 count != 1 (got {content.count(old_5)})"
content = content.replace(old_5, new_5)
print("  [5/5] preventDoubleSubmit() injected into IIFE")

# Write back
TEMPLATE.write_text(content)
print(f"\n[OK] {TEMPLATE} updated.")
print("\nVerify with:")
print(f"  grep -c 'data-loading-text' {TEMPLATE}    # expect: 4")
print(f"  grep -c 'preventDoubleSubmit' {TEMPLATE}  # expect: 3")
