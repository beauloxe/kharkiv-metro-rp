"""Web scraper for Kharkiv metro schedule."""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from urllib.parse import unquote, urljoin

import aiohttp
from bs4 import BeautifulSoup

from .models import DayType, ScheduleEntry, StationSchedule, create_stations

BASE_URL = "https://www.metro.kharkiv.ua"

# Build station name to ID mapping
_STATION_NAME_TO_ID: dict[str, str] = {}
for sid, station in create_stations().items():
    _STATION_NAME_TO_ID[station.name_ua.lower()] = sid
    # Also add normalized versions
    normalized = station.name_ua.lower().replace("'", "").replace(" «", "").replace("» ", "")
    _STATION_NAME_TO_ID[normalized] = sid

# Additional mappings for renamed stations (weekend schedules)
_STATION_NAME_TO_ID["героїв праці"] = "saltivska"  # Former "Героїв праці"
_STATION_NAME_TO_ID["пушкінська"] = "yaroslava_mudroho"  # Former "Пушкінська"
_STATION_NAME_TO_ID["проспект гагаріна"] = "levada"  # Former "Проспект Гагаріна"

# Alternative names for stations
_STATION_NAME_TO_ID["академіка барабашова"] = "barabashova"
_STATION_NAME_TO_ID["барабашова"] = "barabashova"
_STATION_NAME_TO_ID["академіка павлова"] = "pavlova"
_STATION_NAME_TO_ID["павлова"] = "pavlova"

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
        "beketova": "stantsiia-%C2%ABakrkhitektokra-beketova%C2%BB.html",  # typo: akrkhitektokra
        "derzhprom": "stantsiia-%C2%ABdekrzhpkrom%C2%BB.html",  # typo: dekrzhpkrom
        "naukova": "stantsiia-%C2%ABnaukova%C2%BB.html",
        "botanichnyi_sad": "stantsiia-%C2%ABbotanichnyi-sad%C2%BB.html",
        "23_serpnia": "stantsiia-%C2%AB23-sekrpnia%C2%BB.html",  # typo: sekrpnia
        "oleksiivska": "stantsiia-%C2%ABoleksiivska%C2%BB.html",
        "peremoha": "stantsiia-%C2%ABpekremoha%C2%BB.html",  # typo: pekremoha
    },
    DayType.WEEKEND: {
        "metrobudivnykiv": "stantsiia-%C2%ABmetkrobudivnykiv%C2%BB-(vykhidni-dni).html",
        "zakhysnykiv_ukrainy": "stantsiia-%C2%ABzakhysnykiv-ukkrainy%C2%BB-(vykhidni-dni).html",
        "beketova": "stantsiia-%C2%ABakrkhitektokra-beketova%C2%BB-(vykhidni-dni).html",
        "derzhprom": "stantsiia-%C2%ABdekrzhpkrom%C2%BB-(vykhidni-dni).html",
        "naukova": "stantsiia-%C2%ABnaukova%C2%BB-(vykhidni-dni).html",
        "botanichnyi_sad": "stantsiia-%C2%ABbotanichnyi-sad%C2%BB-(vykhidni-dni).html",
        "23_serpnia": "stantsiia-%C2%AB23-sekrpnia%C2%BB-(vykhidni-dni).html",
        "oleksiivska": "stantsiia-%C2%ABoleksiivska%C2%BB-(vykhidni-dni).html",
        "peremoha": "stantsiia-%C2%ABpekremoha%C2%BB-(vykhidni-dni).html",
    },
}

# Station names mapping
STATION_NAMES = {
    "metrobudivnykiv": "Метробудівників",
    "zakhysnykiv_ukrainy": "Захисників України",
    "beketova": "Архітектора Бекетова",
    "derzhprom": "Держпром",
    "naukova": "Наукова",
    "botanichnyi_sad": "Ботанічний сад",
    "23_serpnia": "23 Серпня",
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
    "im.-o.s.-maselskoho": "maselskoho",
    "tkraktokrnyi-zavod": "traktornyi_zavod",
    "industkrialna": "industrialna",
    # Line 2
    "istokrychnyi-muzei": "istorychnyi_muzei",
    "universytet": "university",
    "univekrsytet": "university",  # Typo in weekend URL
    "pushkinska": "yaroslava_mudroho",
    "yakroslava-mudkroho": "yaroslava_mudroho",  # New name on weekend
    "kyivska": "kyivska",
    "akademika-bakrabashova": "barabashova",
    "akademika-pavlova": "pavlova",
    "studentska": "studentska",
    "heroiv-praci": "saltivska",
    "saltivska": "saltivska",  # New name on weekend
    # Line 3
    "metrobudivnykiv": "metrobudivnykiv",
    "metkrobudivnykiv": "metrobudivnykiv",  # typo version
    "zakhysnykiv-ukrainy": "zakhysnykiv_ukrainy",
    "zakhysnykiv-ukkrainy": "zakhysnykiv_ukrainy",  # typo version
    "akrkhitektokra-beketova": "beketova",  # typo version
    "derzhprom": "derzhprom",
    "dekrzhpkrom": "derzhprom",  # typo version
    "nauky": "naukova",
    "naukova": "naukova",  # alternative name
    "botanichnyi-sad": "botanichnyi_sad",
    "23-serpnia": "23_serpnia",
    "23-sekrpnia": "23_serpnia",  # typo version
    "oleksiivska": "oleksiivska",
    "peremoha": "peremoha",
    "pekremoha": "peremoha",  # typo version
}


