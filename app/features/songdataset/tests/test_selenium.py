import tempfile
import time
from pathlib import Path

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.file_detector import LocalFileDetector
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from tests.selenium_support import close_driver, get_host_for_selenium_testing, initialize_driver

pytestmark = pytest.mark.e2e
PASSWORD = "1234"
SONG_DOI = "10.1234/songhub-sample"
SAMPLE_CSV = Path(__file__).parents[1] / "song_examples" / "spotify_youtube_rock_alt.csv"


def _login(driver, host):
    driver.get(f"{host}/login")
    driver.find_element(By.NAME, "email").send_keys("songhub@example.com")
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.ID, "submit").click()
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href="/logout"]')))


def _enable_local_file_detector(driver):
    if hasattr(driver, "command_executor"):
        driver.file_detector = LocalFileDetector()


def _click(driver, element):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", element)
    element.click()


def test_song_upload_page_redirects_anonymous_visitors_to_login():
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()
        driver.get(f"{host}/songdataset/upload")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "password")))
        assert "/login" in driver.current_url
    finally:
        close_driver(driver)


def test_song_upload_dropzone_rejects_invalid_csv_and_creates_and_edits_draft():
    driver = initialize_driver()
    _enable_local_file_detector(driver)
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as invalid_file:
        invalid_file.write("Artist,Track\nGorillaz,Feel Good Inc.\n")
        invalid_path = invalid_file.name

    try:
        host = get_host_for_selenium_testing()
        _login(driver, host)
        driver.get(f"{host}/songdataset/upload")

        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "title")))
        assert ".csv" in driver.find_element(By.NAME, "file").get_attribute("accept")

        # 1. Invalid CSV triggers Dropzone validation error
        dz_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input.dz-hidden-input"))
        )
        dz_input.send_keys(invalid_path)
        alert = WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.ID, "song-upload-alerts")))
        assert "Missing required columns" in alert.text

        # 2. Valid CSV passes Dropzone validation and enables preview
        dz_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input.dz-hidden-input"))
        )
        dz_input.send_keys(str(SAMPLE_CSV.resolve()))
        preview = WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.ID, "song-dropzone-preview")))
        assert "25" in preview.text

        unique_title = f"Selenium Song Draft {int(time.time())}"
        driver.find_element(By.ID, "song_title").send_keys(unique_title)
        driver.find_element(By.ID, "song_description").send_keys("Uploaded via Selenium Dropzone")
        _click(driver, driver.find_element(By.ID, "song_upload_submit"))

        WebDriverWait(driver, 15).until(EC.url_contains("/dataset/list"))
        assert unique_title in driver.find_element(By.TAG_NAME, "body").text

        # 3. Edit the newly created draft song dataset
        edit_link = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.XPATH, f"//tr[td//a[normalize-space()='{unique_title}']]//a[contains(@href, '/edit')]")
            )
        )
        _click(driver, edit_link)

        title_input = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "edit_song_title")))
        edited_title = f"{unique_title} Edited"
        title_input.clear()
        title_input.send_keys(edited_title)
        _click(driver, driver.find_element(By.ID, "song_edit_submit"))

        heading = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1 b")))
        assert heading.text.strip() == edited_title
    finally:
        Path(invalid_path).unlink(missing_ok=True)
        close_driver(driver)


def test_song_detail_shows_integer_statistics_table_and_filter():
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()
        driver.get(f"{host}/doi/{SONG_DOI}/")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "song-table")))

        body_text = driver.find_element(By.TAG_NAME, "body").text
        assert "Song statistics" in body_text
        assert "Curator, Music" in body_text

        summary_text = WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.ID, "song-summary"))).text
        assert "25" in summary_text
        assert "25.00" not in summary_text

        WebDriverWait(driver, 15).until(
            lambda current: len(current.find_elements(By.CSS_SELECTOR, "#song-table tbody tr")) == 25
        )
        driver.find_element(By.ID, "song-filter").send_keys("Gorillaz")
        WebDriverWait(driver, 15).until(
            lambda current: len(current.find_elements(By.CSS_SELECTOR, "#song-table tbody tr")) == 10
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


def test_explore_filters_and_searches_song_datasets():
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()
        driver.get(f"{host}/explore")
        WebDriverWait(driver, 15).until(EC.text_to_be_present_in_element((By.ID, "results_number"), "6 datasets found"))

        # Filter by Dataset type = Song
        Select(driver.find_element(By.ID, "dataset_type")).select_by_value("song")
        WebDriverWait(driver, 15).until(EC.text_to_be_present_in_element((By.ID, "results_number"), "2 datasets found"))
        assert "Music summary" in driver.find_element(By.ID, "results").text

        # Clear filters restores all datasets and resets dataset_type
        driver.find_element(By.ID, "clear-filters").click()
        WebDriverWait(driver, 15).until(EC.text_to_be_present_in_element((By.ID, "results_number"), "6 datasets found"))
        assert Select(driver.find_element(By.ID, "dataset_type")).first_selected_option.get_attribute("value") == "any"

        # Search by artist inside CSV with dataset_type = Any
        driver.find_element(By.ID, "query").send_keys("Gorillaz")
        WebDriverWait(driver, 15).until(EC.text_to_be_present_in_element((By.ID, "results_number"), "1 dataset found"))
        assert "Spotify and YouTube Rock & Alternative" in driver.find_element(By.ID, "results").text
    finally:
        close_driver(driver)
