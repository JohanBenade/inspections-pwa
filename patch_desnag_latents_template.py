#!/usr/bin/env python3
"""
Patch app/templates/inspection/desnag.html for Step 3.

Changes:
1. Gate: total_bfwd == 0 -> total_items == 0; empty-state copy updated.
2. Insert "Latent items" subsection at top of each area card, before
   the category loop. Blue tinted to distinguish from defects.
3. Disabled submit button: "Address all defects" -> "Address all items",
   total_bfwd -> total_items.
"""

PATH = 'app/templates/inspection/desnag.html'

with open(PATH, 'r') as f:
    content = f.read()

# ============================================================
# Change 1: Gate + empty-state text
# ============================================================

old_1 = '''    {% if total_bfwd == 0 %}
    <div class="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
        <div class="text-green-700 font-semibold text-lg">No open defects</div>
        <div class="text-green-600 text-sm mt-1">All defects from previous cycles have been cleared.</div>
    </div>
    {% else %}'''

new_1 = '''    {% if total_items == 0 %}
    <div class="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
        <div class="text-green-700 font-semibold text-lg">Nothing to address</div>
        <div class="text-green-600 text-sm mt-1">No open defects or latent items from previous cycles.</div>
    </div>
    {% else %}'''

assert old_1 in content, "Change 1 anchor not found"
assert content.count(old_1) == 1, f"Change 1 anchor not unique: {content.count(old_1)}"
content = content.replace(old_1, new_1)
print("OK change 1: gate and empty-state copy updated")

# ============================================================
# Change 2: Insert Latent items subsection inside each area card,
#           before the category loop.
# ============================================================

old_2 = '''        <div class="bg-gray-50 px-4 py-3 flex justify-between items-center border-b">
            <span class="font-semibold text-gray-900">{{ area_name }}</span>
            <span id="badge-{{ area_name|replace(' ', '-')|lower }}" class="text-xs px-2 py-1 rounded-full {% if area_data.addressed == area_data.total %}bg-green-100 text-green-700{% else %}bg-gray-200 text-gray-600{% endif %}">
                {{ area_data.addressed }} / {{ area_data.total }}
            </span>
        </div>

        {% for cat_name, defects in area_data.categories.items() %}'''

new_2 = '''        <div class="bg-gray-50 px-4 py-3 flex justify-between items-center border-b">
            <span class="font-semibold text-gray-900">{{ area_name }}</span>
            <span id="badge-{{ area_name|replace(' ', '-')|lower }}" class="text-xs px-2 py-1 rounded-full {% if area_data.addressed == area_data.total %}bg-green-100 text-green-700{% else %}bg-gray-200 text-gray-600{% endif %}">
                {{ area_data.addressed }} / {{ area_data.total }}
            </span>
        </div>

        {% if area_data.latents %}
        <div class="border-b">
            <div class="px-4 py-2 bg-blue-50">
                <span class="text-xs font-medium text-blue-700 uppercase tracking-wider">Latent items</span>
            </div>
            {% for latent in area_data.latents %}
            <div id="latent-{{ latent.id }}" class="px-4 py-3 border-t border-blue-100 bg-blue-50/30">
                {% include 'inspection/_desnag_latent.html' with context %}
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% for cat_name, defects in area_data.categories.items() %}'''

assert old_2 in content, "Change 2 anchor not found"
assert content.count(old_2) == 1, f"Change 2 anchor not unique: {content.count(old_2)}"
content = content.replace(old_2, new_2)
print("OK change 2: Latent items subsection inserted into area card")

# ============================================================
# Change 3: Disabled submit button copy + variable rename
# ============================================================

old_3 = '''        <button disabled class="w-full py-3 px-4 bg-gray-300 text-gray-500 font-semibold rounded-lg cursor-not-allowed">
            Address all defects to submit ({{ total_addressed }} / {{ total_bfwd }})
        </button>'''

new_3 = '''        <button disabled class="w-full py-3 px-4 bg-gray-300 text-gray-500 font-semibold rounded-lg cursor-not-allowed">
            Address all items to submit ({{ total_addressed }} / {{ total_items }})
        </button>'''

assert old_3 in content, "Change 3 anchor not found"
assert content.count(old_3) == 1, f"Change 3 anchor not unique: {content.count(old_3)}"
content = content.replace(old_3, new_3)
print("OK change 3: disabled submit button copy updated")

# Sanity: no more total_bfwd references in this file
remaining = content.count('total_bfwd')
assert remaining == 0, f"total_bfwd still present in {PATH}: {remaining} occurrence(s)"
print("OK sanity: no total_bfwd references remain in desnag.html")

with open(PATH, 'w') as f:
    f.write(content)

print()
print("All 3 changes applied to", PATH)
