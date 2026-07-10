import os
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


EVENTS_URL = "http://ufcstats.com/statistics/events/completed?page={page}"


# ufcstats.com requires JS solution on loading page, selenium instead of
# requests library to simulate browser
def _Driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin:
        options.binary_location = chrome_bin
    return webdriver.Chrome(options=options)

def _GetSoup(driver, url, ready_selector):
    driver.get(url)
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, ready_selector))) # css selector that driver waits to load
    html = driver.page_source
    return BeautifulSoup(html, "html.parser")


def _LatestDate(history_file):
    if not history_file or not os.path.exists(history_file):
        return None
    return pd.to_datetime(pd.read_csv(history_file)["date"], format="%B %d, %Y").max()


def _EventLinks(driver, page=1):
    page_soup = _GetSoup(driver, EVENTS_URL.format(page=page), "a.b-link.b-link_style_black")
    return [link["href"] for link in page_soup.select("a.b-link.b-link_style_black")]


def _EventFights(driver, link):
    fights = []

    soup = _GetSoup(driver, link, "tr.b-fight-details__table-row")
    date = soup.select_one("li.b-list__box-list-item").get_text(strip=True).replace("Date:", "").strip()

    for row in soup.select("tr.b-fight-details__table-row__hover"):
        names = [a.get_text(strip=True) for a in row.select("td.l-page_align_left a.b-link.b-link_style_black")[:2]]
        result = row.select_one("i.b-flag__text").get_text(strip=True).lower()
        winner = {"win": 1, "loss": 0, "draw": None}.get(result)
        fights.append({"r_name": names[0], "b_name": names[1], "winner_id": winner, "date": date})

    return fights


def GetHistory(history_file=None, page=1):
    fights = []

    cutoff = _LatestDate(history_file)
    driver = _Driver()
    try:
        for link in _EventLinks(driver, page):
            for fight in _EventFights(driver, link):
                fight_date = pd.to_datetime(fight["date"], format="%B %d, %Y")
                if cutoff is None or fight_date > cutoff:
                    fights.append(fight)
        return pd.DataFrame(fights)
    finally:
        driver.quit()


if __name__ == "__main__":
    HistoryPD = GetHistory("./data/processed/History.csv", page=1)
    HistoryFile = pd.read_csv("./data/processed/History.csv")

    HistoryFile = pd.concat([HistoryFile, HistoryPD])
    HistoryFile.to_csv("./data/processed/History.csv", index=False)

