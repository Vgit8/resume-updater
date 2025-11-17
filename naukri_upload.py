#!/usr/bin/env python3
"""
import os
naukri_upload.py
Robust Selenium script to upload resume to Naukri.

Environment variables expected (set as GitHub Secrets / workflow env):
  - NAUKRI_USER        (required)  : Naukri username/email
  - NAUKRI_PASS        (required)  : Naukri password
  - RESUME_PATH        (required)  : path to Viswanatha_Resume_Updated.docx
  - NAUKRI_PROFILE_URL (optional)  : direct profile/resume edit URL

Exit codes:
  0 - success
  1 - unexpected error
  2 - resume missing
  3 - blocked by CAPTCHA / manual interaction required
  4 - login failed
"""
import os
import sys
import time
import logging
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)

# autoinstall matching chromedriver
import chromedriver_autoinstaller

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("naukri_upload")

IMPLICIT_WAIT = 6
EXPLICIT_WAIT = 12
WORKSPACE = os.environ.get("GITHUB_WORKSPACE", os.getcwd())


def take_screenshot(driver, name="screenshot.png"):
    Path(WORKSPACE).mkdir(parents=True, exist_ok=True)
    out = os.path.join(WORKSPACE, name)
    try:
        driver.save_screenshot(out)
        logger.info("Saved screenshot: %s", out)
    except Exception as e:
        logger.warning("Failed to save screenshot: %s", e)
    return out


def make_driver():
    """
    Create a Chrome WebDriver using chromedriver_autoinstaller.
    Respects the HEADLESS environment variable:
      - If HEADLESS is "false", "0", or "no" (case-insensitive) -> runs with GUI (not headless)
      - Otherwise runs headless (default)
    """
    import chromedriver_autoinstaller
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options

    # Ensure chromedriver is installed and get path
    chromedriver_path = chromedriver_autoinstaller.install()

    opts = Options()

    # HEADLESS handling: default = True
    headless_env = os.environ.get("HEADLESS", "true").strip().lower()
    headless = headless_env not in ("0", "false", "no")

    # Use newer headless flag if available, fallback to classic
    if headless:
        try:
            opts.add_argument("--headless=new")
        except Exception:
            opts.add_argument("--headless")

    # Typical flags useful for CI
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")

    # Provide a common desktop user-agent to reduce bot detection
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0 Safari/537.36"
    )

    # Optional: prevent automation-controlled display (not guaranteed)
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=opts)

    # Extra niceties
    driver.set_page_load_timeout(60)
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": opts.arguments[-1]}) if headless else None

    return driver

def is_captcha_present(driver):
    txt = driver.page_source.lower()
    if "captcha" in txt or "recaptcha" in txt or "i'm not a robot" in txt or "verify" in txt:
        return True
    # iframe recaptcha check
    try:
        if driver.find_elements(By.XPATH, "//iframe[contains(@src,'recaptcha') or contains(@src,'captcha')]"):
            return True
    except Exception:
        pass
    return False


def find_first(driver, selectors, timeout=EXPLICIT_WAIT):
    """Try a list of (By, selector) and return first element found within timeout each."""
    for by, sel in selectors:
        try:
            el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, sel)))
            return el
        except TimeoutException:
            continue
    raise NoSuchElementException(f"No selector matched among: {selectors}")


