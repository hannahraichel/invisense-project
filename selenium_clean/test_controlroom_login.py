from selenium import webdriver
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome()

try:
    driver.get("http://127.0.0.1:8000/login/")

    print("Login page opened")

    # Login as Control Room user
    driver.find_element(By.ID, "username").send_keys("controlroom")
    driver.find_element(By.ID, "password").send_keys("crpassword")

    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    time.sleep(2)

    print("Current URL:", driver.current_url)

    # Login should succeed
    assert "/login/" not in driver.current_url

    page_text = driver.find_element(
        By.TAG_NAME,
        "body"
    ).text

    print("\n--- Control Room Page ---")
    print(page_text)
    print("------------------------")

    assert "InviSense" in page_text

    print("\nCONTROL ROOM LOGIN TEST PASSED")

finally:
    driver.quit()