# Movie Calendar — Brooklyn

This folder builds a static movie showtimes site suitable for GitHub Pages.

Overview
- The Python backend fetches showtimes from Alamo Drafthouse Brooklyn's public JSON API (`fetchers/alamo.py`) and by scraping BAM Rose Cinemas' public film pages (`fetchers/bam.py`), enriches metadata using the Gracenote/TMS API (`fetchers/tms.py`), OMDb (`fetchers/omdb.py`), and Letterboxd ratings (`fetchers/letterboxd.py`), downloads poster images into `docs/posters/`, and writes `docs/movies.json` consumed by the frontend (`docs/index.html`).

Quick local preview

1. Install dependencies (recommended in a virtualenv):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Export API keys locally (example):

```bash
export OMDB_API_KEY=your_omdb_key
export TMS_API_KEY=your_tms_key
```

3. Run the pipeline to generate `docs/movies.json` and download posters:

```bash
python fetch_movies.py
```

4. Preview the generated site:

```bash
python3 -m http.server --directory docs 8000
# Open http://localhost:8000 in your browser
```

GitHub Pages setup (repo-level)

- This project expects a `docs/` folder at the repository root containing `index.html`, `movies.json`, and `posters/`.
- When you push this folder as the repository root, enable GitHub Pages in the repository Settings → Pages and select `main` (or the branch you use) and the `/docs` folder as the source.

Secrets (required for Actions)

Add the following repository secrets under Settings → Secrets & variables → Actions:

- `OMDB_API_KEY` — your OMDb API key
- `TMS_API_KEY` — your Gracenote/TMS API key (free-tier registration: https://developer.tmsapi.com/member/register)

Alamo and BAM showtimes don't need a key — Alamo is fetched from its own public JSON API and BAM is scraped directly from its site (see "Data sources and theaters" below). TMS is used for metadata enrichment only; a run without `TMS_API_KEY` set still works, it just relies on OMDb alone for enrichment.

CI / GitHub Actions

- A workflow file `.github/workflows/update.yml` is included. It runs 4 times a day (and can be triggered manually) to:
  1. Install dependencies (`requests`, `beautifulsoup4`).
  2. Run `python fetch_movies.py` which regenerates `docs/movies.json` and downloads missing posters into `docs/posters/`.
  3. Commit any changed files under `docs/` back to the repo so Pages serves the newest data.

Data sources and theaters

This project currently includes showtimes for two theaters:

- **Alamo Drafthouse Brooklyn** (Downtown Brooklyn, cinema id `2101`) — fetched from Alamo's own public "mother" API (`https://drafthouse.com/s/mother/v2/schedule/venue/2101`), the same endpoint their website's own app calls. No API key is required. Discovered by inspecting Alamo's site JS bundle for network call templates, then resolving the Brooklyn location's cinema id via `https://drafthouse.com/s/mother/v1/market/nyc`.
- **BAM Rose Cinemas** — scraped from `bam.org/film`. BAM has no public showtime API, so `fetchers/bam.py` collects the film detail page linked from each entry in the site's main listing grid (deliberately skipping a much larger "you might also like" archive grid also linked from that page, which mostly points at past titles with nothing currently on sale) and parses the schema.org `Event` JSON-LD block BAM embeds on any title with bookable showtimes -- including a real ticket purchase URL and price per showing. Some listing entries are repertory series hub pages (e.g. "Arthouse Sci-fi") rather than individual films; the fetcher follows those into their real per-film child pages too (found by cross-checking against TMS -- an early version missed these), bounded by `BAM_MAX_PAGES` as a safety ceiling. Only events at a location starting with "BAM Rose Cinemas" are kept, since BAM also uses the same markup for its Harvey Theater/opera house programming.

Both theaters also happen to be in the Gracenote/TMS theatre database (`fetchers/tms.py`, confirmed live via `GET http://data.tmsapi.com/v1.1/movies/showings?zip=11217&radius=20`), which is why this project uses TMS as a *metadata enrichment* pass rather than a showtime source: its showtime records have no purchase URL and no sold-out status, so real showtimes still come from Alamo's own API and BAM's site. What TMS adds is official catalog data -- full cast, directors, MPAA rating, and synopsis -- for both theaters in a single call, filled in before the OMDb fallback.

How far in the future is fetched

- Alamo's schedule endpoint returns whatever upcoming sessions it currently has on sale for the cinema.
- BAM's film pages list every showtime currently on sale for that title; only future showtimes are kept.
- TMS is queried for a 30-day window (`TMS_NUM_DAYS` in `config.py`) purely for metadata matching -- it doesn't limit which showtimes get published, since it isn't the showtime source.

Poster and movie data retention

- OMDb responses are cached in `cache/omdb_cache.json` by `fetchers/omdb.py` to avoid re-querying OMDb for unchanged titles. OMDb and TMS both only fill fields a fetcher didn't already supply -- TMS runs first (it has better cast/synopsis data for festival and arthouse titles OMDb sometimes lacks), then OMDb fills whatever's still missing (including IMDb/Rotten Tomatoes/Metacritic ratings, which TMS doesn't provide).
- Letterboxd ratings are cached in `cache/letterboxd_cache.json` by `fetchers/letterboxd.py`. Letterboxd has no public API, so each movie's page is found via its IMDb ID (`letterboxd.com/imdb/{imdb_id}/`, which redirects to the film page) and the rating is read out of that page's embedded JSON-LD. This only works for movies OMDb already resolved an `imdb_id` for; Letterboxd's own search page 403s scripted requests, so there's no title-based fallback for movies OMDb missed.
- Posters always come from Alamo/BAM/OMDb, never TMS -- TMS's image URLs require the API key as a query parameter, and baking that into `movies.json` would leak it publicly on GitHub Pages if a poster download ever failed partway through a run.
- Posters are downloaded into `docs/posters/`. The pipeline avoids re-downloading posters that already exist (it checks file presence by filename).
- After each run the pipeline removes stale poster files: any files in `docs/posters/` not referenced by the newly generated `movies.json` are deleted.

Scheduling and frequency

- The default workflow runs 4 times a day (see `.github/workflows/update.yml`). You can change the cron schedule in that file or trigger the workflow manually from the Actions tab.

Security and secrets

- Never commit API keys. Use GitHub repository secrets for Actions and local environment variables for local testing.

Troubleshooting

- If Actions fails due to a missing key, confirm `OMDB_API_KEY` is set in the repository secrets (`TMS_API_KEY` is optional -- its absence only disables the TMS enrichment pass, logged as a warning, not a failure).
- If Alamo's fetch starts failing, their `/s/mother/v2/schedule/venue/{cinemaId}` endpoint or cinema id may have changed -- re-check via `https://drafthouse.com/s/mother/v1/market/nyc`.
- If BAM's fetch starts returning fewer movies than expected, their listing page markup or JSON-LD structure may have changed -- inspect a current film's detail page source for the `application/ld+json` block.

Next improvements (suggested)

- Add image resizing/optimization to generate thumbnails and medium sizes for faster page loads.
- Add test coverage for stale-poster removal behavior.