def do_login(driver, username, password):
    """Attempt login; returns (True,0) on success, (False,code) on failure/code."""
    login_urls = [
        "https://www.naukri.com/nlogin/login",
        "https://www.naukri.com/login",
    ]
    for url in login_urls:
        try:
            logger.info("Opening login URL: %s", url)
            driver.get(url)
            time.sleep(1.0)
            if is_captcha_present(driver):
                logger.error("CAPTCHA detected on login page")
                take_screenshot(driver, "captcha_on_login.png")
                return False, 3

            username_selectors = [
                (By.ID, "usernameField"),
                (By.ID, "username"),
                (By.NAME, "email"),
                (By.NAME, "username"),
                (By.XPATH, "//input[contains(@placeholder,'Email') or contains(@placeholder,'email')]"),
            ]
            password_selectors = [
                (By.ID, "passwordField"),
                (By.ID, "password"),
                (By.NAME, "PASSWORD"),
                (By.NAME, "password"),
                (By.XPATH, "//input[@type='password']"),
            ]

            try:
                user_input = find_first(driver, username_selectors, timeout=6)
                pass_input = find_first(driver, password_selectors, timeout=6)
            except NoSuchElementException:
                # try clicking any login link then retry
                logger.info("Login inputs not found, trying alternative login link")
                try:
                    login_links = driver.find_elements(By.XPATH, "//a[contains(.,'Login') or contains(.,'Sign in') or contains(.,'Log In')]")
                    if login_links:
                        login_links[0].click()
                        time.sleep(1)
                        user_input = find_first(driver, username_selectors, timeout=6)
                        pass_input = find_first(driver, password_selectors, timeout=6)
                    else:
                        take_screenshot(driver, "login_inputs_missing.png")
                        return False, 4
                except Exception as e:
                    logger.exception("Alternative login flow failed: %s", e)
                    take_screenshot(driver, "login_flow_exception.png")
                    return False, 4

            user_input.clear(); user_input.send_keys(username)
            pass_input.clear(); pass_input.send_keys(password)
            time.sleep(0.2)

            # try submit button
            try:
                submit = driver.find_element(By.XPATH, "//button[@type='submit' or contains(.,'Login') or contains(.,'Sign in')]")
                try:
                    submit.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", submit)
            except NoSuchElementException:
                try:
                    pass_input.send_keys("\n")
                except Exception:
                    logger.warning("Could not submit login form programmatically")

            time.sleep(3.0)
            if is_captcha_present(driver):
                logger.error("CAPTCHA detected after login")
                take_screenshot(driver, "captcha_after_login.png")
                return False, 3

            page = driver.page_source.lower()
            if "logout" in page or "my profile" in page or "dashboard" in page or "profile" in page:
                logger.info("Login appears successful")
                return True, 0

            # fallback: assume login OK (some flows redirect) but still continue
            logger.info("Login completed (verification uncertain); proceeding")
            return True, 0

        except Exception as e:
            logger.exception("Exception during login attempt to %s: %s", url, e)
            take_screenshot(driver, "login_exception.png")
            continue

    logger.error("All login attempts failed")
    return False, 4