class AsyncMetroScraper:
    """Async scraper for Kharkiv metro schedules with concurrency control."""

    def __init__(self, max_concurrent: int = 10, timeout: int = 30) -> None:
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    async def _fetch(self, session: aiohttp.ClientSession, url: str) -> str | None:
        """Fetch URL with semaphore-controlled concurrency."""
        async with self.semaphore:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=self.timeout)) as response:
                    response.raise_for_status()
                    return await response.text()
            except aiohttp.ClientError as e:
                print(f"Error fetching {url}: {e}")
                return None

    async def fetch_line_stations(
        self, session: aiohttp.ClientSession, line_slug: str, day_type: DayType
    ) -> list[dict]:
        """Fetch station URLs for a line."""
        url = urljoin(BASE_URL, LINE_URLS[day_type][line_slug])
        html = await self._fetch(session, url)

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
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

    async def fetch_station_schedule(
        self, session: aiohttp.ClientSession, station_url: str, station_id: str
    ) -> list[StationSchedule]:
        """Fetch schedule for a single station."""
        html = await self._fetch(session, station_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        schedules = []

        # Find schedule tables
        tables = soup.find_all("table")

        for table in tables:
            # Try to determine direction from preceding header
            prev = table.find_previous(["h3", "h4", "h5"])
            if not prev:
                prev = table.find_previous("strong")
            direction = None

            if prev:
                text = prev.get_text()
                # Extract direction station name from header
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

    @lru_cache(maxsize=128)
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

    async def scrape_all_schedules(self) -> dict[str, list[StationSchedule]]:
        """Scrape all schedules for all lines and day types concurrently."""
        all_schedules: dict[str, list[StationSchedule]] = {}

        async with aiohttp.ClientSession(headers=self.headers) as session:
            # First, fetch all stations for all lines concurrently
            station_tasks = []
            for day_type in [DayType.WEEKDAY, DayType.WEEKEND]:
                for line_slug in ["kholodnohirsko_zavodska", "saltivska", "oleksiivska"]:
                    task = self.fetch_line_stations(session, line_slug, day_type)
                    station_tasks.append((day_type, line_slug, task))

            # Gather all station lists
            station_results = await asyncio.gather(*[t[2] for t in station_tasks], return_exceptions=True)

            # Collect all stations to fetch schedules for
            schedule_tasks = []
            for (day_type, line_slug, _), stations in zip(station_tasks, station_results, strict=False):
                if isinstance(stations, Exception):
                    print(f"Error fetching {line_slug} for {day_type}: {stations}")
                    continue

                print(f"Scraping {line_slug} for {day_type.value}... ({len(stations)} stations)")

                for station in stations:
                    station_id = station["id"]
                    print(f"  Queuing schedule for {station['name']}...")

                    task = self.fetch_station_schedule(session, station["url"], station_id)
                    schedule_tasks.append((station_id, task))

            # Fetch all schedules concurrently with semaphore control
            schedule_results = await asyncio.gather(*[t[1] for t in schedule_tasks], return_exceptions=True)

            # Collect results
            for (station_id, _), schedules in zip(schedule_tasks, schedule_results, strict=False):
                if isinstance(schedules, Exception):
                    print(f"Error fetching schedule for {station_id}: {schedules}")
                    continue

                if station_id not in all_schedules:
                    all_schedules[station_id] = []
                all_schedules[station_id].extend(schedules)

        return all_schedules


# Backward compatibility: synchronous wrapper
class MetroScraper:
    """Synchronous wrapper for backward compatibility."""

    def __init__(self, max_concurrent: int = 10, timeout: int = 30) -> None:
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    def _fetch(self, url: str) -> str | None:
        """Fetch URL synchronously."""
        import requests

        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def fetch_line_stations(self, line_slug: str, day_type: DayType) -> list[dict]:
        """Fetch station URLs for a line."""
        url = urljoin(BASE_URL, LINE_URLS[day_type][line_slug])
        html = self._fetch(url)

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        stations = []

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
        href = unquote(href)

        match = re.search(r'stantsiia-[«"]?([^"»]+?)["»]?(?:-\(?(?:vykhidni-dni)\)?)?\.html', href)
        if match:
            slug = match.group(1)
            return slug.lower()

        return ""

    def fetch_station_schedule(self, station_url: str, station_id: str) -> list[StationSchedule]:
        """Fetch schedule for a single station."""
        html = self._fetch(station_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        schedules = []

        tables = soup.find_all("table")

        for table in tables:
            prev = table.find_previous(["h3", "h4", "h5"])
            if not prev:
                prev = table.find_previous("strong")
            direction = None

            if prev:
                text = prev.get_text()
                match = re.search(r'[«"]([^»"]+)[»"]', text)
                if match:
                    direction_name = match.group(1)
                    direction = self._find_station_id_by_name(direction_name)
                    print(f"    Direction found: {direction_name} -> {direction}")

            if direction:
                entries = self._parse_schedule_table(table)
                print(f"    Found {len(entries)} entries")
                if entries:
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

            hour_text = cells[0].get_text(strip=True)
            hour_match = re.match(r"(\d+):?", hour_text)
            if not hour_match:
                continue

            try:
                hour = int(hour_match.group(1))
            except ValueError:
                continue

            for cell in cells[1:]:
                minute_text = cell.get_text(strip=True)
                if not minute_text or minute_text == "&nbsp;":
                    continue

                minute_match = re.search(r"(\d+)", minute_text)
                if minute_match:
                    try:
                        minutes = int(minute_match.group(1))
                        if 0 <= minutes < 60:
                            entries.append(ScheduleEntry(hour=hour, minutes=minutes))
                    except ValueError:
                        continue

        return entries

    @lru_cache(maxsize=128)
    def _find_station_id_by_name(self, name: str) -> str | None:
        """Find station ID by Ukrainian name."""
        name_lower = name.lower().strip()

        if name_lower in _STATION_NAME_TO_ID:
            return _STATION_NAME_TO_ID[name_lower]

        normalized = name_lower.replace("'", "").replace("«", "").replace("»", "").strip()
        if normalized in _STATION_NAME_TO_ID:
            return _STATION_NAME_TO_ID[normalized]

        for station_name, station_id in _STATION_NAME_TO_ID.items():
            if name_lower in station_name or station_name in name_lower:
                return station_id

        print(f"      Could not find station ID for: '{name}'")
        return None

    def _fetch_station_schedule_task(self, station: dict) -> tuple[str, list[StationSchedule]]:
        """Task for fetching a single station schedule."""
        station_id = station["id"]
        schedules = self.fetch_station_schedule(station["url"], station_id)
        return station_id, schedules

    def scrape_all_schedules(self) -> dict[str, list[StationSchedule]]:
        """Scrape all schedules for all lines and day types with concurrency."""
        all_schedules: dict[str, list[StationSchedule]] = {}

        # Collect all stations first
        all_stations: list[tuple[DayType, str, list[dict]]] = []
        for day_type in [DayType.WEEKDAY, DayType.WEEKEND]:
            for line_slug in ["kholodnohirsko_zavodska", "saltivska", "oleksiivska"]:
                print(f"Fetching station list for {line_slug} ({day_type.value})...")
                stations = self.fetch_line_stations(line_slug, day_type)
                all_stations.append((day_type, line_slug, stations))

        # Flatten stations list for concurrent processing
        stations_to_fetch: list[tuple[str, dict]] = []
        for day_type, line_slug, stations in all_stations:
            print(f"Scraping {line_slug} for {day_type.value}... ({len(stations)} stations)")
            for station in stations:
                stations_to_fetch.append((station["id"], station))

        # Fetch all schedules concurrently using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            future_to_station = {
                executor.submit(self._fetch_station_schedule_task, station): (station_id, station)
                for station_id, station in stations_to_fetch
            }

            for future in as_completed(future_to_station):
                station_id, station = future_to_station[future]
                try:
                    _, schedules = future.result()
                    print(f"  Fetched schedule for {station['name']}: {len(schedules)} directions")
                    if station_id not in all_schedules:
                        all_schedules[station_id] = []
                    all_schedules[station_id].extend(schedules)
                except Exception as e:
                    print(f"  Error fetching schedule for {station['name']}: {e}")

        return all_schedules
