import sys

def replace_in_file(filepath, old, new, label):
    with open(filepath, 'r') as f:
        content = f.read()
    count = content.count(old)
    if count == 0:
        print(f"  FAIL: [{label}] old string not found in {filepath}")
        sys.exit(1)
    if count > 1:
        print(f"  FAIL: [{label}] old string found {count} times (expected 1)")
        sys.exit(1)
    content = content.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  OK: [{label}] {filepath}")

print("=== Applying ended display ===\n")

replace_in_file(
    'app/templates/batches/live_monitor_data.html',
    """            {% if batch_started_hhmm %}
            <div class="elapsed-started">Started {{ batch_started_hhmm }}</div>
            {% endif %}""",
    """            {% if batch_started_hhmm %}
            <div class="elapsed-started">Started {{ batch_started_hhmm }}</div>
            {% endif %}
            {% if batch_ended_hhmm %}
            <div class="elapsed-started">Ended {{ batch_ended_hhmm }}</div>
            {% endif %}""",
    'ended-display'
)

print("\n=== DONE ===")
