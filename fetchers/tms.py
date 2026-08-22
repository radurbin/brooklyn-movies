"""
fetchers/tms.py

Enriches Movie objects with catalog metadata from the Gracenote/TMS API
(data.tmsapi.com).

Unlike fetchers/alamo.py and fetchers/bam.py, this isn't a showtime
source -- TMS's showtime objects carry no purchase URL and no sold-out
status, so real showtimes still come from Alamo's own API and BAM's site.
What TMS gives instead is official catalog data (full cast, directors,
MPAA rating, synopsis, runtime) for both theaters in a single call,
confirmed live via:

    GET http://data.tmsapi.com/v1.1/movies/showings?zip=11217&radius=20

filtered down to entries with a showtime at theatre id 11303 (Alamo
Drafthouse Brooklyn) or 2576 (BAM Rose Cinemas).

This runs as an enrichment pass before OMDb, and -- like OMDb -- only
fills fields a fetcher didn't already supply.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional

import requests

from config import (
    REQUEST_TIMEOUT,
    TMS_ALAMO_THEATRE_ID,
    TMS_BAM_THEATRE_ID,
    TMS_BASE_URL,
    TMS_NUM_DAYS,
    TMS_RADIUS,
    TMS_ZIP,
    get_tms_key,
)

from models import Movie

RUNTIME_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?$")


def normalize_title(title: str) -> str:
    if not title:
        return ""
    s = title.lower().strip()
    for prefix in ("the ", "a ", "an "):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return " ".join(s.split())


def parse_runtime(run_time: Optional[str]) -> Optional[int]:
    if not run_time:
        return None

    m = RUNTIME_RE.match(run_time)
    if not m:
        return None

    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)

    return (hours * 60 + minutes) or None


class TMSFetcher:
    """Enriches movies with Gracenote/TMS catalog metadata."""

    theatre_ids = {TMS_ALAMO_THEATRE_ID, TMS_BAM_THEATRE_ID}

    def __init__(self):
        self.api_key = get_tms_key()
        self._by_title: Optional[Dict[str, dict]] = None

    # --------------------------------------------------
    # HTTP helper
    # --------------------------------------------------

    def _fetch_showings(self) -> list:
        response = requests.get(
            f"{TMS_BASE_URL}/movies/showings",
            params={
                "api_key": self.api_key,
                "zip": TMS_ZIP,
                "radius": TMS_RADIUS,
                "startDate": date.today().isoformat(),
                "numDays": TMS_NUM_DAYS,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def _load(self) -> Dict[str, dict]:
        if self._by_title is not None:
            return self._by_title

        by_title: Dict[str, dict] = {}

        for entry in self._fetch_showings():
            theatre_ids = {
                st.get("theatre", {}).get("id")
                for st in entry.get("showtimes", [])
            }

            if not theatre_ids & self.theatre_ids:
                continue

            key = normalize_title(entry.get("title", ""))
            if key:
                by_title[key] = entry

        self._by_title = by_title

        print(f"  Loaded TMS metadata for {len(by_title)} titles at our theaters.")

        return by_title

    # --------------------------------------------------
    # Enrichment
    # --------------------------------------------------

    def enrich_movie(self, movie: Movie) -> Movie:
        entry = self._load().get(normalize_title(movie.title))
        if entry is None:
            return movie

        if not movie.plot:
            movie.plot = entry.get("longDescription") or entry.get("shortDescription")

        if not movie.short_description:
            movie.short_description = entry.get("shortDescription")

        if not movie.genres:
            movie.genres = entry.get("genres") or []

        if not movie.actors:
            movie.actors = entry.get("topCast") or []

        if not movie.directors:
            movie.directors = entry.get("directors") or []

        if not movie.rating:
            for r in entry.get("ratings", []):
                if r.get("body") == "Motion Picture Association":
                    movie.rating = r.get("code")
                    break

        if not movie.runtime:
            movie.runtime = parse_runtime(entry.get("runTime"))

        if not movie.release_year:
            movie.release_year = entry.get("releaseYear")

        if not movie.website:
            movie.website = entry.get("officialUrl")

        return movie

    def enrich(self, movies: List[Movie]) -> List[Movie]:
        for movie in movies:
            self.enrich_movie(movie)
        return movies
