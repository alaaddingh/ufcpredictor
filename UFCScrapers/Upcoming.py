import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd



BASE_URL = "https://www.ufc.com/event"

def _GetUpcomingURL():
    soup = _GetSoup(BASE_URL)
    link = soup.select_one("a.e-button--white[href*='/event/']")
    return link["href"]

def _GetSoup(url):
    response = requests.get(url)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")

def _EventDate(soup):
    date = soup.select_one("time")["datetime"]
    return datetime.fromisoformat(date.replace("Z", "+00:00")).strftime("%B %d, %Y")

def GetCard(soup):
    fights = []
    date = _EventDate(soup)

    main_card = soup.select_one("#main-card")

    for fight in main_card.select(".c-listing-fight"):
        names = [
            name.get_text(" ", strip=True)
            for name in fight.select(".c-listing-fight__names-row a")
        ]

        fights.append({
            "r_name": names[0],
            "b_name": names[1],
            "date": date
        })

    return pd.DataFrame(fights)

if __name__ == "__main__":
    soup = _GetSoup(_GetUpcomingURL())
    card = GetCard(soup)

    card.to_csv("./data/processed/Upcoming.csv", index=False)
        


