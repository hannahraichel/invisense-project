from selenium import webdriver
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome()

try:
    # Open login page
    driver.get("http://127.0.0.1:8000/login/")

    print("Login page opened")

    # Login as invigilator
    driver.find_element(By.ID, "username").send_keys("invigilator1")
    driver.find_element(By.ID, "password").send_keys("invpassword")

    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    time.sleep(2)

    print("Current URL:", driver.current_url)

    # Verify login did not remain on login page
    assert "/login/" not in driver.current_url

    # Verify page loaded successfully
    page_text = driver.find_element(
        By.TAG_NAME,
        "body"
    ).text

    print("\n--- Invigilator Page ---")
    print(page_text)
    print("-----------------------")

    assert "InviSense" in page_text

    print("\nINVIGILATOR LOGIN TEST PASSED")

finally:
    driver.quit()