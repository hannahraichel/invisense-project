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

    # 3. Verify admin dashboard URL
    assert driver.current_url == "http://127.0.0.1:8000/admin-dashboard/"

    print("Admin dashboard URL verified")

    # 4. Verify page title
    assert driver.title == "Overview — InviSense"

    print("Page title verified")

    # 5. Verify main heading
    heading = driver.find_element(By.TAG_NAME, "h1")

    assert heading.text == "Overview"

    print("Dashboard heading verified")

    # 6. Verify important dashboard sections
    page_text = driver.find_element(By.TAG_NAME, "body").text

    assert "ACTIVE SESSIONS" in page_text
    assert "STUDENTS MAPPED" in page_text
    assert "PENDING ALERTS" in page_text
    assert "INVIGILATORS ON FILE" in page_text

    print("Dashboard statistics verified")

    # 7. Verify important navigation links
    assert driver.find_element(
        By.LINK_TEXT, "Setup Exam"
    ).is_displayed()

    assert driver.find_element(
        By.LINK_TEXT, "Upload Roster"
    ).is_displayed()

    assert driver.find_element(
        By.LINK_TEXT, "Staff"
    ).is_displayed()

    assert driver.find_element(
        By.LINK_TEXT, "Live Feed"
    ).is_displayed()

    print("Navigation links verified")

    print("\nADMIN DASHBOARD TEST PASSED")

    time.sleep(2)

finally:
    driver.quit()