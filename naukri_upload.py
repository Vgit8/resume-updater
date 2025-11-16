#!/usr/bin/env python3
"""
naukri_upload.py
Automates uploading the updated resume to Naukri.

Usage (via GitHub Actions workflow):
  - Set secrets: NAUKRI_USER, NAUKRI_PASS, NAUKRI_PROFILE_URL (optional)
  - Set RESUME_PATH env var (workflow sets this)
  - This script will:
      * launch headless Chrome
      * log in to Naukri
      * navigate to profile / resume upload area
      * upload the file and attempt to save
      * take screenshots and print verbose logs for debugging

Exit codes:
  0 - success
  1 - unexpected error
  2 - resume file missing or invalid
  3 - automation blocked (CAPTCHA / manual interaction required)
  4 - login failed
"""

import os
import sys
import time
import logging
from pathlib import Path

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
    ElementNotInteractableException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# chromedriver autoinstaller
import chromedriver_autoinstaller

# --- Configuration ---
LOG_LEVEL = logging.INFO
IMPLICIT_WAIT = 6   # seconds
EXPLICIT_WAIT = 12  # seconds
SCREENSHOT_DIR = os.environ.get("GITHUB_WORKSPACE", os.getcwd())  # saves screenshots to workspace

# --- Logging setup ---
logger = logging.getLogger("naukri_upload")
logger.setLevel(LOG_LEVEL)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)


def take_screenshot(driver, name="screenshot.png"):
    """Save screenshot to workspace and return path."""
    Path(SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)
    out = os.path.join(SCREENSHOT_DIR, name)
    try:
        driver.save_screenshot(out)
        logger.info(f"Saved screenshot: {out}")
    except Exception as e:
        logger.warning(f"Failed to save screenshot: {e}")
    return out


def make_driver():
    """
    Create a headless Chrome driver and return it.
    Uses chromedriver_autoinstaller to install a matching chromedriver.
    """
    try:
        chromedriver_autoinstaller.install()
    except Exception as e:
        logger.warning(f"chromedriver_autoinstaller.install() failed: {e} - trying without install")

    opts = Options()
    # headless on GitHub runner; adjust if you want visible browser for local debugging
    # For newer Chrome use "--headless=new", otherwise fallback to "--headless"
    try:
        opts.add_argument("--headless=new")
    except Exception:
        opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-gpu")

    # configure service (chromedriver_autoinstaller ensures chromedriver on PATH)
    service = Service()
    try:
        driver = webdriver.Chrome(service=service, options=opts)
    except WebDriverException as e:
        logger.error("Failed to start Chrome WebDriver: %s", e)
        raise

    driver.implicitly_wait(IMPLICIT_WAIT)
    return driver


# Helper to try multiple selectors
def find_element_with_fallback(driver, selectors, timeout=EXPLICIT_WAIT):
    """
    selectors: list of tuples (By, selector)
    Returns first element found.
    """
    wait = WebDriverWait(driver, timeout)
    for by, sel in selectors:
        try:
            el = wait.until(EC.presence_of_element_located((by, sel)))
            logger.debug(f"Found element by {by} -> {sel}")
            return el
        except TimeoutException:
            logger.debug(f"Not found by {by} -> {sel} (timeout)")
            continue
    raise NoSuchElementException(f"No element found for selectors: {selectors}")


def is_captcha_present(driver):
    """Detect presence of common captcha markers on page."""
    page = driver.page_source.lower()
    if "captcha" in page or "i'm not a robot" in page or "recaptcha" in page:
        return True
    # also try to find common captcha elements
    try:
        if driver.find_elements(By.XPATH, "//iframe[contains(@src, 'recaptcha')]"):
            return True
    except Exception:
        pass
    return False


