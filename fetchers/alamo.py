"""
fetchers/alamo.py

Fetches showtimes for Alamo Drafthouse Brooklyn.

Alamo Drafthouse isn't in TMS/Gracenote's theatre database, but its own
website is a client-rendered app that calls a public JSON API -- found by
downloading the site's JS bundle (sspa.prod.aws.drafthouse.com) and
grepping it for network call templates. The relevant one:

    GET https://drafthouse.com/s/mother/v2/schedule/venue/{cinemaId}

This is the same endpoint drafthouse.com's own SPA calls to render a
cinema's showtimes page. No API key is required. It returns every
upcoming "presentation" (a movie/format/event pairing, e.g. "Dune: Part
Three in 70mm") and every "session" (one bookable showtime) for the
cinema in a single response.

Alamo Drafthouse Brooklyn's cinema id (2101) and slug (downtown-brooklyn)
were found via the market lookup endpoint:

    GET https://drafthouse.com/s/mother/v1/market/nyc
"""

from __future__ import annotations

from typing import Dict, List, Optional

import requests

from config import (
    ALAMO_BASE_URL,
    ALAMO_CINEMA_ID,
    ALAMO_MARKET_SLUG,
    ALAMO_THEATER,
    REQUEST_TIMEOUT,
)

from models import Movie, Showtime

# Sessions whose format is plain digital projection don't get a
# premium_format label -- everything else (70mm, HDR by Barco, Open
# Caption, ...) does, using the human-readable title Alamo itself uses.
STANDARD_FORMAT_SLUGS = {"2d-digital"}


class AlamoFetcher:
    """Fetches and normalizes Alamo Drafthouse Brooklyn showtime data."""

    def __init__(self):
        self.theater_name = ALAMO_THEATER["name"]

    # --------------------------------------------------
    # HTTP helper
    # --------------------------------------------------

    def _get_schedule(self) -> dict:
        response = requests.get(
            f"{ALAMO_BASE_URL}/s/mother/v2/schedule/venue/{ALAMO_CINEMA_ID}",
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["data"]

    # --------------------------------------------------
    # Parsing helpers
    # --------------------------------------------------

    @staticmethod
    def _poster(show: dict) -> Optional[str]:
        images = show.get("posterImages") or []
        return images[0].get("uri") if images else None

    @staticmethod
    def _movie_url(film_slug: str) -> str:
        return f"{ALAMO_BASE_URL}/{ALAMO_MARKET_SLUG}/show/{film_slug}"

    @staticmethod
    def _purchase_url(presentation_slug: str, session_id: str) -> str:
        return (
            f"{ALAMO_BASE_URL}/{ALAMO_MARKET_SLUG}/tickets/"
            f"{presentation_slug}/{ALAMO_CINEMA_ID}/{session_id}"
        )

    @staticmethod
    def _auditorium(session: dict) -> Optional[int]:
        screen = session.get("screenNumber")
        return int(screen) if screen and screen.isdigit() else None

    # --------------------------------------------------
    # Public method
    # --------------------------------------------------

    def fetch_movies(self) -> List[Movie]:
        data = self._get_schedule()

        presentations = {p["slug"]: p for p in data.get("presentations", [])}

        format_titles = {
            f["slug"]: f.get("title", f["slug"])
            for f in data.get("formats", [])
        }

        movies: Dict[str, Movie] = {}

        for session in data.get("sessions", []):
            if session.get("status") in ("PAST", "CANCELLED"):
                continue

            presentation = presentations.get(session["presentationSlug"])
            if presentation is None:
                continue

            show = presentation.get("show")
            if show is None:
                continue

            title = show["title"]

            movie = movies.get(title)
            if movie is None:
                movie = Movie(
                    source="Alamo",
                    title=title,
                    poster=self._poster(show),
                    movie_url=self._movie_url(show["slug"]),
                )
                movies[title] = movie

            format_slug = session.get("formatSlug")
            premium_format = (
                "Standard"
                if not format_slug or format_slug in STANDARD_FORMAT_SLUGS
                else format_titles.get(format_slug, format_slug)
            )

            movie.add_showtime(Showtime(
                source="Alamo",
                theater_id=int(ALAMO_CINEMA_ID),
                theater=self.theater_name,
                showtime_id=int(session["sessionId"]),
                datetime=session["showTimeClt"],
                datetime_utc=session.get("showTimeUtc"),
                auditorium=self._auditorium(session),
                premium_format=premium_format,
                purchase_url=self._purchase_url(presentation["slug"], session["sessionId"]),
                sold_out=session.get("status") == "SOLDOUT",
            ))

        result = list(movies.values())

        print(f"  Found {len(result)} Alamo Drafthouse Brooklyn movies.")

        return result
