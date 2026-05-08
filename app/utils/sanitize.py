"""
HTML sanitization for rich-text fields (latent area notes).

Uses bleach to strip everything except a small set of formatting tags
matching the WYSIWYG toolbar in the inspector mobile + TL desktop UI.
"""
import bleach

ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li']
ALLOWED_ATTRIBUTES = {}


def sanitize_note_html(raw_html):
    """Strip all tags and attributes except the WYSIWYG whitelist.

    Input:  HTML string from contenteditable / WYSIWYG editor.
    Output: sanitized HTML safe to store in DB and render in templates.
    """
    if raw_html is None:
        return ''
    return bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )
