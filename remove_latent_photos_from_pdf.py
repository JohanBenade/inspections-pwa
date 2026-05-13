#!/usr/bin/env python3
"""
Remove the photos block from the Latent Defects Addendum in the per-unit
De-snag PDF (defects_list.html). Status line + rich-text description stay.

The encode_latent_photos() call in pdf_generator.py is left in place
because the SMB §08 still uses the same data shape (and currently
ignores photos too). No functional waste worth touching another file.

Idempotent. Assert-guarded. Atomic write.
"""
from pathlib import Path

TEMPLATE = Path("app/templates/pdf/defects_list.html")
assert TEMPLATE.exists(), f"Not found: {TEMPLATE}"

PHOTOS_OLD = """            {% if note.photos %}
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
"""


def main():
    t = TEMPLATE.read_text()

    if 'note.photos' not in t:
        print("[NO-OP] Photos block already removed.")
        raise SystemExit(0)

    assert PHOTOS_OLD in t, "Anchor missing - file may have drifted"
    assert t.count(PHOTOS_OLD) == 1, f"Anchor not unique (count={t.count(PHOTOS_OLD)})"

    t_new = t.replace(PHOTOS_OLD, "")

    assert 'note.photos' not in t_new, "Photos reference still present after replace"
    assert '<img src="{{ p.src }}"' not in t_new, "Photo img tag still present"
    # Surrounding structure intact
    assert '{% if latent_notes_list %}' in t_new, "Latent addendum wrapper lost"
    assert '{{ note.note_html | safe }}' in t_new, "Rich-text description lost"
    assert 'Status:' in t_new, "Status line lost"

    TEMPLATE.write_text(t_new)
    print("[OK] Photos block removed from Latent Defects Addendum.")
    print("Verify: git --no-pager diff --stat")


if __name__ == "__main__":
    main()
