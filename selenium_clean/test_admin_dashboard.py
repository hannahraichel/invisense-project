from selenium import webdriver
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome()

try:
    # 1. Open login page
    driver.get("http://127.0.0.1:8000/login/")

    print("Opened login page")

    # 2. Login as admin
    driver.find_element(By.ID, "username").send_keys("admin")
    driver.find_element(By.ID, "password").send_keys("adminpassword")

    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    time.sleep(2)

    # 3. Verify dashboard URL
    assert driver.current_url == "http://127.0.0.1:8000/admin-dashboard/"

    print("Admin dashboard URL verified")

    # 4. Verify page title
    assert driver.title == "Overview — InviSense"

    print("Page title verified")

    # 5. Verify main heading
    heading = driver.find_element(By.TAG_NAME, "h1")
    assert heading.text == "Overview"

    print("Dashboard heading verified")

    # 6. Get dashboard text
    page_text = driver.find_element(By.TAG_NAME, "body").text

    print("\n--- Dashboard Text ---")
    print(page_text)
    print("----------------------\n")

    # 7. Verify actual dashboard labels
    assert "ACTIVE SESSIONS" in page_text
    assert "STUDENTS MAPPED" in page_text
    assert "PENDING ALERTS" in page_text
    assert "INVIGILATORS ON FILE" in page_text

    print("Dashboard statistics verified")

    # 8. Verify navigation links
    assert driver.find_element(
        By.PARTIAL_LINK_TEXT, "Exam Periods"
    ).is_displayed()

    assert driver.find_element(
        By.PARTIAL_LINK_TEXT, "Halls Manager"
    ).is_displayed()

    assert driver.find_element(
        By.PARTIAL_LINK_TEXT, "Staff"
    ).is_displayed()

    assert driver.find_element(
        By.PARTIAL_LINK_TEXT, "Live Feed"
    ).is_displayed()

    print("Navigation links verified")

    print("\nADMIN DASHBOARD TEST PASSED")

finally:
    driver.quit()