import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from tests.selenium_support import close_driver, get_host_for_selenium_testing, initialize_driver

pytestmark = pytest.mark.e2e
PASSWORD = "1234"
SONG_DOI = "10.1234/songhub-sample"


def test_song_upload_page_exposes_csv_dropzone_to_anonymous_visitors():
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()
        driver.get(f"{host}/songdataset/upload")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "password")))
        assert "/login" in driver.current_url
    finally:
        close_driver(driver)


def _login(driver, host):
    driver.get(f"{host}/login")
    driver.find_element(By.NAME, "email").send_keys("songhub@example.com")
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.ID, "submit").click()
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href="/logout"]')))


def test_song_upload_form_requires_csv_and_exposes_metadata_fields():
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()
        _login(driver, host)
        driver.get(f"{host}/songdataset/upload")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "title")))
        assert ".csv" in driver.find_element(By.NAME, "file").get_attribute("accept")
        assert driver.find_element(By.NAME, "description").is_displayed()
    finally:
        close_driver(driver)


def test_song_detail_shows_statistics_table_and_filter():
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()
        driver.get(f"{host}/doi/{SONG_DOI}/")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "song-table")))
        assert "Song statistics" in driver.find_element(By.TAG_NAME, "body").text
        rows = driver.find_elements(By.CSS_SELECTOR, "#song-table tbody tr")
        assert rows
        driver.find_element(By.ID, "song-filter").send_keys("Gorillaz")
        WebDriverWait(driver, 15).until(
            lambda current: len(current.find_elements(By.CSS_SELECTOR, "#song-table tbody tr")) < len(rows)
        )
    finally:
        close_driver(driver)


def test_song_detail_exposes_csv_download():
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()
        driver.get(f"{host}/doi/{SONG_DOI}/")
        link = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/songdataset/file/"]'))
        )
        assert link.get_attribute("href").endswith("/download")
    finally:
        close_driver(driver)
