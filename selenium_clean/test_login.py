from selenium import webdriver
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome()

try:
    driver.get("http://127.0.0.1:8000/login/")

    print("Login page opened")

    driver.find_element(By.ID, "username").send_keys("admin")
    driver.find_element(By.ID, "password").send_keys("adminpassword")

    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    time.sleep(2)

    print("Current URL:", driver.current_url)

    assert "/admin-dashboard/" in driver.current_url

    print("LOGIN TEST PASSED")

finally:
    driver.quit()