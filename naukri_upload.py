# naukri_upload.py
# Best-effort Selenium script to log into Naukri and upload resume.
# Notes:
#  - If Naukri shows a captcha this script will stop and report it.
#  - Selectors may change; we'll add helpful debug output if upload fails.
import chromedriver_autoinstaller
chromedriver_autoinstaller.install()
import os
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, WebDriverException

NAUKRI_USER = os.getenv("NAUKRI_USER")
NAUKRI_PASS = os.getenv("NAUKRI_PASS")
PROFILE_URL = os.getenv("NAUKRI_PROFILE_URL", "")  # optional direct profile/resume edit URL
RESUME_PATH = Path(os.getenv("RESUME_PATH", "Viswanatha_Resume_Updated.docx"))

def make_driver():
    opts = Options()
    opts.add_argument("--no-sandbox")
    opts.add.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=opts)
    return driver

def find_and_upload_file(driver, resume_path):
    inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
    if not inputs:
        return False, "No file input found on the page"
    try:
        inputs[0].send_keys(str(resume_path.resolve()))
        time.sleep(2)
        return True, "Sent file to first file input"
    except Exception as e:
        return False, f"Failed to send file: {e}"

def click_possible_save(driver):
    try:
        btns = driver.find_elements(By.XPATH,
            "//button[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'save') or "
            "contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'update') or "
            "contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'upload')]")
        if btns:
            btns[0].click()
            time.sleep(2)
            return True, "Clicked possible save/upload button"
    except Exception:
        pass
    return False, "No obvious save button clicked"

def detect_captcha(page_source):
    txt = page_source.lower()
    if "captcha" in txt or "recaptcha" in txt or "i'm not a robot" in txt or "verify" in txt:
        return True
    return False

def upload():
    if not RESUME_PATH.exists():
        print("ERROR: resume not found:", RESUME_PATH)
        return 2

    if not NAUKRI_USER or not NAUKRI_PASS:
        print("ERROR: NAUKRI_USER/NAUKRI_PASS secrets not set")
        return 3

    driver = None
    try:
        driver = make_driver()
    except WebDriverException as e:
        print("ERROR: Cannot start Chrome WebDriver:", e)
        return 4

    try:
        driver.get("https://www.naukri.com/nlogin/login")
        time.sleep(2)

        if detect_captcha(driver.page_source):
            print("CAPTCHA detected on login page. Cannot automate.")
            return 5

        try:
            u = driver.find_element(By.ID, "username")
            p = driver.find_element(By.ID, "password")
        except NoSuchElementException:
            try:
                u = driver.find_element(By.NAME, "email")
                p = driver.find_element(By.NAME, "password")
            except NoSuchElementException:
                print("ERROR: Login form inputs not found:")
                print(driver.page_source[:2000])
                return 6

        u.clear(); u.send_keys(NAUKRI_USER)
        p.clear(); p.send_keys(NAUKRI_PASS)

        try:
            driver.find_element(By.XPATH, "//button[contains(@type,'submit')]").click()
        except:
            try:
                driver.find_element(By.XPATH, "//button[contains(.,'Login') or contains(.,'Sign in')]").click()
            except:
                print("WARNING: Login button not found.")

        time.sleep(4)

        if detect_captcha(driver.page_source):
            print("CAPTCHA detected after login. Manual completion required.")
            return 5

        if PROFILE_URL:
            driver.get(PROFILE_URL)
        else:
            driver.get("https://www.naukri.com/mnjuser/profile")
        time.sleep(3)

        if detect_captcha(driver.page_source):
            print("CAPTCHA found on profile page. Manual required.")
            return 5

        ok, msg = find_and_upload_file(driver, RESUME_PATH)
        print("Upload file attempt:", ok, msg)
        if not ok:
            print("PAGE SNIPPET:")
            print(driver.page_source[:2000])
            return 7

        clicked, msg2 = click_possible_save(driver)
        print("Clicked save:", clicked, msg2)
        print("Upload attempted - verify on Naukri profile.")
        return 0

    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    exit(upload())
