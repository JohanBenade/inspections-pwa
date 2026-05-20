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


def split_note_html_by_li(html):
    """Split sanitised note HTML into one string per <li>, IFF content is
    a pure list (a single <ul> or <ol> with >=2 <li>s and nothing else).

    Returns a list of HTML strings. Each output string is a single-item
    list of the same type as the input (<ul> or <ol>).

    Returns [html] unchanged for:
      - empty / falsy input
      - single <li> (no point splitting)
      - no list at all (plain <p>, etc.)
      - mixed content (anything outside the single root <ul>/<ol>)
    """
    from bs4 import BeautifulSoup
    if not html:
        return [html]
    soup = BeautifulSoup(html, 'html.parser')
    def _ignorable(c):
        if isinstance(c, str):
            return not c.strip()
        if getattr(c, 'name', None) == 'p' and not c.get_text(strip=True):
            return True
        return False
    children = [c for c in soup.children if not _ignorable(c)]
    if len(children) != 1:
        return [html]
    root = children[0]
    if getattr(root, 'name', None) not in ('ul', 'ol'):
        return [html]
    lis = root.find_all('li', recursive=False)
    if len(lis) < 2:
        return [html]
    tag = root.name
    return [f'<{tag}><li>{li.decode_contents()}</li></{tag}>' for li in lis]
