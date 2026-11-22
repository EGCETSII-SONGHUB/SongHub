"""End-to-end browser tests for the community feature."""

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from tests.selenium_support import close_driver, get_host_for_selenium_testing, initialize_driver

pytestmark = pytest.mark.e2e


def test_community_index_is_reachable_from_sidebar():
    driver = initialize_driver()
    try:
        host = get_host_for_selenium_testing()
        driver.get(host)

        driver.find_element(By.CSS_SELECTOR, '#sidebar a[href="/community"]').click()

        WebDriverWait(driver, 15).until(EC.url_contains("/community"))
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))

        assert "Page not found" not in driver.title
        assert driver.find_element(By.TAG_NAME, "h1").text.strip() == "Communities"
        active = driver.find_element(By.CSS_SELECTOR, "#sidebar li.sidebar-item.active a")
        assert active.get_attribute("href").endswith("/community")
    finally:
        close_driver(driver)
