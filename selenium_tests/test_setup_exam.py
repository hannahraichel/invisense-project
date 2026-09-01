from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import time

driver = webdriver.Chrome()

try:
    # -----------------------------------
    # 1. Open Login Page
    # -----------------------------------
    driver.get("http://127.0.0.1:8000/login/")

    print("Opened login page")

    # Login as Admin
    driver.find_element(By.ID, "username").send_keys("admin")
    driver.find_element(By.ID, "password").send_keys("adminpassword")

    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    time.sleep(2)

    print("Admin login successful")

    # -----------------------------------
    # 2. Open Setup Exam
    # -----------------------------------
    driver.get("http://127.0.0.1:8000/setup-session/")

    time.sleep(1)

    print("Setup Exam page opened")

    # -----------------------------------
    # 3. Enter Exam Date
    # -----------------------------------

    date_field = driver.find_element(By.ID, "date")

    # Set HTML date input directly as YYYY-MM-DD
    driver.execute_script(
        """
        arguments[0].value = '2026-09-02';
        arguments[0].dispatchEvent(
            new Event('input', {bubbles: true})
        );
        arguments[0].dispatchEvent(
            new Event('change', {bubbles: true})
        );
        """,
        date_field
    )

    # -----------------------------------
    # 4. Select Shift
    # -----------------------------------

    shift = Select(
        driver.find_element(By.ID, "shift")
    )

    shift.select_by_visible_text("Morning")

    # -----------------------------------
    # 5. Enter Hall Number
    # -----------------------------------

    hall = driver.find_element(
        By.NAME, "hall_number"
    )

    hall.clear()
    hall.send_keys("999")

    # -----------------------------------
    # 6. Enter Capacity
    # -----------------------------------

    capacity = driver.find_element(
        By.NAME, "capacity"
    )

    capacity.clear()
    capacity.send_keys("30")

    # -----------------------------------
    # 7. Enter Seats Per Row
    # -----------------------------------

    seats = driver.find_element(
        By.NAME, "seats_per_row"
    )

    seats.clear()
    seats.send_keys("6")

    time.sleep(1)

    # -----------------------------------
    # 8. Read Actual Form Values
    # -----------------------------------

    actual_date = date_field.get_attribute("value")
    actual_shift = shift.first_selected_option.text
    actual_hall = hall.get_attribute("value")
    actual_capacity = capacity.get_attribute("value")
    actual_seats = seats.get_attribute("value")

    print("\n========== FORM VALUES ==========")

    print("Date:", actual_date)
    print("Shift:", actual_shift)
    print("Hall:", actual_hall)
    print("Capacity:", actual_capacity)
    print("Seats per row:", actual_seats)

    # -----------------------------------
    # 9. Verify Values
    # -----------------------------------

    assert actual_date == "2026-09-02", \
        f"Wrong date: {actual_date}"

    assert actual_shift == "Morning", \
        f"Wrong shift: {actual_shift}"

    assert actual_hall == "999", \
        f"Wrong hall: {actual_hall}"

    assert actual_capacity == "30", \
        f"Wrong capacity: {actual_capacity}"

    assert actual_seats == "6", \
        f"Wrong seats per row: {actual_seats}"

    print("\nFORM VALUES VERIFIED")

    # -----------------------------------
    # 10. Submit Form
    # -----------------------------------

    driver.find_element(
        By.CSS_SELECTOR,
        "button[type='submit']"
    ).click()

    print("Create session button clicked")

    time.sleep(2)

    # -----------------------------------
    # 11. Verify Session Creation
    # -----------------------------------

    print("\nFinal URL:", driver.current_url)

    page_text = driver.find_element(
        By.TAG_NAME,
        "body"
    ).text

    print("\n========== RESULT ==========")
    print(page_text)

    assert "Session created with 1 hall(s)." in page_text

    print("\nSETUP EXAM TEST PASSED")

    time.sleep(3)

finally:
    driver.quit()