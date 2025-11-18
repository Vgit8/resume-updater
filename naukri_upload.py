# naukri_upload.py (snippet — add near the top)
import os, time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller

# ensure chromedriver that matches the installed Chrome is present
chromedriver_autoinstaller.install()  # downloads driver to PATH if needed

def make_driver(headless=True):
    chrome_path = os.environ.get("CHROME_PATH", "/usr/bin/chromium-browser")  # set by workflow
    options = Options()
    if headless:
        options.add_argument("--headless=new")   # newer headless mode
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # some environments require this:
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36")
    # point to chromium binary if needed
    if os.path.exists(chrome_path):
        options.binary_location = chrome_path

    service = Service()  # chromedriver_autoinstaller put chromedriver in PATH
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# Example usage:
# driver = make_driver(headless=True)   # in CI
# driver.get("https://www.naukri.com/login")
