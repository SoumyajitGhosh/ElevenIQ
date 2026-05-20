"""
agent/scrapers.py — All live data fetching lives here.

Each function is responsible for one source:
  fetch_player_fbref()      → FBref.com (player stats)
  fetch_formation_wiki()    → Wikipedia REST API (formations)
  fetch_role_wiki()         → Wikipedia REST API (tactical roles)

Keeping scraping logic separate from tools means:
  - Tools stay clean and readable
  - You can swap a scraper without touching tool signatures
  - Easy to unit-test scraping logic independently

Resilience patterns used here:
  - _get_with_retry()  : exponential backoff on 429 / 5xx responses
  - _cache             : in-memory TTL cache so the same request isn't
                         repeated within a session (no disk writes)
"""

import asyncio
import time

import httpx
from bs4 import BeautifulSoup

# ── Shared HTTP config ────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

REQUEST_TIMEOUT = 15.0  # seconds
MAX_RETRIES     = 3     # attempts before giving up
CACHE_TTL       = 300   # seconds (5 minutes) — how long cached results stay fresh


# ── In-memory session cache ───────────────────────────────────────────────────
#
# A plain dict mapping cache_key → (stored_at_timestamp, result_data).
# Nothing is written to disk. Everything lives in RAM and expires after
# CACHE_TTL seconds. This prevents hammering FBref when the user asks
# about the same player twice in one conversation.
#
# Structure: { "fbref:haaland": (1716000000.0, {...stats...}), ... }

_cache: dict[str, tuple[float, dict]] = {}


def _cache_get(key: str) -> dict | None:
    """Return cached value if it exists and hasn't expired, else None."""
    entry = _cache.get(key)
    if entry is None:
        return None
    stored_at, data = entry
    if time.monotonic() - stored_at > CACHE_TTL:
        del _cache[key]   # expired — evict it
        return None
    return data


def _cache_set(key: str, data: dict) -> None:
    """Store a result in the cache with the current timestamp."""
    _cache[key] = (time.monotonic(), data)


# ── Retry helper ──────────────────────────────────────────────────────────────
#
# Why exponential backoff?
# If FBref rate-limits us (429) or has a momentary server error (5xx),
# the right response is to wait a little and try again — not to fail
# immediately. Waiting 1s → 2s → 4s gives the server time to recover
# without hammering it further.

async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
) -> httpx.Response:
    """
    GET a URL with up to MAX_RETRIES attempts and exponential backoff.

    Retries on:
      429 Too Many Requests  — rate limited, back off and try again
      5xx Server Error       — transient server problem

    Raises httpx.HTTPStatusError on the final failed attempt.
    """
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(url)

            if resp.status_code in (429,) or resp.status_code >= 500:
                wait_seconds = 2 ** attempt          # 1s, 2s, 4s
                print(
                    f"  [scraper] HTTP {resp.status_code} on attempt {attempt + 1}. "
                    f"Retrying in {wait_seconds}s..."
                )
                await asyncio.sleep(wait_seconds)
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                )
                continue

            return resp   # success

        except httpx.RequestError as exc:
            last_exc = exc
            wait_seconds = 2 ** attempt
            print(f"  [scraper] Request error on attempt {attempt + 1}: {exc}. Retrying in {wait_seconds}s...")
            await asyncio.sleep(wait_seconds)

    raise last_exc


# ── FBref: Player Stats ───────────────────────────────────────────────────────

async def fetch_player_fbref(player_name: str) -> dict:
    """
    Search FBref for a player and return their most recent season stats.

    Checks the in-memory cache first. On a cache miss, fetches FBref
    (with retry logic) and caches the result before returning.

    FBref search either:
      (a) redirects straight to the player page  — one request
      (b) returns a search results page           — two requests

    Returns a dict with name, club, position, and key stats.
    On failure returns {"fallback": True} so the tool escalates to web search.
    """
    cache_key = f"fbref:{player_name.lower().strip()}"

    # ── Cache hit ─────────────────────────────────────────────────────────────
    cached = _cache_get(cache_key)
    if cached is not None:
        print(f"  [cache] HIT for '{player_name}'")
        return cached

    # ── Cache miss: fetch from FBref ──────────────────────────────────────────
    print(f"  [cache] MISS for '{player_name}' — fetching FBref...")
    encoded = player_name.strip().replace(" ", "+")
    search_url = f"https://fbref.com/search/search.fcgi?search={encoded}"

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, headers=HEADERS, timeout=REQUEST_TIMEOUT
        ) as client:
            resp = await _get_with_retry(client, search_url)
            soup = BeautifulSoup(resp.text, "lxml")

            # Case (a): redirected straight to a player page
            if "/en/players/" in str(resp.url):
                result = _parse_fbref_player_page(soup, str(resp.url))
                _cache_set(cache_key, result)
                return result

            # Case (b): search results — take the first player link
            for item in soup.select("div.search-item"):
                link = item.select_one("div.search-item-name a")
                if link and "/en/players/" in link.get("href", ""):
                    player_url = "https://fbref.com" + link["href"]
                    player_resp = await _get_with_retry(client, player_url)
                    player_soup = BeautifulSoup(player_resp.text, "lxml")
                    result = _parse_fbref_player_page(player_soup, player_url)
                    _cache_set(cache_key, result)
                    return result

        return {"error": f"'{player_name}' not found on FBref.", "fallback": True}

    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        return {"error": f"FBref fetch failed after retries: {exc}", "fallback": True}


