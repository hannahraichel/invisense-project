from selenium import webdriver
from selenium.webdriver.common.by import By
import time

# Start Chrome
driver = webdriver.Chrome()

try:
    # Open InviSense login page
    driver.get("http://127.0.0.1:8000/login/")

    print("Opened login page")
    print("Current URL:", driver.current_url)

    # Find username field
    username = driver.find_element(By.ID, "username")
    username.send_keys("admin")

    # Find password field
    password = driver.find_element(By.ID, "password")
    password.send_keys("adminpassword")

    # Find and click Sign in button
    login_button = driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    )
    login_button.click()

    # Give Django time to redirect
    time.sleep(2)

    print("After login URL:", driver.current_url)

    # Check that login was successful
    assert "/admin-dashboard/" in driver.current_url

    print("LOGIN TEST PASSED")

finally:
    time.sleep(2)
    driver.quit()