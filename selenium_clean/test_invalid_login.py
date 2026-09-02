from selenium import webdriver
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome()

try:
    driver.get("http://127.0.0.1:8000/login/")

    driver.find_element(By.ID, "username").send_keys("admin")
    driver.find_element(By.ID, "password").send_keys("wrongpassword")

    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    time.sleep(1)

    page_text = driver.find_element(By.TAG_NAME, "body").text

    assert "Invalid username or password." in page_text
    assert "/login/" in driver.current_url

    print("INVALID LOGIN TEST PASSED")

finally:
    driver.quit()