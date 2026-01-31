"""Web scraper for Kharkiv metro schedule."""

from __future__ import annotations

import re
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup

from ..core.models import DayType, ScheduleEntry, StationSchedule, create_stations

BASE_URL = "https://www.metro.kharkiv.ua"

# Build station name to ID mapping
_STATION_NAME_TO_ID = {}
for sid, station in create_stations().items():
    _STATION_NAME_TO_ID[station.name_ua.lower()] = sid
    # Also add normalized versions
    normalized = station.name_ua.lower().replace("'", "").replace(" «", "").replace("» ", "")
    _STATION_NAME_TO_ID[normalized] = sid

# Additional mappings for renamed stations (weekend schedules)
_STATION_NAME_TO_ID["салтівська"] = "heroes_praci"  # Former "Героїв праці"
_STATION_NAME_TO_ID["ярослава мудрого"] = "pushkinska"  # Former "Пушкінська"
_STATION_NAME_TO_ID["академіка барабашова"] = "kyivska"  # Former "Київська"

# URL mappings for lines
LINE_URLS = {
    DayType.WEEKDAY: {
        "kholodnohirsko_zavodska": "kholodnohikrsko-zavodska-liniia/",
        "saltivska": "saltivska-liniia/",
        "oleksiivska": "oleksiivska-liniia/",
    },
    DayType.WEEKEND: {
        "kholodnohirsko_zavodska": "kholodnohikrsko-zavodska-liniia-vykhidni-dni/",
        "saltivska": "saltivska-liniia.html",  # Different URL pattern for weekend
        "oleksiivska": "oleksiivska-liniia-vykhidni-dni/",
    },
}

# Direct station URLs for Line 3 (Oleksiivska) - these are not all listed on the line page
# Note: URLs contain typos as they appear on the website
LINE_3_STATION_URLS = {
    DayType.WEEKDAY: {
        "metrobudivnykiv": "stantsiia-%C2%ABmetkrobudivnykiv%C2%BB.html",  # typo: metkrobudivnykiv
        "zakhysnykiv_ukrainy": "stantsiia-%C2%ABzakhysnykiv-ukkrainy%C2%BB.html",  # typo: ukkrainy
        "arvatska": "stantsiia-%C2%ABakrkhitektokra-beketova%C2%BB.html",  # typo: akrkhitektokra
        "derzhprom": "stantsiia-%C2%ABdekrzhpkrom%C2%BB.html",  # typo: dekrzhpkrom
        "nauky": "stantsiia-%C2%ABnaukova%C2%BB.html",
        "botanichnyi_sad": "stantsiia-%C2%ABbotanichnyi-sad%C2%BB.html",
        "23_serpnya": "stantsiia-%C2%AB23-sekrpnia%C2%BB.html",  # typo: sekrpnia
        "oleksiivska": "stantsiia-%C2%ABoleksiivska%C2%BB.html",
        "peremoha": "stantsiia-%C2%ABpekremoha%C2%BB.html",  # typo: pekremoha
    },
    DayType.WEEKEND: {
        "metrobudivnykiv": "stantsiia-%C2%ABmetkrobudivnykiv%C2%BB-(vykhidni-dni).html",
        "zakhysnykiv_ukrainy": "stantsiia-%C2%ABzakhysnykiv-ukkrainy%C2%BB-(vykhidni-dni).html",
        "arvatska": "stantsiia-%C2%ABakrkhitektokra-beketova%C2%BB-(vykhidni-dni).html",
        "derzhprom": "stantsiia-%C2%ABdekrzhpkrom%C2%BB-(vykhidni-dni).html",
        "nauky": "stantsiia-%C2%ABnaukova%C2%BB-(vykhidni-dni).html",
        "botanichnyi_sad": "stantsiia-%C2%ABbotanichnyi-sad%C2%BB-(vykhidni-dni).html",
        "23_serpnya": "stantsiia-%C2%AB23-sekrpnia%C2%BB-(vykhidni-dni).html",
        "oleksiivska": "stantsiia-%C2%ABoleksiivska%C2%BB-(vykhidni-dni).html",
        "peremoha": "stantsiia-%C2%ABpekremoha%C2%BB-(vykhidni-dni).html",
    },
}

