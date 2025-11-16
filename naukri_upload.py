#!/usr/bin/env python3
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import chromedriver_autoinstaller

def make_driver():
    chromedriver_autoinstaller.install()

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--remote-debugging-port=9222")

    service = Service()
    return webdriver.Chrome(service=service, options=opts)

def upload():
    USER = os.getenv("NAUKRI_USER")
    PASS = os.getenv("NAUKRI_PASS")
    PROFILE_URL = os.getenv("NAUKRI_PROFILE_URL")
    RESUME_PATH = os.getenv("RESUME_PATH")

    if not USER or not PASS or not PROFILE_URL or not RESUME_PATH:
        raise Exception("Missing required environment variables!")

    driver = make_driver()
    driver.get("https://www.naukri.com/nlogin/login")

    wait = WebDriverWait(driver, 20)

    # Login
    wait.until(EC.presence_of_element_located((By.ID, "usernameField"))).send_keys(USER)
    wait.until(EC.presence_of_element_located((By.ID, "passwordField"))).send_keys(PASS)
    wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Login')]"))).click()

    time.sleep(5)

    # Open profile
    driver.get(PROFILE_URL)
    time.sleep(5)

    # Upload resume
    upload_input = wait.until(EC.presence_of_element_located(
        (By.XPATH, "//input[@type='file' and @id='attachCV']")
    ))

    upload_input.send_keys(RESUME_PATH)
    time.sleep(5)

    driver.quit()

if __name__ == "__main__":
    upload()
