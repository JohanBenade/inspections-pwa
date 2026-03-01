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

print("=== Applying clock auto-stop fix ===\n")

# EDIT 1: batches.py - Add batch_ended to live monitor data
replace_in_file(
    'app/routes/batches.py',
    "        'batch_started_hhmm': _format_local_hhmm(batch_started),",
    "        'batch_started_hhmm': _format_local_hhmm(batch_started),\n        'batch_ended': batch.get('submitted_at') or '',\n        'batch_ended_hhmm': _format_local_hhmm(batch.get('submitted_at')) or '',",
    'add-batch-ended'
)

# EDIT 2: live_monitor.html - JS uses batch_ended when set
replace_in_file(
    'app/templates/batches/live_monitor.html',
    """var batchStartedStr = '{{ batch_started|default("", true) }}';
function updateBatchElapsed() {
    var el = document.getElementById('batch-elapsed');
    if (!el || !batchStartedStr) return;
    var started = new Date(batchStartedStr);
    if (isNaN(started.getTime())) return;
    var diff = Math.floor((Date.now() - started.getTime()) / 1000);""",
    """var batchStartedStr = '{{ batch_started|default("", true) }}';
var batchEndedStr = '{{ batch_ended|default("", true) }}';
function updateBatchElapsed() {
    var el = document.getElementById('batch-elapsed');
    if (!el || !batchStartedStr) return;
    var started = new Date(batchStartedStr);
    if (isNaN(started.getTime())) return;
    var endTime = Date.now();
    if (batchEndedStr) {
        var ended = new Date(batchEndedStr);
        if (!isNaN(ended.getTime())) endTime = ended.getTime();
    }
    var diff = Math.floor((endTime - started.getTime()) / 1000);""",
    'js-clock-stop'
)

print("\n=== ALL EDITS APPLIED ===")
print("Next: git add -A && git commit -m 'Live monitor: auto-stop elapsed clock when batch submitted' && git push")
