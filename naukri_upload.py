# naukri_upload.py
# Robust Naukri login + placeholder upload flow
# Save as naukri_upload.py in repo root.

import os
import time
import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    WebDriverException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ----- Logging -----
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("naukri_upload")

# ----- Config / env -----
NAUKRI_USER = os.getenv("NAUKRI_USER")
NAUKRI_PASS = os.getenv("NAUKRI_PASS")
RESUME_PATH = os.getenv("RESUME_PATH")
NAUKRI_PROFILE_URL = os.getenv("NAUKRI_PROFILE_URL")  # optional, not required for login

# Where to save screenshots (artifact)
DEBUG_DIR = Path("debug_screens")
DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def make_driver():
    """Create and return a Chrome webdriver with options suitable for GitHub Actions runner."""
    opts = Options()
    opts.add_argument("--headless=new")  # headless new mode
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    # allow runner to find chromedriver placed by workflow (chromedriver-autoinstaller or apt)
    return webdriver.Chrome(options=opts)


def save_shot(driver, name):
    path = DEBUG_DIR / f"{name}.png"
    try:
        driver.save_screenshot(str(path))
        log.info(f"Saved screenshot: {path}")
    except Exception as e:
        log.warning(f"Failed to save screenshot {path}: {e}")


def try_find_send(driver, wait, selectors, text):
    """Try multiple selectors for a field and send text, return True on success."""
    for by, sel in selectors:
        try:
            el = wait.until(EC.presence_of_element_located((by, sel)))
            el.clear()
            el.send_keys(text)
            log.info(f"Filled field with selector {by}:{sel}")
            return True
        except Exception:
            continue
    return False


def attempt_login(driver):
    """
    Try to login by visiting multiple URLs and using multiple selectors for username/password.
    Return True if login succeeded (profile/username visible), False otherwise.
    """
    wait = WebDriverWait(driver, 8)

    # Candidate login entry pages (try multiple variants)
    login_urls = [
        "https://www.naukri.com/nlogin/login",  # older login
        "https://www.naukri.com/login",  # newer modal path
        "https://www.naukri.com/mnjuser/homepage",  # sometimes redirects to modal
    ]

    username_selectors = [
        (By.CSS_SELECTOR, "input[type='email']"),
        (By.CSS_SELECTOR, "input[type='text']"),
        (By.CSS_SELECTOR, "input[name='email']"),
        (By.CSS_SELECTOR, "input[name='username']"),
        (By.CSS_SELECTOR, "input[id*='email']"),
        (By.CSS_SELECTOR, "input[id*='username']"),
        (By.CSS_SELECTOR, "input[placeholder*='Email']"),
    ]
    password_selectors = [
        (By.CSS_SELECTOR, "input[type='password']"),
        (By.CSS_SELECTOR, "input[name='password']"),
        (By.CSS_SELECTOR, "input[id*='password']"),
    ]

    login_button_selectors = [
        (By.XPATH, "//button[normalize-space()='Login']"),
        (By.XPATH, "//button[contains(@class,'login')]"),
        (By.CSS_SELECTOR, "button[type='submit']"),
    ]

    for url in login_urls:
        log.info(f"Opening login URL: {url}")
        try:
            driver.get(url)
        except WebDriverException as e:
            log.warning(f"Failed to open {url}: {e}")
            continue

        time.sleep(1.0)
        save_shot(driver, "after_open")

        # If login modal hidden behind a "Login" button on page, try click that.
        try:
            for by, sel in [
                (By.XPATH, "//a[normalize-space()='Login']"),
                (By.XPATH, "//button[normalize-space()='Login']"),
                (By.CSS_SELECTOR, "a.login"),
                (By.CSS_SELECTOR, "button.login"),
            ]:
                try:
                    btn = driver.find_element(by, sel)
                    btn.click()
                    log.info("Clicked Login button to open modal")
                    time.sleep(0.7)
                    break
                except Exception:
                    continue
        except Exception:
            pass

        # Try locating input fields and fill them
        try:
            ok_user = try_find_send(driver, wait, username_selectors, NAUKRI_USER)
            ok_pass = try_find_send(driver, wait, password_selectors, NAUKRI_PASS)
            if not ok_user or not ok_pass:
                log.warning("Username/password input not found on page; trying next URL")
                save_shot(driver, "login_inputs_not_found")
                continue

            # try clicking login
            clicked = False
            for by, sel in login_button_selectors:
                try:
                    btn = driver.find_element(by, sel)
                    btn.click()
                    clicked = True
                    log.info(f"Clicked login button {by}:{sel}")
                    break
                except Exception:
                    continue

            if not clicked:
                # fallback: submit via pressing enter on password field
                try:
                    pwd_el = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                    pwd_el.submit()
                    log.info("Submitted password field as fallback")
                except Exception:
                    log.warning("Could not find login button or submit fallback")
                    save_shot(driver, "login_submit_fallback_failed")

            # wait for a post-login indicator (profile avatar, link, or presence of logout)
            try:
                # multiple selectors that indicate logged-in state
                post_login_ok = WebDriverWait(driver, 10).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='logout']")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "img[src*='profile']")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.profileBox")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "span.user-name")),
                    )
                )
                log.info("Login appears successful (post-login element found).")
                save_shot(driver, "login_success")
                return True
            except Exception:
                log.warning("Post-login element not found - login may have failed.")
                save_shot(driver, "login_failed")
                continue

        except Exception as e:
            log.exception("Exception during login attempt")
            save_shot(driver, "login_exception")
            continue

    # all login urls attempted
    log.error("All login URLs attempted, login failed.")
    return False