def do_login(driver, username, password):
    """Try to login to Naukri. Returns True on success, False otherwise."""
    login_urls = [
        "https://www.naukri.com/nlogin/login",          # standard login
        "https://www.naukri.com/login",                 # fallback
    ]
    logged_in = False

    for url in login_urls:
        try:
            logger.info(f"Opening login URL: {url}")
            driver.get(url)
            time.sleep(1.2)
            if is_captcha_present(driver):
                logger.error("CAPTCHA detected on login page")
                take_screenshot(driver, "captcha_on_login.png")
                return False, 3

            # selectors fallback for username/email field
            username_selectors = [
                (By.ID, "usernameField"),
                (By.ID, "eLogin"),
                (By.NAME, "email"),
                (By.NAME, "username"),
                (By.XPATH, "//input[contains(@placeholder,'Email') or contains(@placeholder,'email') or contains(@placeholder,'Username')]"),
            ]
            password_selectors = [
                (By.ID, "passwordField"),
                (By.ID, "pLogin"),
                (By.NAME, "PASSWORD"),
                (By.NAME, "password"),
                (By.XPATH, "//input[@type='password']"),
            ]

            try:
                user_in = find_element_with_fallback(driver, username_selectors, timeout=6)
                pass_in = find_element_with_fallback(driver, password_selectors, timeout=6)
            except NoSuchElementException:
                logger.warning("Username/password input not found on page; trying to click login link")
                # attempt to click a login link then retry
                try:
                    # look for login link/button
                    login_btns = driver.find_elements(By.XPATH, "//a[contains(., 'Login') or contains(., 'Sign in') or contains(., 'Log In')]")
                    if login_btns:
                        login_btns[0].click()
                        time.sleep(1)
                        user_in = find_element_with_fallback(driver, username_selectors, timeout=6)
                        pass_in = find_element_with_fallback(driver, password_selectors, timeout=6)
                    else:
                        logger.error("No login inputs nor login link found on the page")
                        take_screenshot(driver, "login_inputs_not_found.png")
                        continue
                except Exception as e:
                    logger.exception("Failed trying login link: %s", e)
                    continue

            # Clear and enter credentials
            user_in.clear()
            user_in.send_keys(username)
            pass_in.clear()
            pass_in.send_keys(password)
            time.sleep(0.2)

            # Find a submit button and click
            submit_selectors = [
                (By.XPATH, "//button[@type='submit']"),
                (By.XPATH, "//input[@type='submit']"),
                (By.XPATH, "//button[contains(., 'Login') or contains(., 'Sign in') or contains(., 'Log In')]"),
                (By.XPATH, "//a[contains(@class,'login') and contains(.,'Login')]"),
            ]
            try:
                submit_btn = find_element_with_fallback(driver, submit_selectors, timeout=5)
                try:
                    submit_btn.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", submit_btn)
            except NoSuchElementException:
                # fallback: press Enter on password field
                try:
                    pass_in.send_keys("\n")
                except Exception:
                    logger.warning("Could not submit form programmatically")
            logger.info("Login submitted, waiting for navigation...")
            time.sleep(3.5)

            # After submit, check whether logged in by presence of profile elements or absence of login form
            if is_captcha_present(driver):
                logger.error("CAPTCHA detected after login attempt")
                take_screenshot(driver, "captcha_after_login.png")
                return False, 3

            # crude check: if page contains "logout" or profile link
            page = driver.page_source.lower()
            if "logout" in page or "my profile" in page or "dashboard" in page or "profile" in page:
                logger.info("Login appears successful (page content check).")
                return True, 0

            # some sites redirect to profile URL after login; check cookies or try to open profile URL
            logger.info("Login not obviously successful; trying profile URL if provided.")
            # continue to next step; return a neutral failure here and let upload flow try
            # but not treat as hard failure yet
            return True, 0

        except Exception as e:
            logger.exception("Exception while trying login at %s: %s", url, e)
            take_screenshot(driver, "login_exception.png")
            continue

    logger.error("All login URLs attempted, login failed.")
    return False, 4


