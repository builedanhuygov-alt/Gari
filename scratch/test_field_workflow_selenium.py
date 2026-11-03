import os
import sys
import time
import json
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def run_field_workflow_test():
    print("=" * 80)
    print("TESTING VIETNAM FIELD COLLECTION & READINESS WORKFLOW (SELENIUM)")
    print("=" * 80)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1600,1200")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 35)

    SCRATCH_DIR = r"D:\leaf-diseases-detector-main\scratch"
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    DATA_DIR = r"D:\leaf-diseases-detector-main\data\organized\PlantVillage"
    real_sample = os.path.join(DATA_DIR, "Potato___Early_blight", os.listdir(os.path.join(DATA_DIR, "Potato___Early_blight"))[0])

    try:
        # STEP 1: AUTHENTICATION
        print("\n[STEP 1] Authenticating at http://localhost:8000/frontend2/login.html ...")
        driver.get("http://localhost:8000/frontend2/login.html")
        time.sleep(1)
        wait.until(EC.element_to_be_clickable((By.ID, "btnDevAutofill"))).click()
        time.sleep(0.5)
        driver.find_element(By.ID, "btnSubmit").click()
        time.sleep(2)
        print("  Authentication successful!")

        # STEP 2: LOAD COLLECT.HTML
        print("\n[STEP 2] Navigating to http://localhost:8000/frontend2/collect.html ...")
        driver.get("http://localhost:8000/frontend2/collect.html")
        time.sleep(2)
        driver.save_screenshot(os.path.join(SCRATCH_DIR, "selenium_field_step2_collect_page.png"))
        print(f"  Page Title: {driver.title}")

        # Verify 8 key crop readiness cards
        readiness_cards = driver.find_elements(By.CSS_SELECTOR, "#cropReadinessGrid .readiness-card")
        print(f"  Readiness cards loaded: {len(readiness_cards)} (Expected 8)")
        assert len(readiness_cards) >= 8, "Expected at least 8 key crop readiness cards!"

        # STEP 3: SUBMIT FIELD SAMPLE (COFFEE RUST IN DAK LAK)
        print("\n[STEP 3] Testing field sample ingestion...")
        file_input = driver.find_element(By.ID, "fieldFileInput")
        file_input.send_keys(real_sample)
        time.sleep(1)

        # Select Coffee
        crop_sel = Select(driver.find_element(By.ID, "colCrop"))
        crop_sel.select_by_value("Coffee")
        print("  Selected crop: 'Coffee' (Cà phê)")

        # Mark abnormal
        driver.find_element(By.CSS_SELECTOR, "input[name='healthStatus'][value='abnormal']").click()
        time.sleep(0.2)

        # Enter disease
        disease_input = driver.find_element(By.ID, "colDisease")
        disease_input.clear()
        disease_input.send_keys("Bệnh gỉ sắt cà phê (Hemileia vastatrix)")

        # Select province & district
        prov_sel = Select(driver.find_element(By.ID, "colProvince"))
        prov_sel.select_by_value("Đắk Lắk")
        dist_input = driver.find_element(By.ID, "colDistrict")
        dist_input.clear()
        dist_input.send_keys("Cư M'gar")

        notes_input = driver.find_element(By.ID, "colNotes")
        notes_input.clear()
        notes_input.send_keys("Thu thập tại nông trường cà phê Cư M'gar, mặt dưới lá có phấn vàng cam.")

        # Click submit
        btn_submit = driver.find_element(By.ID, "btnSubmitCollect")
        driver.execute_script("arguments[0].click();", btn_submit)
        time.sleep(3)

        driver.save_screenshot(os.path.join(SCRATCH_DIR, "selenium_field_step3_uploaded.png"))
        print("  Sample submitted! Screenshot saved: scratch/selenium_field_step3_uploaded.png")

        # STEP 4: VERIFY RECORD IN REVIEW TABLE
        print("\n[STEP 4] Verifying newly recorded field sample in table...")
        rows = driver.find_elements(By.CSS_SELECTOR, "#fieldTableBody tr")
        print(f"  Total records in table: {len(rows)}")
        first_row_text = rows[0].text
        print(f"  First Record: {first_row_text}")
        assert "Cà phê" in first_row_text, "Newly uploaded Coffee record not found in table!"

        # STEP 5: TEST REVIEWER VERIFICATION WORKFLOW (MODAL)
        print("\n[STEP 5] Testing Agronomist Reviewer Verification Modal...")
        review_btn = rows[0].find_element(By.CSS_SELECTOR, ".btn-review")
        driver.execute_script("arguments[0].click();", review_btn)
        time.sleep(1)

        wait.until(EC.visibility_of_element_located((By.ID, "reviewModal")))
        driver.save_screenshot(os.path.join(SCRATCH_DIR, "selenium_field_step5_review_modal.png"))

        # Select verified
        status_sel = Select(driver.find_element(By.ID, "revStatus"))
        status_sel.select_by_value("verified")

        notes_rev = driver.find_element(By.ID, "revNotes")
        notes_rev.clear()
        notes_rev.send_keys("Đã xác nhận lâm sàng: Triệu chứng nấm gỉ sắt Hemileia vastatrix chuẩn thực địa.")

        btn_save_rev = driver.find_element(By.ID, "btnSaveReview")
        driver.execute_script("arguments[0].click();", btn_save_rev)
        time.sleep(2)

        driver.save_screenshot(os.path.join(SCRATCH_DIR, "selenium_field_step5_verified_badge.png"))
        updated_first_row = driver.find_elements(By.CSS_SELECTOR, "#fieldTableBody tr")[0].text
        print(f"  Updated row after agronomist verification: {updated_first_row}")
        assert "Đã xác thực" in updated_first_row, "Status badge was not updated to Đã xác thực!"

        # STEP 6: VERIFY PREDICT.HTML ENHANCEMENTS
        print("\n[STEP 6] Testing frontend2/predict.html UX enhancements...")
        driver.get("http://localhost:8000/frontend2/predict.html")
        time.sleep(2)
        driver.save_screenshot(os.path.join(SCRATCH_DIR, "selenium_field_step6_predict_ux.png"))

        # Verify capture view pills
        view_pills = driver.find_elements(By.CSS_SELECTOR, "#predictViewPills .view-pill-btn")
        print(f"  Capture view options found: {len(view_pills)} (Expected 4)")
        assert len(view_pills) == 4, "Expected 4 capture view options in predict.html!"

        # Verify Unknown crop option
        crop_sel = Select(driver.find_element(By.ID, "cropSelect"))
        has_unknown = any("Tôi chưa biết cây gì" in opt.text for opt in crop_sel.options)
        print(f"  'Tôi chưa biết cây gì' option present: {has_unknown}")
        assert has_unknown, "Missing 'Tôi chưa biết cây gì' option!"

        print("\nALL FIELD WORKFLOW TESTS COMPLETED SUCCESSFULLY!")

    except Exception as e:
        print(f"ERROR: {e}")
        driver.save_screenshot(os.path.join(SCRATCH_DIR, "selenium_field_error.png"))
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    run_field_workflow_test()
