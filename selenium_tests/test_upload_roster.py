from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import time
import csv
import os

# -----------------------------------
# Create test CSV file
# -----------------------------------

csv_file = os.path.abspath("test_roster.csv")

students = [
    ["roll_number", "name", "subject_code"],
    ["TEST001", "Test Student One", "MCA"],
    ["TEST002", "Test Student Two", "MCA"],
]

with open(csv_file, "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(students)

print("Test CSV created:", csv_file)

# -----------------------------------
# Start Chrome
# -----------------------------------

driver = webdriver.Chrome()

try:
    # -----------------------------------
    # 1. Login
    # -----------------------------------

    driver.get("http://127.0.0.1:8000/login/")

    driver.find_element(By.ID, "username").send_keys("admin")
    driver.find_element(By.ID, "password").send_keys("adminpassword")

    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    time.sleep(2)

    print("Admin login successful")

    # -----------------------------------
    # 2. Open Upload Roster
    # -----------------------------------

    driver.get("http://127.0.0.1:8000/upload-mapping/")

    time.sleep(1)

    print("Upload Roster page opened")

    # -----------------------------------
    # 3. Select an active exam session
    # -----------------------------------

    session_select = Select(
        driver.find_element(By.ID, "session_id")
    )

    # Select the first available active session
    session_select.select_by_index(0)

    selected_session = session_select.first_selected_option.text

    print("Selected session:", selected_session)

    # -----------------------------------
    # 4. Upload CSV
    # -----------------------------------

    file_input = driver.find_element(
        By.ID,
        "mapping_file"
    )

    file_input.send_keys(csv_file)

    print("CSV file selected")

    # -----------------------------------
    # 5. Click Upload
    # -----------------------------------

    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    print("Upload button clicked")

    time.sleep(2)

    # -----------------------------------
    # 6. Check result
    # -----------------------------------

    page_text = driver.find_element(
        By.TAG_NAME,
        "body"
    ).text

    print("\n========== RESULT ==========")
    print(page_text)

    # -----------------------------------
    # 7. Verify students imported
    # -----------------------------------

    assert "Imported 2 student(s)" in page_text

    print("\nUPLOAD ROSTER TEST PASSED")

    time.sleep(3)

finally:
    driver.quit()

    # Remove temporary CSV
    if os.path.exists(csv_file):
        os.remove(csv_file)