def _parse_fbref_player_page(soup: BeautifulSoup, url: str) -> dict:
    """
    Extract key stats from a FBref player page.

    FBref stats tables use <td data-stat="goals"> etc., making them
    easy to parse without fragile CSS selectors that break on redesigns.
    """
    name_tag = soup.select_one("h1 span")
    name = name_tag.get_text(strip=True) if name_tag else "Unknown"

    position, club, nationality = "", "", ""
    meta = soup.select_one("div#meta")
    if meta:
        for p in meta.find_all("p"):
            text = p.get_text(" ", strip=True)
            if "Position:" in text:
                position = text.split("Position:")[-1].strip().split("▪")[0].strip()
            if "Club:" in text or "Team:" in text:
                club = text.split(":")[-1].strip()
            if "National Team:" in text:
                nationality = text.split("National Team:")[-1].strip()

    # Walk all tables, find the one with per-season goal/assist data
    stats = {}
    for table in soup.find_all("table"):
        rows = table.select("tbody tr:not(.thead):not(.over_header)")
        for row in reversed(rows):
            if "partial_table" in row.get("class", []):
                continue
            cells = {
                td["data-stat"]: td.get_text(strip=True)
                for td in row.find_all("td")
                if td.get("data-stat")
            }
            if "goals" in cells and cells.get("season", ""):
                stats = {
                    "season":               cells.get("season", ""),
                    "squad":                cells.get("squad", club),
                    "competition":          cells.get("comp", ""),
                    "matches_played":       cells.get("games", ""),
                    "minutes":              cells.get("minutes", ""),
                    "goals":                cells.get("goals", ""),
                    "assists":              cells.get("assists", ""),
                    "xG":                   cells.get("xg", ""),
                    "xA":                   cells.get("xg_assist", ""),
                    "shots_per_90":         cells.get("shots_per90", ""),
                    "key_passes":           cells.get("assisted_shots", ""),
                    "progressive_carries":  cells.get("progressive_carries", ""),
                }
                club = stats["squad"] or club
                break
        if stats:
            break

    return {
        "player":      name,
        "club":        club,
        "position":    position,
        "nationality": nationality,
        "stats":       stats,
        "source":      "FBref",
        "url":         url,
    }


# ── Wikipedia REST API: Formations ───────────────────────────────────────────

_FORMATION_WIKI_TITLES: dict[str, str] = {
    "4-3-3":   "4–3–3 formation",
    "4-2-3-1": "4–2–3–1 formation",
    "3-4-3":   "3–4–3 formation",
    "4-4-2":   "4–4–2 formation",
    "3-5-2":   "3–5–2 formation",
    "5-4-1":   "5–4–1 formation",
    "4-1-4-1": "4–1–4–1 formation",
    "4-3-2-1": "4–3–2–1 formation",
}


async def fetch_formation_wiki(formation: str) -> dict:
    """
    Fetch formation description from the Wikipedia REST API.
    Uses the in-memory cache and retry logic.
    """
    cache_key = f"wiki_formation:{formation.strip()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        print(f"  [cache] HIT for formation '{formation}'")
        return cached

    title = _FORMATION_WIKI_TITLES.get(
        formation.strip(),
        formation.replace("-", "–") + " formation",
    )
    encoded = title.replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=REQUEST_TIMEOUT) as client:
            resp = await _get_with_retry(client, url)

        if resp.status_code == 404:
            return {"error": f"No Wikipedia article for '{formation}'.", "fallback": True}

        data = resp.json()
        result = {
            "formation":     formation,
            "title":         data.get("title", ""),
            "description":   data.get("extract", ""),
            "wikipedia_url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            "source":        "Wikipedia",
        }
        _cache_set(cache_key, result)
        return result

    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        return {"error": f"Wikipedia fetch failed: {exc}", "fallback": True}


# ── Wikipedia REST API: Tactical Roles ───────────────────────────────────────

_ROLE_WIKI_TITLES: dict[str, str] = {
    "target man":             "Target man",
    "deep-lying playmaker":   "Playmaker",
    "regista":                "Regista",
    "inverted winger":        "Inverted winger",
    "box-to-box midfielder":  "Midfielder",
    "ball-playing defender":  "Sweeper (association football)",
    "false 9":                "False 9",
    "false nine":             "False 9",
    "libero":                 "Libero (football)",
    "trequartista":           "Trequartista",
    "mezzala":                "Mezzala",
    "enganche":               "Enganche",
    "carrilero":              "Carrilero",
    "segundo volante":        "Segundo volante",
    "shadow striker":         "Shadow striker",
    "pressing forward":       "Pressing forward",
    "complete forward":       "Centre forward",
    "sweeper keeper":         "Goalkeeper",
}


async def fetch_role_wiki(role_name: str) -> dict:
    """
    Fetch a tactical role description from the Wikipedia REST API.
    Uses the in-memory cache and retry logic.
    """
    key = role_name.lower().strip()
    cache_key = f"wiki_role:{key}"
    cached = _cache_get(cache_key)
    if cached is not None:
        print(f"  [cache] HIT for role '{role_name}'")
        return cached

    title = _ROLE_WIKI_TITLES.get(key, role_name.title())
    clean_title = title.split("#")[0].replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{clean_title}"

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=REQUEST_TIMEOUT) as client:
            resp = await _get_with_retry(client, url)

        if resp.status_code == 404:
            return {
                "not_found": True,
                "message": f"No Wikipedia article for '{role_name}'. Try search_football_web.",
                "fallback": True,
            }

        data = resp.json()
        result = {
            "role":          role_name,
            "title":         data.get("title", ""),
            "description":   data.get("extract", ""),
            "wikipedia_url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            "source":        "Wikipedia",
        }
        _cache_set(cache_key, result)
        return result

    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        return {"error": f"Wikipedia fetch failed: {exc}", "fallback": True}
