from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
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

    time.sleep(1)

    # Open Setup Exam
    driver.get("http://127.0.0.1:8000/setup-session/")

    time.sleep(1)

    print("Setup Exam page opened")

    # Date
    date_field = driver.find_element(By.ID, "date")

    driver.execute_script(
        """
        arguments[0].value = '2026-09-03';
        arguments[0].dispatchEvent(
            new Event('input', {bubbles: true})
        );
        arguments[0].dispatchEvent(
            new Event('change', {bubbles: true})
        );
        """,
        date_field
    )

    # Shift
    shift = Select(driver.find_element(By.ID, "shift"))
    shift.select_by_visible_text("Morning")

    # Hall number
    hall = driver.find_element(By.NAME, "hall_number")
    hall.clear()
    hall.send_keys("999")

    # Capacity
    capacity = driver.find_element(By.NAME, "capacity")
    capacity.clear()
    capacity.send_keys("30")

    # Seats per row
    seats = driver.find_element(By.NAME, "seats_per_row")
    seats.clear()
    seats.send_keys("6")

    print("Exam form filled")

    # Verify values
    assert date_field.get_attribute("value") == "2026-09-03"
    assert shift.first_selected_option.text == "Morning"
    assert hall.get_attribute("value") == "999"
    assert capacity.get_attribute("value") == "30"
    assert seats.get_attribute("value") == "6"

    print("Form values verified")

    # Submit
    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    time.sleep(2)

    page_text = driver.find_element(By.TAG_NAME, "body").text

    print("\n--- Result ---")
    print(page_text)
    print("--------------")

    assert "Session created" in page_text

    print("\nSETUP EXAM TEST PASSED")

finally:
    driver.quit()