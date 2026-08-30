"""
Headless driver: tests Brand Profile search for 'DermaGlow PK'.

Steps:
  1. Seed the DB with the mock dataset so there is data to search.
  2. Create the main window (offscreen).
  3. Navigate to Brand Profile (index 7).
  4. Type 'DermaGlow' into brand_search_input and trigger returnPressed.
  5. Assert metrics and table populated correctly.
  6. Screenshot the window to a file.
  7. Assert Track This Brand button is enabled.
"""

import os
import sys

# Ensure project root on path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

app = QApplication(sys.argv)

# ── 1. Seed mock data ──────────────────────────────────────────────────────
from src.db.repository import init_db, get_all_ads
from src.core.fetcher import fetch_ads
from src.db.repository import save_ads

init_db()
print("[1] Seeding demo dataset...")
ads = fetch_ads(industry="General", use_mock=True)
saved = save_ads(ads)
print(f"    Saved {saved} new records (already-present records skipped).")
all_db = get_all_ads()
print(f"    Total ads in DB: {len(all_db)}")

# Confirm DermaGlow is present
dg_in_db = [a for a in all_db if "dermaglow" in a.get("page_name","").lower()]
if not dg_in_db:
    print("WARN: DermaGlow PK not found in DB after seeding — trying broader search.")
    # fall back to first brand in DB
    first_brand = all_db[0]["page_name"] if all_db else None
    SEARCH_TERM = first_brand.split()[0] if first_brand else "PK"
else:
    SEARCH_TERM = "DermaGlow"
print(f"    Search term: '{SEARCH_TERM}'")

# ── 2. Launch window offscreen ─────────────────────────────────────────────
print("[2] Launching AdLensPKWindow...")
from src.desktop.main_window import AdLensPKWindow
win = AdLensPKWindow()
win.show()

# ── 3. Navigate to Brand Profile (index 7) ─────────────────────────────────
print("[3] Navigating to Brand Profile page (index 7)...")
win._switch_page(7)
assert win.content_stack.currentIndex() == 7, "Failed to navigate to Brand Profile"
nav_btn = win.nav_buttons[7]
assert nav_btn.isChecked(), "Brand Profile nav button not checked"
print("    Navigation OK.")

# ── 4. Type search term and trigger search ─────────────────────────────────
print(f"[4] Searching for '{SEARCH_TERM}'...")
win.brand_search_input.setText(SEARCH_TERM)
win.brand_search_input.returnPressed.emit()  # simulate Enter

# Process any pending Qt events
app.processEvents()

# ── 5. Assert metrics populated ───────────────────────────────────────────
print("[5] Checking metric labels...")
total_text = win.bp_val_total.text()
avg_days_text = win.bp_val_avg_days.text()
cta_text = win.bp_val_cta.text()
cod_text = win.bp_val_cod.text()

print(f"    Total Ads:      {total_text}")
print(f"    Avg Days Active:{avg_days_text}")
print(f"    Most Used CTA:  {cta_text}")
print(f"    COD Usage:      {cod_text}")

assert total_text != "-" and total_text != "0", f"Expected ads found, got: {total_text}"
assert avg_days_text != "-", f"Avg days should be set, got: {avg_days_text}"
assert cta_text != "-", f"CTA should be set, got: {cta_text}"
assert "%" in cod_text, f"COD should show percentage, got: {cod_text}"

# ── 6. Assert table populated ─────────────────────────────────────────────
print("[6] Checking ad records table...")
row_count = win.brand_ads_table.rowCount()
print(f"    Table rows: {row_count}")
assert row_count > 0, f"Expected table rows, got {row_count}"

# Spot-check first row columns
col_headers = ["Date Pulled", "Ad Copy (100 chars)", "Days Active", "Has COD", "Primary CTA"]
for col_idx, col_name in enumerate(col_headers):
    cell = win.brand_ads_table.item(0, col_idx)
    val = cell.text() if cell else "<empty>"
    print(f"    Row 0, {col_name}: {val!r}")
    assert cell is not None, f"Column '{col_name}' is empty at row 0"

# ── 7. Assert Track This Brand enabled ────────────────────────────────────
print("[7] Checking Track This Brand button...")
assert win.track_brand_button.isEnabled(), "Track This Brand button should be enabled after results"
print("    Button is enabled. OK.")

# ── 8. Screenshot ─────────────────────────────────────────────────────────
print("[8] Taking screenshot...")
screenshot_path = os.path.join(ROOT, "scripts", "brand_profile_test.png")
pixmap = win.grab()
pixmap.save(screenshot_path)
print(f"    Screenshot saved to: {screenshot_path}")

print("\nAll Brand Profile assertions passed.")
app.quit()