def upload_resume(driver):
    """Placeholder for the resume upload flow. Adjust selectors to your account's 'Edit profile' page."""
    log.info("Starting resume upload (placeholder).")
    # Example: open profile URL (if provided)
    if NAUKRI_PROFILE_URL:
        try:
            driver.get(NAUKRI_PROFILE_URL)
            time.sleep(1)
            save_shot(driver, "profile_page")
        except Exception:
            log.warning("Could not open NAUKRI_PROFILE_URL; continuing to attempt navigating to profile from menu.")

    # The exact upload steps depend on page structure (you must inspect saved screenshots and adapt)
    # Here's a simple example of selecting a file input:
    try:
        file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if not file_inputs:
            log.error("No file input found on profile page; cannot upload automatically.")
            save_shot(driver, "no_file_input")
            return False

        first_file_input = file_inputs[0]
        first_file_input.send_keys(RESUME_PATH)
        time.sleep(1)
        save_shot(driver, "uploaded_resume_input")
        log.info("Resume file path set on file input (may need extra clicks to save).")
        # You may need to click a Save button afterwards: find & click it
        try:
            save_btn = driver.find_element(By.XPATH, "//button[normalize-space()='Save']")
            save_btn.click()
            time.sleep(1)
            save_shot(driver, "save_clicked")
        except Exception:
            log.info("No explicit Save button clicked (depends on site).")
        return True
    except Exception:
        log.exception("Exception in upload_resume")
        return False


def main():
    # basic env sanity checks
    if not (NAUKRI_USER and NAUKRI_PASS):
        log.error("NAUKRI_USER or NAUKRI_PASS not set in environment")
        return 2

    if not RESUME_PATH or not Path(RESUME_PATH).exists():
        log.error(f"RESUME_PATH not set or file does not exist: {RESUME_PATH}")
        return 3

    log.info("Starting Naukri upload script")
    log.info(f"RESUME_PATH={RESUME_PATH}")

    driver = None
    try:
        driver = make_driver()
    except Exception as e:
        log.exception("Failed to create webdriver")
        return 5

    try:
        ok = attempt_login(driver)
        if not ok:
            log.error("Login failed; aborting.")
            return 4

        # now do upload
        uploaded = upload_resume(driver)
        if not uploaded:
            log.error("Upload step failed.")
            return 6

        log.info("Upload flow completed successfully.")
        return 0

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    rc = main()
    log.info(f"Exiting with code {rc}")
    # exit code for GitHub runner
    import sys
    sys.exit(rc)
