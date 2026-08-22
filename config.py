"""
config.py

Global configuration for the Movie Calendar project.
"""

import os
from pathlib import Path

# ============================================================
# Project directories
# ============================================================

ROOT = Path(__file__).resolve().parent

FETCHERS_DIR = ROOT / "fetchers"

CACHE_DIR = ROOT / "cache"

DOCS_DIR = ROOT / "docs"

CACHE_DIR.mkdir(exist_ok=True)

DOCS_DIR.mkdir(exist_ok=True)

# ============================================================
# Generated files
# ============================================================

MOVIES_JSON = DOCS_DIR / "movies.json"

OMDB_CACHE = CACHE_DIR / "omdb_cache.json"

# ============================================================
# API Keys
# ============================================================

OMDB_API_KEY = os.getenv("OMDB_API_KEY")

TMS_API_KEY = os.getenv("TMS_API_KEY")

# ============================================================
# API Endpoints
# ============================================================

OMDB_BASE_URL = "https://www.omdbapi.com/"

# Both Brooklyn theaters ARE in TMS/Gracenote's theatre database (unlike
# Sidewalk in the Birmingham version of this project) -- confirmed live via
# GET http://data.tmsapi.com/v1.1/movies/showings?zip=11217&radius=20 --
# but TMS's showtime data has no purchase URL and no sold-out status, so it
# isn't used as the showtime source. Instead it's used as an *enrichment*
# pass (see fetchers/tms.py): one call gives real catalog metadata (full
# cast, directors, MPAA rating, synopsis) for both theaters at once, filled
# in before the OMDb fallback.
TMS_BASE_URL = "http://data.tmsapi.com/v1.1"
TMS_ZIP = "11217"
TMS_RADIUS = 20
TMS_NUM_DAYS = 30
TMS_ALAMO_THEATRE_ID = "11303"
TMS_BAM_THEATRE_ID = "2576"

# Alamo Drafthouse's own website is a client-rendered app that calls a
# public JSON API (the same one its own SPA uses -- found by inspecting
# the site's JS bundle for network calls; confirmed live, no API key
# required). This is the showtime source for Alamo: it returns every
# upcoming presentation/session for a cinema in one shot, including real
# ticket purchase URLs, live sold-out status, and exact formats (70mm,
# HDR by Barco, ...) that TMS's syndicated data doesn't carry.
ALAMO_BASE_URL = "https://drafthouse.com"
ALAMO_MARKET_SLUG = "nyc"
ALAMO_CINEMA_ID = "2101"
ALAMO_CINEMA_SLUG = "downtown-brooklyn"

# BAM Rose Cinemas has no public showtime API, so showtimes are scraped
# from bam.org directly (see fetchers/bam.py for the approach: BAM renders
# a schema.org Event JSON-LD block -- with a real ticket purchase URL --
# on each film's detail page whenever it has bookable showtimes). Only the
# films currently listed on the main listing grid are checked, plus any
# per-film pages a repertory series hub in that grid links out to (not
# BAM's much larger archive of past/catalog title pages also linked from
# the listing page), which keeps this to several dozen requests per run
# rather than the ~110 a full crawl of every /film/ link would take.
BAM_BASE_URL = "https://www.bam.org"
BAM_FILM_LISTING_URL = "https://www.bam.org/film"
BAM_REQUEST_DELAY = 0.3
BAM_MAX_PAGES = 80  # safety ceiling on total pages checked per run

# ============================================================
# Request settings
# ============================================================

REQUEST_TIMEOUT = 30

USER_AGENT = (
    "MovieCalendar/1.0 "
    "(https://github.com/yourusername/movie-calendar)"
)

OMDB_DELAY = 0.25

# ============================================================
# Brooklyn Theaters
# ============================================================

ALAMO_THEATER = {
    "name": "Alamo Drafthouse Brooklyn",
    "city": "Brooklyn",
}

BAM_THEATER = {
    "name": "BAM Rose Cinemas",
    "city": "Brooklyn",
}

TARGET_THEATERS = [
    ALAMO_THEATER["name"],
    BAM_THEATER["name"],
]

# ============================================================
# OMDb fields
# ============================================================

OMDB_RATINGS = {
    "Internet Movie Database": "imdb",
    "Rotten Tomatoes": "rotten",
    "Metacritic": "metacritic",
}

# ============================================================
# Helpers
# ============================================================

def require_api_key(name: str) -> str:
    """
    Raises a helpful exception if an API key is missing.
    """

    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"{name} environment variable is not set."
        )

    return value


def get_omdb_key() -> str:
    return require_api_key("OMDB_API_KEY")


def get_tms_key() -> str:
    return require_api_key("TMS_API_KEY")
