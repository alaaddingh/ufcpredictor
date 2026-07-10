import requests
import numpy as np
from datetime import datetime
from bs4 import BeautifulSoup
import re
from fake_useragent import UserAgent
from requests.exceptions import RequestException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

WAYBACK_URL = "https://web.archive.org/web"
WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"
UFC_URL = "https://www.ufc.com/athlete"
REQUEST_TIMEOUT = (100, 180)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def _build_headers():
    try:
        user_agent = UserAgent(fallback=DEFAULT_USER_AGENT)
        agent = user_agent.random
    except Exception:
        agent = DEFAULT_USER_AGENT
    return {
        "User-Agent": agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

_session = requests.Session()
_session.headers.update(_build_headers())
_retry = Retry(
    total=4,
    backoff_factor=2,  # 2s, 4s, 8s, 16s between retries
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
_adapter = HTTPAdapter(max_retries=_retry, pool_maxsize=20, pool_connections=20)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

class Fighter:
    def __init__(self, fighter_name, fight_date):
        self.fighter_name = fighter_name
        self.fight_date = fight_date
        self.TimeStamp = self.GetTimeStamp()
        self.ResolvedTimeStamp = self.GetResolvedTimeStamp()
        self.Snapshot = self.GetSnapShot()
        self.RetrievedTimeStamp = self.GetRetrievedTimeStamp()
        self.RetrievedDate = self.GetRetrievedDate()
        self.Soup = self.GetSoup()
        self.wins, self.losses, self.draws = self.GetWLD()
        self.height = self.GetHeightCM()
        self.weight = self.GetWeightKG()
        self.reach = self.GetReachCM()
        self.splm = self.GetSLpM()
        self.str_acc = self.GetStrAcc()
        self.sapm = self.GetSApM()
        self.str_def = self.GetStrDef()
        self.td_avg = self.GetTDAvg()
        self.td_avg_acc = self.GetTDAcc()
        self.td_def = self.GetTDDef()
        self.sub_avg = self.GetSubAvg()

    def GetTimeStamp(self):
        TimeStamp = datetime.strptime(self.fight_date, "%B %d, %Y").strftime("%Y%m%d235959")
        return TimeStamp

    def GetResolvedTimeStamp(self):
        params = {
            "url": f"{UFC_URL}/{self.fighter_name}",
            "output": "json",
            "fl": "timestamp,statuscode,original",
            "filter": "statuscode:200",
        }

        pre_fight_params = {
            **params,
            "limit": "-1",
            "to": self.TimeStamp,
        }
        try:
            pre_fight_rows = self._get_cdx_rows(pre_fight_params)
            if pre_fight_rows:
                pre_fight_rows.sort(key=lambda row: row[0])
                return pre_fight_rows[-1][0]

            raise ValueError(
                f"could not find archived snapshot for {self.fighter_name} on or before {self.fight_date}"
            )
        except RequestException:
            return self.TimeStamp

    def _get_cdx_rows(self, params):
        response = _session.get(WAYBACK_CDX_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return data[1:] if len(data) >= 2 else []

    def GetRetrievedTimeStamp(self):
        match = re.search(r"/web/(\d{14})/", self.Snapshot.url)
        if match:
            return match.group(1)
        return None

    def GetRetrievedDate(self):
        if not self.RetrievedTimeStamp:
            return "Unknown"
        RetrievedDate = datetime.strptime(self.RetrievedTimeStamp, "%Y%m%d%H%M%S").strftime("%B %d, %Y")
        return RetrievedDate

    def GetSnapShot(self):
        SnapshotURL = f"{WAYBACK_URL}/{self.ResolvedTimeStamp}/{UFC_URL}/{self.fighter_name}"
        response = _session.get(SnapshotURL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response

    def GetSoup(self):
        soup = BeautifulSoup(self.Snapshot.text, 'html.parser')
        return soup

    def GetWLD(self):
        div = self.Soup.find("div", class_="c-hero__headline-suffix")
        if div:
            text = div.get_text(" ", strip=True)

        else:
            record = self.Soup.find("p", class_="hero-profile__division-body")
            if record is None:
                # stats unavailable
                return np.nan, np.nan, np.nan
            
            text = record.get_text(" ", strip=True)
        match = re.search(r'(\d+)-(\d+)-(\d*)\s*\(W-L-D\)', text)
        if not match:
            # stats unavailable
            return np.nan, np.nan, np.nan
        
        wins = int(match.group(1))
        losses = int(match.group(2))
        draws = int(match.group(3)) if match.group(3) else 0
        return wins, losses, draws

    def GetHeightCM(self):
        label = self.Soup.find("div", class_="c-bio__label", string=lambda s: s and s.strip() == "Height")
        value = label.find_next_sibling("div", class_="c-bio__text") if label is not None else None
        if label is None or value is None:
            return np.nan
        try:
            return round(float(value.get_text(strip=True)) * 2.54, 2)
        except ValueError:
            return np.nan

    def GetWeightKG(self):
        label = self.Soup.find("div", class_="c-bio__label", string=lambda s: s and s.strip() == "Weight")
        value = label.find_next_sibling("div", class_="c-bio__text") if label is not None else None
        if label is None or value is None:
            return np.nan
        try:
            return round(float(value.get_text(strip=True)) / 2.205, 2)
        except ValueError:
            return np.nan

    def GetReachCM(self):
        label = self.Soup.find("div", class_="c-bio__label", string=lambda s: s and s.strip() == "Reach")
        value = label.find_next_sibling("div", class_="c-bio__text") if label is not None else None
        if label is None or value is None:
            return np.nan
        try:
            return round(float(value.get_text(strip=True)) * 2.54, 2)
        except ValueError:
            return np.nan

    def GetSLpM(self):
        label = self.Soup.find("div", class_="c-stat-compare__label", string=lambda s: s and s.strip() == "Sig. Str. Landed")
        group = label.find_parent("div", class_="c-stat-compare__group-1") if label is not None else None
        number = group.find("div", class_="c-stat-compare__number") if group is not None else None
        if label is None or group is None or number is None:
            return np.nan
        try:
            return round(float(number.get_text(strip=True)), 2)
        except ValueError:
            return np.nan

    def GetStrAcc(self):
        title = self.Soup.find("h2", class_="e-t3", string=lambda s: s and s.strip() == "Striking accuracy")
        block = title.find_parent("div", class_="overlap-athlete-content") if title is not None else None
        if block is None and title is not None:
            block = title.find_parent("div", class_="c-overlap-athlete-detail__card")
        percent = block.find("text", class_="e-chart-circle__percent") if block is not None else None
        if title is None or block is None or percent is None:
            return np.nan
        try:
            return round(float(percent.get_text(strip=True).replace("%", "")), 2)
        except ValueError:
            return np.nan

    def GetSApM(self):
        label = self.Soup.find("div", class_="c-stat-compare__label", string=lambda s: s and s.strip() == "Sig. Str. Absorbed")
        group = label.find_parent("div", class_="c-stat-compare__group-2") if label is not None else None
        number = group.find("div", class_="c-stat-compare__number") if group is not None else None
        if label is None or group is None or number is None:
            return np.nan
        try:
            return round(float(number.get_text(strip=True)), 2)
        except ValueError:
            return np.nan

    def GetStrDef(self):
        label = self.Soup.find("div", class_="c-stat-compare__label", string=lambda s: s and s.strip() == "Sig. Str. Defense")
        group = label.find_parent("div", class_="c-stat-compare__group-1") if label is not None else None
        number = group.find("div", class_="c-stat-compare__number") if group is not None else None
        if label is None or group is None or number is None:
            return np.nan
        try:
            return round(float(number.get_text(strip=True).replace("%", "")), 2)
        except ValueError:
            return np.nan

    def GetTDAvg(self):
        label = self.Soup.find("div", class_="c-stat-compare__label", string=lambda s: s and s.strip() == "Takedown avg")
        group = label.find_parent("div", class_="c-stat-compare__group-1") if label is not None else None
        number = group.find("div", class_="c-stat-compare__number") if group is not None else None
        if label is None or group is None or number is None:
            return np.nan
        try:
            return round(float(number.get_text(strip=True)), 2)
        except ValueError:
            return np.nan

    def GetTDAcc(self):
        title = self.Soup.find("h2", class_="e-t3", string=lambda s: s and s.strip() in ["Grappling accuracy", "Takedown Accuracy"])
        block = title.find_parent("div", class_="overlap-athlete-content") if title is not None else None
        if block is None and title is not None:
            block = title.find_parent("div", class_="c-overlap-athlete-detail__card")
        percent = block.find("text", class_="e-chart-circle__percent") if block is not None else None
        if title is None or block is None or percent is None:
            return np.nan
        try:
            return round(float(percent.get_text(strip=True).replace("%", "")), 2)
        except ValueError:
            return np.nan

    def GetTDDef(self):
        label = self.Soup.find("div", class_="c-stat-compare__label", string=lambda s: s and s.strip() == "Takedown Defense")
        group = label.find_parent("div", class_="c-stat-compare__group-2") if label is not None else None
        number = group.find("div", class_="c-stat-compare__number") if group is not None else None
        if label is None or group is None or number is None:
            return np.nan
        try:
            return round(float(number.get_text(strip=True).replace("%", "")), 2)
        except ValueError:
            return np.nan

    def GetSubAvg(self):
        label = self.Soup.find("div", class_="c-stat-compare__label", string=lambda s: s and s.strip() == "Submission avg")
        group = label.find_parent("div", class_="c-stat-compare__group-2") if label is not None else None
        number = group.find("div", class_="c-stat-compare__number") if group is not None else None
        if label is None or group is None or number is None:
            return np.nan
        try:
            return round(float(number.get_text(strip=True)), 2)
        except ValueError:
            return np.nan


if __name__ == "__main__":
    # Test with Islam Makhachev
    islam = Fighter("islam-makhachev", "March 1, 2026")
    print(islam.RetrievedDate)
    print(islam.height)
    print(islam.weight)
    print(islam.reach)
    print(islam.splm)
    print(islam.str_acc)
    print(islam.sapm)
    print(islam.str_def)
    print(islam.td_avg)
    print(islam.td_avg_acc)
    print(islam.td_def)
    print(islam.sub_avg)