# Station names mapping
STATION_NAMES = {
    "metrobudivnykiv": "Метробудівників",
    "zakhysnykiv_ukrainy": "Захисників України",
    "arvatska": "Архітектора Бекетова",
    "derzhprom": "Держпром",
    "nauky": "Наукова",
    "botanichnyi_sad": "Ботанічний сад",
    "23_serpnya": "23 Серпня",
    "oleksiivska": "Олексіївська",
    "peremoha": "Перемога",
}

# Station ID mappings from URL slugs
STATION_URL_MAPPING = {
    # Line 1
    "kholodna-hokra": "kholodna_hora",
    "vokzalna": "vokzalna",
    "tsentkralnyi-krynok": "tsentralnyi_rynok",
    "maidan-konstytutsii": "maidan_konstytutsii",
    "levada": "levada",
    "spokrtyvna": "sportyvna",
    "zavodska": "zavodska",
    "tukrboatom": "turboatom",
    "palats-spokrtu": "palats_sportu",
    "akrmiiska": "armiiska",
    "im-o-s-maselskoho": "maselskoho",
    "tkraktokrnyi-zavod": "traktornyi_zavod",
    "industkrialna": "industrialna",
    # Line 2
    "istokrychnyi-muzei": "historical_museum",
    "universytet": "universytet",
    "univekrsytet": "universytet",  # Typo in weekend URL
    "pushkinska": "pushkinska",
    "yakroslava-mudkroho": "pushkinska",  # New name on weekend
    "kyivska": "kyivska",
    "akademika-bakrabashova": "kyivska",  # New name on weekend
    "akademika-pavlova": "akademika_pavlova",
    "studentska": "studentska",
    "heroiv-praci": "heroes_praci",
    "saltivska": "heroes_praci",  # New name on weekend
    # Line 3
    "metrobudivnykiv": "metrobudivnykiv",
    "metkrobudivnykiv": "metrobudivnykiv",  # typo version
    "zakhysnykiv-ukrainy": "zakhysnykiv_ukrainy",
    "zakhysnykiv-ukkrainy": "zakhysnykiv_ukrainy",  # typo version
    "arvatska": "arvatska",  # Архітектора Бекетова
    "akrkhitektokra-beketova": "arvatska",  # typo version
    "derzhprom": "derzhprom",
    "dekrzhpkrom": "derzhprom",  # typo version
    "nauky": "nauky",
    "naukova": "nauky",  # alternative name
    "botanichnyi-sad": "botanichnyi_sad",
    "23-serpnia": "23_serpnya",
    "23-sekrpnia": "23_serpnya",  # typo version
    "oleksiivska": "oleksiivska",
    "peremoha": "peremoha",
    "pekremoha": "peremoha",  # typo version
}