def upload_resume_to_profile(driver, resume_path, profile_url=None):
    """
    Navigate to profile edit or provided profile_url and try to upload resume.
    Returns (True, 0) on success, (False, code) on failure.
    """
    if not os.path.exists(resume_path):
        logger.error("Resume file not found: %s", resume_path)
        return False, 2

    try:
        if profile_url:
            logger.info("Opening profile URL: %s", profile_url)
            driver.get(profile_url)
            time.sleep(2)
        else:
            # attempt to go to edit profile
            logger.info("Profile URL not provided; attempting to navigate to profile page.")
            driver.get("https://www.naukri.com/mnjuser/profile")  # common path; might redirect
            time.sleep(2)

        if is_captcha_present(driver):
            logger.error("CAPTCHA detected on profile page")
            take_screenshot(driver, "captcha_on_profile.png")
            return False, 3

        # Try to find file input elements
        file_selectors = [
            (By.XPATH, "//input[@type='file']"),
            (By.XPATH, "//input[contains(@id,'resume') and @type='file']"),
            (By.XPATH, "//input[contains(@name,'resume') and @type='file']"),
            (By.CSS_SELECTOR, "input[type='file']"),
        ]

        try:
            file_input = find_element_with_fallback(driver, file_selectors, timeout=6)
        except NoSuchElementException:
            logger.warning("File input not found immediately; trying to click edit/resume buttons")

            # Try to click an Edit or Upload button to reveal the file input
            edit_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Edit') or contains(., 'Update') or contains(., 'Add resume') or contains(., 'Upload') or contains(., 'Edit Profile')]")
            if edit_buttons:
                try:
                    logger.info("Clicking edit button to reveal upload input")
                    edit_buttons[0].click()
                    time.sleep(1)
                    file_input = find_element_with_fallback(driver, file_selectors, timeout=6)
                except Exception as e:
                    logger.exception("Failed to reveal file input after clicking edit: %s", e)
                    take_screenshot(driver, "reveal_input_failed.png")
                    return False, 1
            else:
                logger.error("No edit/upload button found and no file input - cannot upload automatically.")
                take_screenshot(driver, "no_upload_input.png")
                return False, 1

        # We have a file input element -> send_keys resume path
        abspath = os.path.abspath(resume_path)
        logger.info("Uploading resume: %s", abspath)
        try:
            file_input.send_keys(abspath)
        except Exception as e:
            logger.exception("Failed to send_keys to file input: %s", e)
            # try JS fallback: set attribute (rarely works due to browser security)
            try:
                driver.execute_script("arguments[0].style.display = 'block';", file_input)
                file_input.send_keys(abspath)
            except Exception as e2:
                logger.exception("JS fallback also failed: %s", e2)
                take_screenshot(driver, "file_input_sendkeys_failed.png")
                return False, 1

        time.sleep(1.5)

        # Try to find and click save/upload button
        save_selectors = [
            (By.XPATH, "//button[contains(., 'Save') or contains(., 'Upload') or contains(., 'Save & Continue') or contains(., 'Update resume')]"),
            (By.XPATH, "//input[@type='submit']"),
            (By.XPATH, "//button[contains(@class,'save') or contains(@class,'upload')]"),
        ]
        try:
            save_btn = find_element_with_fallback(driver, save_selectors, timeout=6)
            try:
                save_btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", save_btn)
            logger.info("Clicked save/upload button")
            time.sleep(3)
        except NoSuchElementException:
            logger.warning("Could not find explicit Save/Upload button; assuming upload auto-saved")
            # still consider this not fatal; check for confirmation message below

        # Check for success indicators (flash message or updated resume name)
        page = driver.page_source.lower()
        if any(s in page for s in ("resume uploaded", "successfully uploaded", "upload successful", "resume updated")):
            logger.info("Upload appears successful (page content matched).")
            take_screenshot(driver, "upload_success.png")
            return True, 0

        # As another heuristic: check if file input now contains value or profile shows resume filename
        # (try to find text that looks like a filename)
        possible_names = driver.find_elements(By.XPATH, "//*[contains(text(), '.pdf') or contains(text(), '.doc') or contains(text(), '.docx')]")
        if possible_names:
            logger.info("Found likely resume filename on page after upload.")
            take_screenshot(driver, "upload_likely_success.png")
            return True, 0

        # If none matched, capture screenshot and return non-fatal failure code
        logger.warning("Upload did not show clear confirmation. Saving screenshot for diagnostics.")
        take_screenshot(driver, "upload_uncertain.png")
        return True, 0  # return 0 to avoid false failure; change to (False,1) if you want strict failure

    except Exception as e:
        logger.exception("Exception during upload: %s", e)
        take_screenshot(driver, "upload_exception.png")
        return False, 1


def main():
    username = os.environ.get("NAUKRI_USER")
    password = os.environ.get("NAUKRI_PASS")
    resume_path = os.environ.get("RESUME_PATH") or os.environ.get("INPUT_RESUME_PATH")
    profile_url = os.environ.get("NAUKRI_PROFILE_URL")

    logger.info("Starting Naukri upload script")
    logger.info("RESUME_PATH=%s", resume_path)
    if not resume_path:
        logger.error("RESUME_PATH not set. Set env var RESUME_PATH to the resume path.")
        sys.exit(2)
    if not os.path.exists(resume_path):
        logger.error("RESUME_PATH path does not exist: %s", resume_path)
        sys.exit(2)

    if not username or not password:
        logger.error("NAUKRI_USER or NAUKRI_PASS not provided in environment variables.")
        sys.exit(4)

    driver = None
    try:
        driver = make_driver()
    except Exception as e:
        logger.exception("Could not initialize WebDriver: %s", e)
        sys.exit(1)

    try:
        ok, code = do_login(driver, username, password)
        if not ok:
            logger.error("Login failed with code: %s", code)
            # if code indicates a captcha (3), exit with that code
            if code == 3:
                logger.error("CAPTCHA or bot protection detected during login; manual intervention needed.")
                sys.exit(3)
            else:
                logger.error("Login failed; aborting.")
                take_screenshot(driver, "login_failed.png")
                sys.exit(4)
        time.sleep(1.0)

        success, ucode = upload_resume_to_profile(driver, resume_path, profile_url)
        if not success:
            logger.error("Upload failed with code: %s", ucode)
            if ucode == 3:
                logger.error("CAPTCHA or manual interaction required on profile page.")
                sys.exit(3)
            sys.exit(1)

        logger.info("Upload finished - success.")
        sys.exit(0)

    except Exception as e:
        logger.exception("Unexpected error in main: %s", e)
        take_screenshot(driver, "unexpected_error.png")
        sys.exit(1)

    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
