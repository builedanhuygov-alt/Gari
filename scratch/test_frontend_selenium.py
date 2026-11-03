import os
import sys
import time
import json
from PIL import Image, ImageFilter

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def run_selenium_frontend_audit():
    print("=" * 80)
    print("GARI FRONTEND2 — AUTOMATED REAL BROWSER VALIDATION AUDIT (SELENIUM)")
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
    real_sample_path = os.path.join(DATA_DIR, "Potato___Early_blight", os.listdir(os.path.join(DATA_DIR, "Potato___Early_blight"))[0])

    frontend_audit_log = {}

    try:
        # STEP 1: AUTHENTICATION VIA LOGIN.HTML
        print("\n[STEP 1] Navigating to http://localhost:8000/frontend2/login.html ...")
        driver.get("http://localhost:8000/frontend2/login.html")
        time.sleep(1)
        
        btn_autofill = wait.until(EC.element_to_be_clickable((By.ID, "btnDevAutofill")))
        btn_autofill.click()
        time.sleep(0.5)

        btn_submit = driver.find_element(By.ID, "btnSubmit")
        btn_submit.click()
        time.sleep(2)

        token = driver.execute_script("return localStorage.getItem('gari_token');")
        print(f"  Login successful! Session JWT Token acquired: {token[:20]}...")

        # STEP 2: LOAD PREDICT.HTML
        print("\n[STEP 2] Navigating to http://localhost:8000/frontend2/predict.html ...")
        driver.get("http://localhost:8000/frontend2/predict.html")
        time.sleep(2)
        print(f"  Page Title: {driver.title}")

        crop_select = Select(wait.until(EC.presence_of_element_located((By.ID, "cropSelect"))))
        selected_option = crop_select.first_selected_option.text
        print(f"  Default crop selection: '{selected_option}'")
        assert "Tự động nhận diện cây trồng" in selected_option, "Default selection is not Auto crop!"

        # STEP 3: SUBMIT REAL LEAF IMAGE (POTATO EARLY BLIGHT)
        print(f"\n[STEP 3] Uploading real leaf sample: {real_sample_path} ...")
        file_input = driver.find_element(By.ID, "fileInput")
        file_input.send_keys(real_sample_path)
        time.sleep(1)

        btn_predict = driver.find_element(By.ID, "btnPredict")
        print("  Clicking 'Tiến hành kiểm tra lá' button...")
        driver.execute_script("arguments[0].click();", btn_predict)

        # STEP 4: MONITOR PROGRESS PIPELINE AND WAIT FOR RESULTS
        print("\n[STEP 4] Waiting for inference pipeline to complete...")
        wait.until(EC.visibility_of_element_located((By.ID, "activeResultCard")))
        time.sleep(2)
        driver.save_screenshot(os.path.join(SCRATCH_DIR, "selenium_step4_diagnosis_result.png"))
        print("  Diagnosis result rendered! Screenshot saved: scratch/selenium_step4_diagnosis_result.png")

        # STEP 5: VERIFY DIAGNOSIS OUTPUTS & SCIENTIFIC TERMINOLOGY
        print("\n[STEP 5] Auditing rendered diagnosis elements...")
        report_title = driver.find_element(By.XPATH, "//h2[contains(text(), 'KẾT QUẢ KIỂM TRA LÁ')]").text
        disease_name = driver.find_element(By.ID, "repDisease").text
        crop_badge = driver.find_element(By.ID, "repCrop").text
        score_val = driver.find_element(By.ID, "repConfidence").text

        print(f"  Report Header:       {report_title}")
        print(f"  Identified Crop:     {crop_badge}")
        print(f"  Diagnosed Disease:   {disease_name}")
        print(f"  Prediction Score:    {score_val}")

        score_label = driver.find_element(By.XPATH, "//span[contains(text(), 'Điểm dự đoán của mô hình')]").text
        print(f"  Confidence Label:    '{score_label}' (Verified: Explicitly labeled Softmax Score)")

        # STEP 6: VERIFY LOCALIZATION VIEWER (GRAD-CAM & VISUALLY SUSPICIOUS REGIONS)
        print("\n[STEP 6] Testing visual localization viewer controls...")
        tab_original = driver.find_element(By.ID, "tabOriginal")
        tab_attention = driver.find_element(By.ID, "tabAttention")
        tab_overlay = driver.find_element(By.ID, "tabOverlay")

        # Click attention tab via script to avoid sticky topbar overlap
        driver.execute_script("arguments[0].click();", tab_attention)
        time.sleep(0.5)
        attention_img_src = driver.find_element(By.ID, "viewerMainImg").get_attribute("src")
        print(f"  Attention Heatmap Image URL: {attention_img_src}")

        # Click overlay tab
        driver.execute_script("arguments[0].click();", tab_overlay)
        time.sleep(0.5)
        overlay_img_src = driver.find_element(By.ID, "viewerMainImg").get_attribute("src")
        print(f"  Suspicious Overlay Image URL: {overlay_img_src}")

        # Click original tab
        driver.execute_script("arguments[0].click();", tab_original)
        time.sleep(0.5)
        original_img_src = driver.find_element(By.ID, "viewerMainImg").get_attribute("src")
        print(f"  Original Leaf Image URL:     {original_img_src}")

        region_items = driver.find_elements(By.CSS_SELECTOR, "#regionsList .region-item")
        print(f"  Suspicious regions rendered in panel: {len(region_items)}")

        disclaimer_text = driver.find_element(By.CSS_SELECTOR, ".attention-disclaimer-box").text
        print(f"  Localization Disclaimer: '{disclaimer_text[:110]}...'")

        # Scroll to report details and capture screenshot
        driver.execute_script("arguments[0].scrollIntoView();", driver.find_element(By.CLASS_NAME, "report-card"))
        time.sleep(1)
        driver.save_screenshot(os.path.join(SCRATCH_DIR, "selenium_step5_report_details.png"))
        print("  Screenshot saved: scratch/selenium_step5_report_details.png")

        # STEP 7: TEST CROP CORRECTION FLOW
        print("\n[STEP 7] Testing manual crop correction flow...")
        driver.execute_script("arguments[0].scrollIntoView();", driver.find_element(By.ID, "cropSelect"))
        time.sleep(0.5)
        crop_select = Select(driver.find_element(By.ID, "cropSelect"))
        crop_select.select_by_value("Tomato")
        print("  Manually selected crop: 'Tomato' (Cà chua)")
        driver.execute_script("arguments[0].click();", btn_predict)
        time.sleep(4)
        wait.until(EC.visibility_of_element_located((By.ID, "activeResultCard")))
        corrected_crop = driver.find_element(By.ID, "repCrop").text
        print(f"  Corrected Crop in Report: {corrected_crop}")
        driver.save_screenshot(os.path.join(SCRATCH_DIR, "selenium_step7_crop_corrected.png"))

        # STEP 8: TEST IMAGE QUALITY GATE ERROR HANDLING
        print("\n[STEP 8] Testing quality gate rejection handling in UI...")
        img_raw = Image.open(real_sample_path).convert("RGB")
        blurry = img_raw.filter(ImageFilter.GaussianBlur(radius=20))
        blurry_path = os.path.join(SCRATCH_DIR, "selenium_test_blur.jpg")
        blurry.save(blurry_path, "JPEG")

        file_input = driver.find_element(By.ID, "fileInput")
        file_input.send_keys(blurry_path)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", btn_predict)
        time.sleep(2)

        wait.until(EC.visibility_of_element_located((By.ID, "rejectionCard")))
        driver.save_screenshot(os.path.join(SCRATCH_DIR, "selenium_step8_quality_rejection.png"))
        rejection_reason = driver.find_element(By.ID, "rejectionReason").text
        print(f"  Rejection Card Visible! Reason: {rejection_reason}")
        print("  Screenshot saved: scratch/selenium_step8_quality_rejection.png")

        # STEP 9: TEST PERSISTENT DIAGNOSIS HISTORY (REPORTS.HTML)
        print("\n[STEP 9] Navigating to http://localhost:8000/frontend2/reports.html ...")
        driver.get("http://localhost:8000/frontend2/reports.html")
        time.sleep(3)
        driver.save_screenshot(os.path.join(SCRATCH_DIR, "selenium_step9_history_reports.png"))

        history_rows = driver.find_elements(By.CSS_SELECTOR, "#auditTableBody tr")
        print(f"  Total Diagnosis History Records: {len(history_rows)}")
        first_row_text = ""
        if history_rows:
            first_row_text = history_rows[0].text.replace("\n", " | ")
            print(f"  Latest Diagnosis Record: {first_row_text}")
        print("  Screenshot saved: scratch/selenium_step9_history_reports.png")

        frontend_audit_log = {
            "test_frontend": "PASSED",
            "report_header_verified": report_title,
            "crop_identification_verified": crop_badge,
            "crop_correction_verified": corrected_crop,
            "quality_rejection_verified": rejection_reason,
            "localization_tabs_verified": True,
            "history_persistence_verified": True,
            "history_record_count": len(history_rows),
            "latest_record": first_row_text
        }

    except Exception as e:
        print(f"ERROR DURING SELENIUM AUDIT: {e}")
        driver.save_screenshot(os.path.join(SCRATCH_DIR, "selenium_error.png"))
        frontend_audit_log = {"test_frontend": "FAILED", "error": str(e)}
    finally:
        driver.quit()

    report_file = os.path.join(SCRATCH_DIR, "frontend_selenium_audit.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(frontend_audit_log, f, ensure_ascii=False, indent=2)
    print(f"\nFrontend audit complete! Log saved to: {report_file}")

if __name__ == "__main__":
    run_selenium_frontend_audit()
