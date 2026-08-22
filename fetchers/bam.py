"""
fetchers/bam.py

Scrapes showtimes for BAM Rose Cinemas from bam.org.

BAM has no public showtime API, so showtimes are scraped directly from
BAM's own site.

Approach:
  1. Fetch the film listing page (bam.org/film) and collect the detail
     page link (`/film/{year}/{slug}`) out of each "productionblock" div
     that carries a `data-sort-title` attribute -- that's how the current
     listing grid's own sort buttons (view by month/genre) address a
     block, so its presence (regardless of value) marks a block as
     belonging to the current listing rather than the much larger "you
     might also like" archive grid also linked from that page (~100
     further titles, mostly past screenings, whose productionblock divs
     carry no data-sort-* attributes at all). Note this deliberately does
     NOT filter on `data-sort-genre="Film"` specifically -- repertory
     series hubs (see step 3) are also part of the current listing grid
     but carry `data-sort-genre=""`, and filtering on that value alone
     silently dropped them along with the archive.
  2. Fetch each film's detail page and parse its embedded schema.org
     `Event` JSON-LD block, which carries the real ticket purchase URL
     and price per showtime.
  3. Some listing-grid entries are repertory *series* hub pages (e.g.
     "Arthouse Sci-fi"), not individual films -- they carry no Event
     JSON-LD of their own, only links to one detail page per film in the
     series. Confirmed by cross-checking against TMS/Gracenote's showings
     for BAM: TMS knew about several films (Solaris, Stalker, eXistenZ,
     ...) that an early version of this scraper silently missed. Every
     series' child pages share its slug as a prefix
     (`arthouse-scifi-solaris`, `arthouse-scifi-stalker`, ...), which is
     what `_child_paths` follows -- bounded by `BAM_MAX_PAGES` as a
     safety ceiling on total pages checked per run (currently landing
     around 60-70 in practice, well under the ~110 a full unfiltered
     crawl of the archive grid too would take).
  4. Keep only events whose location name starts with "BAM Rose Cinemas"
     -- BAM also uses the same Event markup for its Harvey Theater/opera
     house programming under a different location name, so this keeps
     film screenings only.
  5. Drop any event whose start time has already passed, as an extra
     guard against stale data.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from config import (
    BAM_BASE_URL,
    BAM_FILM_LISTING_URL,
    BAM_MAX_PAGES,
    BAM_REQUEST_DELAY,
    BAM_THEATER,
    REQUEST_TIMEOUT,
)

from models import Movie, Showtime

FILM_PATH_RE = re.compile(r"^/film/\d{4}/([a-z0-9-]+)$")

LD_JSON_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>',
    re.DOTALL,
)


class BAMFetcher:
    """Scrapes BAM Rose Cinemas showtimes from bam.org."""

    def __init__(self):
        self.theater_name = BAM_THEATER["name"]

    # --------------------------------------------------
    # HTTP helper
    # --------------------------------------------------

    def _fetch(self, url: str) -> str:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.text

    # --------------------------------------------------
    # Listing page
    # --------------------------------------------------

    def _list_film_paths(self) -> List[str]:
        html = self._fetch(BAM_FILM_LISTING_URL)
        soup = BeautifulSoup(html, "html.parser")

        paths = []
        seen = set()

        # The "you might also like" archive grid reuses the same
        # productionblock class but omits data-sort-title entirely --
        # it's how the current listing grid's own sort buttons (view by
        # month/genre) address a block, so its presence (regardless of
        # value) reliably marks a block as belonging to the current
        # listing rather than the archive. Deliberately NOT filtering by
        # data-sort-genre="Film" here: repertory series hubs are also
        # part of this listing grid but carry data-sort-genre="" -- this
        # was confirmed missing series like "Arthouse Sci-fi" (and the
        # real per-film showtimes inside it) when checked against TMS.
        for block in soup.find_all("div", class_="productionblock", attrs={"data-sort-title": True}):
            a = block.find("a", href=FILM_PATH_RE)
            if a and a["href"] not in seen:
                seen.add(a["href"])
                paths.append(a["href"])

        return paths

    # --------------------------------------------------
    # Detail page parsing
    # --------------------------------------------------

    @staticmethod
    def _parse_events(html: str) -> List[dict]:
        events = []

        for match in LD_JSON_RE.finditer(html):
            try:
                payload = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

            graph = payload.get("graph") or [payload]

            for node in graph:
                if node.get("@type") == "Event":
                    events.append(node)

        return events

    @staticmethod
    def _title(soup: BeautifulSoup) -> Optional[str]:
        tag = soup.find("meta", attrs={"property": "og:title"})
        if tag and tag.get("content"):
            return tag["content"].strip()
        return None

    @staticmethod
    def _child_paths(html: str, parent_path: str) -> List[str]:
        """
        Series hub pages link to one detail page per film in the series,
        each sharing the hub's slug as a prefix. Only these are followed
        -- not every /film/ link on the page -- so a normal single-film
        page's "you might also like" widget doesn't pull in unrelated
        titles.
        """
        parent_slug = parent_path.rstrip("/").rsplit("/", 1)[-1]
        prefix = f"{parent_slug}-"

        children = []
        seen = set()

        for href in re.findall(r'href="(/film/\d{4}/[a-z0-9-]+)"', html):
            slug = href.rsplit("/", 1)[-1]
            if slug.startswith(prefix) and href not in seen:
                seen.add(href)
                children.append(href)

        return children

    def _parse_film_page(self, path: str) -> Tuple[Optional[Movie], List[str]]:
        html = self._fetch(f"{BAM_BASE_URL}{path}")

        events = [
            e for e in self._parse_events(html)
            if (e.get("location") or {}).get("name", "").startswith(self.theater_name)
        ]

        if not events:
            # No Event markup on this page at all -- either nothing is
            # currently on sale for this title, or it's a series hub
            # page. Either way, check for series children before giving
            # up on it.
            return None, self._child_paths(html, path)

        soup = BeautifulSoup(html, "html.parser")
        title = self._title(soup)
        if not title:
            return None, []

        movie = Movie(
            source="BAM",
            title=title,
            poster=events[0].get("image"),
            plot=events[0].get("description"),
            movie_url=f"{BAM_BASE_URL}{path}",
        )

        now = datetime.now(timezone.utc)

        for event in events:
            start = event.get("startDate")
            if not start:
                continue

            try:
                start_dt = datetime.fromisoformat(start)
            except ValueError:
                continue

            if start_dt < now:
                continue

            offer = event.get("offers") or {}
            purchase_url = offer.get("url")

            movie.add_showtime(Showtime(
                source="BAM",
                theater_id=0,
                theater=self.theater_name,
                showtime_id=self._showtime_id(purchase_url),
                datetime=start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                datetime_utc=start_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                purchase_url=purchase_url,
                sold_out="soldout" in (offer.get("availability") or "").lower(),
            ))

        return (movie, []) if movie.showtimes else (None, [])

    @staticmethod
    def _showtime_id(url: Optional[str]) -> int:
        if not url:
            return 0
        m = re.search(r"(\d+)$", url)
        return int(m.group(1)) if m else 0

    # --------------------------------------------------
    # Public method
    # --------------------------------------------------

    def fetch_movies(self) -> List[Movie]:
        queue = list(self._list_film_paths())
        visited = set()

        movies: List[Movie] = []
        checked = 0

        while queue and checked < BAM_MAX_PAGES:
            path = queue.pop(0)
            if path in visited:
                continue
            visited.add(path)

            if checked:
                time.sleep(BAM_REQUEST_DELAY)

            try:
                movie, children = self._parse_film_page(path)
            except Exception as ex:
                print(f"  BAM: failed to fetch {path}: {ex}")
                movie, children = None, []

            checked += 1

            if movie is not None:
                movies.append(movie)
            else:
                queue.extend(c for c in children if c not in visited)

        print(f"  Found {len(movies)} BAM Rose Cinemas movies across {checked} pages checked.")

        return movies
