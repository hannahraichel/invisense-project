from selenium import webdriver
from selenium.webdriver.common.by import By
import time

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

    time.sleep(2)

    # Open Setup Exam
    driver.get("http://127.0.0.1:8000/setup-session/")

    time.sleep(2)

    print("\n========== SETUP EXAM PAGE ==========")
    print("URL:", driver.current_url)
    print("Title:", driver.title)

    print("\n========== PAGE TEXT ==========")
    print(driver.find_element(By.TAG_NAME, "body").text)

    print("\n========== FORM FIELDS ==========")

    # Input fields
    inputs = driver.find_elements(By.TAG_NAME, "input")

    for element in inputs:
        print(
            "INPUT:",
            "type=", element.get_attribute("type"),
            "name=", element.get_attribute("name"),
            "id=", element.get_attribute("id"),
            "placeholder=", element.get_attribute("placeholder")
        )

    # Select fields
    selects = driver.find_elements(By.TAG_NAME, "select")

    for element in selects:
        print(
            "SELECT:",
            "name=", element.get_attribute("name"),
            "id=", element.get_attribute("id")
        )

    # Textareas
    textareas = driver.find_elements(By.TAG_NAME, "textarea")

    for element in textareas:
        print(
            "TEXTAREA:",
            "name=", element.get_attribute("name"),
            "id=", element.get_attribute("id")
        )

    # Buttons
    print("\n========== BUTTONS ==========")

    buttons = driver.find_elements(By.TAG_NAME, "button")

    for button in buttons:
        print(
            "BUTTON:",
            button.text,
            "type=", button.get_attribute("type")
        )

    print("\n========== LINKS ==========")

    links = driver.find_elements(By.TAG_NAME, "a")

    for link in links:
        text = link.text.strip()

        if text:
            print(
                text,
                "->",
                link.get_attribute("href")
            )

    time.sleep(3)

finally:
    driver.quit()