from selenium import webdriver
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome()

try:
    driver.get("http://127.0.0.1:8000/login/")

    print("Opened login page")

    # Enter incorrect credentials
    driver.find_element(By.ID, "username").send_keys("wronguser")
    driver.find_element(By.ID, "password").send_keys("wrongpassword")

    # Click Sign in
    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    time.sleep(2)

    print("Current URL:", driver.current_url)

    # The user should NOT reach the admin dashboard
    assert "/admin-dashboard/" not in driver.current_url

    print("INVALID LOGIN TEST PASSED")

finally:
    time.sleep(2)
    driver.quit()