class MetroScraper:
    """Scraper for Kharkiv metro schedules."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
        )

    def fetch_line_stations(self, line_slug: str, day_type: DayType) -> list[dict]:
        """Fetch station URLs for a line."""
        url = urljoin(BASE_URL, LINE_URLS[day_type][line_slug])

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        stations = []

        # Find all station links in the content
        content = soup.find("div", class_="content-text")
        if content:
            for link in content.find_all("a", href=True):
                href = str(link.get("href", ""))
                if "stantsiia-" in href:
                    station_name = link.get_text(strip=True).strip('"').strip("«»")
                    station_slug = self._extract_station_slug(href)
                    station_id = STATION_URL_MAPPING.get(station_slug)

                    if station_id:
                        stations.append(
                            {
                                "id": station_id,
                                "name": station_name,
                                "url": urljoin(BASE_URL, str(href)),
                            }
                        )

        # For Line 3 (Oleksiivska), add missing stations from direct URLs
        # because the line page doesn't list all stations
        if line_slug == "oleksiivska":
            existing_ids = {s["id"] for s in stations}
            for station_id, station_path in LINE_3_STATION_URLS[day_type].items():
                if station_id not in existing_ids:
                    stations.append(
                        {
                            "id": station_id,
                            "name": STATION_NAMES.get(station_id, station_id),
                            "url": urljoin(BASE_URL, station_path),
                        }
                    )

        return stations

    def _extract_station_slug(self, href: str) -> str:
        """Extract station slug from URL."""
        # Decode URL encoding
        href = unquote(href)

        # Extract from URLs like:
        # - "stantsiia-«kholodna-hokra».html" (weekday)
        # - "stantsiia-«kholodna-hokra»-vykhidni-dni.html" (weekend)
        # - "stantsiia-«vokzalna»-(vykhidni-dni).html" (weekend alt)
        match = re.search(r'stantsiia-[«"]?([^"»]+?)["»]?(?:-\(?(?:vykhidni-dni)\)?)?\.html', href)
        if match:
            slug = match.group(1)
            return slug.lower()

        return ""

    def fetch_station_schedule(self, station_url: str, station_id: str) -> list[StationSchedule]:
        """Fetch schedule for a single station."""
        try:
            response = self.session.get(station_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching {station_url}: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        schedules = []

        # Find schedule tables
        tables = soup.find_all("table")

        for table in tables:
            # Try to determine direction from preceding header
            # First try h3/h4/h5, then strong as fallback
            prev = table.find_previous(["h3", "h4", "h5"])
            if not prev:
                prev = table.find_previous("strong")
            direction = None

            if prev:
                text = prev.get_text()
                # Extract direction station name from header like
                # "ЧАС ВІДПРАВЛЕННЯ ПОЇЗДІВ В НАПРЯМКУ СТАНЦІЇ «ІНДУСТРІАЛЬНА»"
                match = re.search(r'[«"]([^»"]+)[»"]', text)
                if match:
                    direction_name = match.group(1)
                    direction = self._find_station_id_by_name(direction_name)
                    print(f"    Direction found: {direction_name} -> {direction}")

            if direction:
                entries = self._parse_schedule_table(table)
                print(f"    Found {len(entries)} entries")
                if entries:
                    # Determine day type from URL
                    day_type = DayType.WEEKDAY
                    if "vykhidni" in station_url.lower():
                        day_type = DayType.WEEKEND

                    schedules.append(
                        StationSchedule(
                            station_id=station_id,
                            direction_station_id=direction,
                            day_type=day_type,
                            entries=entries,
                        )
                    )
            else:
                debug_text = prev.get_text()[:100] if prev else "No header found"
                print(f"    Warning: Could not determine direction from text: {debug_text}")

        return schedules

    def _parse_schedule_table(self, table) -> list[ScheduleEntry]:
        """Parse schedule entries from HTML table."""
        entries = []
        rows = table.find_all("tr")

        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            # First cell should contain hour
            hour_text = cells[0].get_text(strip=True)
            hour_match = re.match(r"(\d+):?", hour_text)
            if not hour_match:
                continue

            try:
                hour = int(hour_match.group(1))
            except ValueError:
                continue

            # Remaining cells contain minutes
            for cell in cells[1:]:
                minute_text = cell.get_text(strip=True)
                if not minute_text or minute_text == "&nbsp;":
                    continue

                # Extract number from text (might have * for last trains)
                minute_match = re.search(r"(\d+)", minute_text)
                if minute_match:
                    try:
                        minutes = int(minute_match.group(1))
                        if 0 <= minutes < 60:
                            entries.append(ScheduleEntry(hour=hour, minutes=minutes))
                    except ValueError:
                        continue

        return entries

    def _find_station_id_by_name(self, name: str) -> str | None:
        """Find station ID by Ukrainian name."""
        name_lower = name.lower().strip()

        # Try exact match first
        if name_lower in _STATION_NAME_TO_ID:
            return _STATION_NAME_TO_ID[name_lower]

        # Try with normalized name (remove quotes, etc)
        normalized = name_lower.replace("'", "").replace("«", "").replace("»", "").strip()
        if normalized in _STATION_NAME_TO_ID:
            return _STATION_NAME_TO_ID[normalized]

        # Try partial match
        for station_name, station_id in _STATION_NAME_TO_ID.items():
            if name_lower in station_name or station_name in name_lower:
                return station_id

        # Debug: print what we couldn't find
        print(f"      Could not find station ID for: '{name}'")
        return None

    def scrape_all_schedules(self) -> dict[str, list[StationSchedule]]:
        """Scrape all schedules for all lines and day types."""
        all_schedules: dict[str, list[StationSchedule]] = {}

        for day_type in [DayType.WEEKDAY, DayType.WEEKEND]:
            for line_slug in ["kholodnohirsko_zavodska", "saltivska", "oleksiivska"]:
                print(f"Scraping {line_slug} for {day_type.value}...")

                stations = self.fetch_line_stations(line_slug, day_type)

                for station in stations:
                    station_id = station["id"]
                    print(f"  Fetching schedule for {station['name']}...")

                    schedules = self.fetch_station_schedule(station["url"], station_id)

                    if station_id not in all_schedules:
                        all_schedules[station_id] = []
                    all_schedules[station_id].extend(schedules)

        return all_schedules
