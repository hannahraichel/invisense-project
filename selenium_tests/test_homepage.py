from selenium import webdriver
import time

driver = webdriver.Chrome()

driver.get("http://127.0.0.1:8000/")

print("Page title:", driver.title)
print("Current URL:", driver.current_url)

time.sleep(3)

driver.quit()

print("Selenium test completed successfully!")