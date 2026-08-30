"""
Driver: tests Trend Tracker 'New This Week' section.

Steps:
  1. Confirm DB has data (no re-seed needed).
  2. Launch window offscreen.
  3. Navigate to Trend Tracker (index 4).
  4. Assert new entrants count label is updated.
  5. Assert table has rows with correct column values.
  6. Spot-check first and last rows.
  7. Screenshot.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)

# 1. Confirm DB state
from src.db.repository import get_new_entrants, get_all_ads
all_ads = get_all_ads()
print(f"[1] DB has {len(all_ads)} ad records.")
entrants = get_new_entrants(days_back=7)
print(f"    get_new_entrants(7) returns {len(entrants)} entrants.")
assert len(entrants) > 0, "No new entrants in DB — cannot test display."

# 2. Launch window
print("[2] Launching AdLensPKWindow...")
from src.desktop.main_window import AdLensPKWindow
win = AdLensPKWindow()
win.show()
app.processEvents()

# 3. Navigate to Trend Tracker (index 4)
print("[3] Navigating to Trend Tracker (index 4)...")
win._switch_page(4)
app.processEvents()
assert win.content_stack.currentIndex() == 4, "Failed to switch to Trend Tracker"
assert win.nav_buttons[4].isChecked(), "Trend Tracker nav button not checked"
print("    Navigation OK.")

# 4. Check count label
print("[4] Checking new entrants count label...")
count_text = win.new_entrants_count_label.text()
print(f"    Label: '{count_text}'")
assert "0" not in count_text or len(entrants) == 0, \
    f"Count label shows 0 but DB has {len(entrants)} entrants."
assert str(len(entrants)) in count_text, \
    f"Expected '{len(entrants)}' in label, got: '{count_text}'"
print("    Count label OK.")

# 5. Check table row count
print("[5] Checking table row count...")
row_count = win.new_entrants_table.rowCount()
print(f"    Table rows: {row_count}")
assert row_count == len(entrants), \
    f"Expected {len(entrants)} rows, got {row_count}"
print("    Row count OK.")

# 6. Spot-check columns on first and last rows
print("[6] Spot-checking row data...")
cols = ["Brand Name", "Industry", "First Seen", "Ads Found"]
for check_row in (0, row_count - 1):
    print(f"    Row {check_row}:")
    for col_idx, col_name in enumerate(cols):
        cell = win.new_entrants_table.item(check_row, col_idx)
        val = cell.text() if cell else "<empty>"
        print(f"      {col_name}: {val!r}")
        assert cell is not None and val.strip() != "", \
            f"Column '{col_name}' is empty at row {check_row}"
    # First Seen should look like a date (starts with 20)
    first_seen_val = win.new_entrants_table.item(check_row, 2).text()
    assert first_seen_val.startswith("20"), \
        f"First Seen '{first_seen_val}' doesn't look like a date"
    # Ads Found should be numeric
    ads_found_val = win.new_entrants_table.item(check_row, 3).text()
    assert ads_found_val.isdigit(), \
        f"Ads Found '{ads_found_val}' is not numeric"
print("    Column data OK.")

# 7. Screenshot
print("[7] Taking screenshot...")
shot_path = os.path.join(ROOT, "scripts", "trend_tracker_test.png")
win.grab().save(shot_path)
print(f"    Saved: {shot_path}")

print("\nAll Trend Tracker assertions passed.")
app.quit()