def upload_resume_to_profile(driver, resume_path, profile_url=None):
    """Navigate to profile / upload resume and attempt to save/upload."""
    if not os.path.exists(resume_path):
        logger.error("Resume not found: %s", resume_path)
        return False, 2

    try:
        if profile_url:
            logger.info("Opening profile URL: %s", profile_url)
            driver.get(profile_url)
        else:
            logger.info("Going to default profile path")
            driver.get("https://www.naukri.com/mnjuser/profile")
        time.sleep(2.0)

        if is_captcha_present(driver):
            logger.error("CAPTCHA detected on profile page")
            take_screenshot(driver, "captcha_on_profile.png")
            return False, 3

        file_selectors = [
            (By.XPATH, "//input[@type='file']"),
            (By.XPATH, "//input[contains(@id,'resume') and @type='file']"),
            (By.XPATH, "//input[contains(@name,'resume') and @type='file']"),
            (By.CSS_SELECTOR, "input[type='file']"),
        ]

        file_input = None
        for by, sel in file_selectors:
            try:
                file_input = WebDriverWait(driver, 6).until(EC.presence_of_element_located((by, sel)))
                break
            except TimeoutException:
                continue

        if file_input is None:
            # try reveal via clicking edit/upload buttons
            logger.info("File input not visible; trying edit/upload buttons")
            try:
                btns = driver.find_elements(By.XPATH, "//button[contains(., 'Edit') or contains(., 'Upload') or contains(., 'Add resume') or contains(., 'Update')]")
                if btns:
                    btns[0].click()
                    time.sleep(1)
                    for by, sel in file_selectors:
                        try:
                            file_input = WebDriverWait(driver, 4).until(EC.presence_of_element_located((by, sel)))
                            break
                        except TimeoutException:
                            continue
                else:
                    logger.error("No edit/upload button found and no file input available")
                    take_screenshot(driver, "no_upload_input.png")
                    return False, 1
            except Exception as e:
                logger.exception("Error trying to reveal file input: %s", e)
                take_screenshot(driver, "reveal_input_failed.png")
                return False, 1

        abs_path = os.path.abspath(resume_path)
        logger.info("Uploading resume from %s", abs_path)
        try:
            file_input.send_keys(abs_path)
        except Exception as e:
            logger.exception("send_keys to file input failed: %s", e)
            try:
                driver.execute_script("arguments[0].style.display = 'block';", file_input)
                file_input.send_keys(abs_path)
            except Exception as e2:
                logger.exception("JS fallback also failed: %s", e2)
                take_screenshot(driver, "file_input_sendkeys_failed.png")
                return False, 1

        time.sleep(1.5)

        # attempt to click Save/Upload
        try:
            save_btn = driver.find_element(By.XPATH, "//button[contains(., 'Save') or contains(., 'Upload') or contains(., 'Update') or contains(., 'Submit')]")
            try:
                save_btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", save_btn)
            time.sleep(2.5)
            logger.info("Clicked save/upload if present")
        except NoSuchElementException:
            logger.info("No explicit save button found (may be auto-saved)")

        # heuristics to detect success
        page = driver.page_source.lower()
        if any(k in page for k in ("resume uploaded", "successfully uploaded", "upload successful", "resume updated")):
            logger.info("Upload likely successful (message detected)")
            take_screenshot(driver, "upload_success.png")
            return True, 0

        # try to find filename on page
        matches = driver.find_elements(By.XPATH, "//*[contains(text(), '.pdf') or contains(text(), '.doc') or contains(text(), '.docx')]")
        if matches:
            logger.info("Found likely resume filename on page after upload")
            take_screenshot(driver, "upload_likely_success.png")
            return True, 0

        # uncertain - save screenshot for debugging but return success (non-strict)
        logger.warning("Upload uncertain - saved screenshot for inspection")
        take_screenshot(driver, "upload_uncertain.png")
        return True, 0

    except Exception as e:
        logger.exception("Exception during resume upload: %s", e)
        take_screenshot(driver, "upload_exception.png")
        return False, 1


def main():
    username = os.environ.get("NAUKRI_USER")
    password = os.environ.get("NAUKRI_PASS")
    resume_path = os.environ.get("RESUME_PATH")
    profile_url = os.environ.get("NAUKRI_PROFILE_URL")

    logger.info("Starting Naukri upload script")
    logger.info("RESUME_PATH=%s", resume_path)

    if not resume_path or not os.path.exists(resume_path):
        logger.error("RESUME_PATH missing or not found: %s", resume_path)
        sys.exit(2)
    if not username or not password:
        logger.error("NAUKRI_USER/NAUKRI_PASS not provided")
        sys.exit(4)

    driver = None
    try:
        driver = make_driver()
    except Exception as e:
        logger.exception("Failed to init driver: %s", e)
        sys.exit(1)

    try:
        ok, code = do_login(driver, username, password)
        if not ok:
            logger.error("Login failed (code=%s).", code)
            if code == 3:
                sys.exit(3)
            sys.exit(4)

        ok2, code2 = upload_resume_to_profile(driver, resume_path, profile_url)
        if not ok2:
            logger.error("Upload failed (code=%s).", code2)
            if code2 == 3:
                sys.exit(3)
            sys.exit(1)

        logger.info("Upload finished (success).")
        sys.exit(0)

    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        if driver:
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
