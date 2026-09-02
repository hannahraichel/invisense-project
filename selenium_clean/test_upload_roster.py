from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import time
import os

driver = webdriver.Chrome()

try:
    # Login
    driver.get("http://127.0.0.1:8000/login/")

    driver.find_element(By.ID, "username").send_keys("admin")
    driver.find_element(By.ID, "password").send_keys("adminpassword")

    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    time.sleep(1)

    print("Admin login successful")

    # Open Upload Roster page
    driver.get("http://127.0.0.1:8000/upload-mapping/")

    time.sleep(1)

    print("Upload Roster page opened")

    # Select exam session
    session = Select(
        driver.find_element(By.ID, "session_id")
    )

    assert len(session.options) > 0

    session.select_by_index(0)

    print("Exam session selected")

    # Upload CSV
    csv_path = os.path.abspath("test_students.csv")

    file_input = driver.find_element(
        By.ID,
        "mapping_file"
    )

    file_input.send_keys(csv_path)

    print("CSV file selected")

    # Submit
    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    time.sleep(2)

    page_text = driver.find_element(
        By.TAG_NAME,
        "body"
    ).text

    print("\n--- Upload Result ---")
    print(page_text)
    print("---------------------")

    # Verify successful import
    assert "Imported" in page_text
    assert "student(s)" in page_text

    print("\nUPLOAD ROSTER TEST PASSED")

finally:
    driver.quit()