"""
agent/scrapers.py — Live data scrapers for 4 football data sources.

Sources and what each is best at:
  SofaScore  → Player profile, stats, rating (clean JSON API)
  Understat  → xG / xA per season (embedded JSON in HTML)
  FBref      → Broad historical stats (HTML tables, fallback)
  FootyStats → Formation stats per league (HTML table)

WhoScored is intentionally excluded — it requires JavaScript rendering
(Selenium/Playwright) which is outside the scope of this project.
"""

import asyncio
import json
import re
import time
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

# ── Shared config ─────────────────────────────────────────────────────────────

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SOFASCORE_HEADERS = {
    **BROWSER_HEADERS,
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Accept": "application/json, text/plain, */*",
}

TIMEOUT = 15.0
MAX_RETRY = 3
CACHE_TTL = 300  # 5 minutes

# ── In-memory session cache ───────────────────────────────────────────────────

_cache: dict[str, tuple[float, dict | list]] = {}


def _cache_get(key: str) -> dict | list | None:
    if (entry := _cache.get(key)) and time.monotonic() - entry[0] < CACHE_TTL:
        print(f"  [cache] HIT  {key}")
        return entry[1]
    _cache.pop(key, None)
    return None


def _cache_set(key: str, data: dict | list) -> None:
    _cache[key] = (time.monotonic(), data)


# ── Retry helper ──────────────────────────────────────────────────────────────

async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """GET with exponential backoff on 429 / 5xx (1s → 2s → 4s)."""
    exc: Exception = RuntimeError("no attempts")
    for attempt in range(MAX_RETRY):
        try:
            resp = await client.get(url)
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = 2 ** attempt
                print(f"  [http] {resp.status_code} → retry in {wait}s")
                await asyncio.sleep(wait)
                exc = httpx.HTTPStatusError("rate-limited", request=resp.request, response=resp)
                continue
            return resp
        except httpx.RequestError as e:
            exc = e
            await asyncio.sleep(2 ** attempt)
    raise exc


def _safe_json_response(resp: httpx.Response, source: str, context: str) -> dict | list:
    """Decode JSON safely and raise a readable ValueError on empty/invalid responses."""
    body = resp.text.strip()
    if not body:
        raise ValueError(f"{source} returned an empty response for {context}.")

    content_type = resp.headers.get("content-type", "")
    if "json" not in content_type.lower() and body[:1] not in ("{", "["):
        preview = body[:200].replace("\n", " ")
        raise ValueError(
            f"{source} returned non-JSON content for {context} "
            f"(content-type={content_type!r}, preview={preview!r})."
        )

    try:
        return resp.json()
    except json.JSONDecodeError as e:
        preview = body[:200].replace("\n", " ")
        raise ValueError(
            f"{source} returned invalid JSON for {context}: {e}. Preview: {preview!r}"
        ) from e


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 1 — SofaScore
# ═══════════════════════════════════════════════════════════════════════════════

SOFA_BASE = "https://api.sofascore.com/api/v1"


async def fetch_sofascore_player(player_name: str) -> dict:
    """
    Full SofaScore pipeline: search → profile → most recent season stats.
    Returns a merged dict with player info + stats.
    """
    key = f"sofa:{player_name.lower().strip()}"
    if cached := _cache_get(key):
        return cached  # type: ignore[return-value]

    print(f"  [sofascore] fetching '{player_name}'...")
    try:
        async with httpx.AsyncClient(
            headers=SOFASCORE_HEADERS,
            timeout=TIMEOUT,
            follow_redirects=True,
        ) as client:
            search_resp = await _get(client, f"{SOFA_BASE}/search/all/?q={quote(player_name)}")
            search_data = _safe_json_response(search_resp, "SofaScore", f"search for {player_name}")
            players = search_data.get("players", []) if isinstance(search_data, dict) else []
            if not players:
                return {"error": f"'{player_name}' not found on SofaScore.", "source": "SofaScore"}

            player = players[0].get("entity", {})
            player_id = player.get("id")
            if not player_id:
                return {"error": "SofaScore search result missing player ID.", "source": "SofaScore"}

            seasons_resp = await _get(client, f"{SOFA_BASE}/player/{player_id}/statistics/seasons")
            seasons_data = _safe_json_response(
                seasons_resp,
                "SofaScore",
                f"season list for player ID {player_id}",
            )
            tournament_seasons = (
                seasons_data.get("uniqueTournamentSeasons", []) if isinstance(seasons_data, dict) else []
            )

            stats: dict = {}
            for ts in tournament_seasons:
                unique_tournament = ts.get("uniqueTournament", {})
                seasons = ts.get("seasons", [])
                tournament_id = unique_tournament.get("id")
                tournament_name = unique_tournament.get("name", "")
                if not tournament_id or not seasons:
                    continue

                recent_season = seasons[0]
                season_id = recent_season.get("id")
                season_name = recent_season.get("name")
                if not season_id:
                    continue

                stats_resp = await _get(
                    client,
                    f"{SOFA_BASE}/player/{player_id}"
                    f"/unique-tournament/{tournament_id}"
                    f"/season/{season_id}/statistics/overall",
                )
                try:
                    stats_payload = _safe_json_response(
                        stats_resp,
                        "SofaScore",
                        f"overall stats for player ID {player_id} in tournament {tournament_id}",
                    )
                except ValueError:
                    continue

                stats_data = stats_payload.get("statistics") if isinstance(stats_payload, dict) else None
                if stats_data:
                    stats = {
                        "season": season_name,
                        "tournament": tournament_name,
                        "appearances": stats_data.get("appearances"),
                        "minutes_played": stats_data.get("minutesPlayed"),
                        "goals": stats_data.get("goals"),
                        "assists": stats_data.get("assists"),
                        "rating": stats_data.get("rating"),
                        "shots_on_target": stats_data.get("onTargetScoringAttempt"),
                        "key_passes": stats_data.get("keyPass"),
                        "dribbles": stats_data.get("successfulDribbles"),
                        "yellow_cards": stats_data.get("yellowCards"),
                    }
                    break

        result: dict = {
            "player": player.get("name"),
            "position": player.get("position"),
            "team": player.get("team", {}).get("name", ""),
            "nationality": player.get("country", {}).get("name", ""),
            "stats": stats,
            "source": "SofaScore",
        }
        _cache_set(key, result)
        return result
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as e:
        return {"error": str(e), "source": "SofaScore"}


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 2 — Understat
# ═══════════════════════════════════════════════════════════════════════════════

UNDERSTAT_BASE = "https://understat.com"


def _extract_understat_json(html: str, var_name: str) -> dict | list:
    """
    Pull JSON out of an Understat script tag.

    Understat stores data like:
      var groupsData = JSON.parse('{\\"season\\":[...]}')
    The value is double-escaped, so we decode unicode escapes first.
    """
    pattern = rf"var\s+{var_name}\s*=\s*JSON\.parse\('(.+?)'\)"
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return {}
    raw = match.group(1).encode("utf-8").decode("unicode_escape")
    return json.loads(raw)


async def search_understat_player(player_name: str) -> dict | None:
    """
    POST to Understat's search endpoint and return the top match.
    Returns {"id": "...", "name": "..."} or None.
    """
    try:
        async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{UNDERSTAT_BASE}/main/getSearchResults",
                data={"q": player_name},
            )
        if resp.status_code != 200:
            return None
        payload = _safe_json_response(resp, "Understat", f"search for {player_name}")
        players = payload.get("player", []) if isinstance(payload, dict) else []
        return players[0] if players else None
    except (httpx.RequestError, ValueError):
        return None


async def fetch_understat_player_xg(player_name: str) -> dict:
    """
    Fetch per-season xG / xA from Understat for a player.
    Returns the most recent season's xG metrics.
    """
    key = f"understat:{player_name.lower().strip()}"
    if cached := _cache_get(key):
        return cached  # type: ignore[return-value]

    print(f"  [understat] fetching xG for '{player_name}'...")
    match = await search_understat_player(player_name)
    if not match:
        return {"error": f"'{player_name}' not found on Understat.", "source": "Understat"}

    try:
        player_id = match["id"]
        async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=TIMEOUT) as client:
            resp = await _get(client, f"{UNDERSTAT_BASE}/player/{player_id}")

        groups = _extract_understat_json(resp.text, "groupsData")
        seasons = groups.get("season", []) if isinstance(groups, dict) else []
        if not seasons:
            return {"error": "No season data found on Understat.", "source": "Understat"}

        recent = seasons[0]
        result = {
            "player": match.get("name", player_name),
            "season": recent.get("year"),
            "goals": recent.get("goals"),
            "xG": round(float(recent.get("xG", 0)), 2),
            "assists": recent.get("assists"),
            "xA": round(float(recent.get("xA", 0)), 2),
            "shots": recent.get("shots"),
            "key_passes": recent.get("key_passes"),
            "minutes": recent.get("time"),
            "npxG": round(float(recent.get("npxG", 0)), 2),
            "source": "Understat",
        }
        _cache_set(key, result)
        return result
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError, KeyError) as e:
        return {"error": str(e), "source": "Understat"}


async def fetch_understat_league_players(
    league: str = "EPL",
    season: str = "2024",
) -> list[dict]:
    """
    Fetch all players from a league season on Understat.
    Used by scout_role to find top performers at a given position.

    league options: EPL, La_liga, Bundesliga, Serie_A, Ligue_1, RFPL
    season: four-digit year of the season start (e.g. "2024" for 2024/25)
    """
    key = f"understat_league:{league}:{season}"
    if cached := _cache_get(key):
        return cached  # type: ignore[return-value]

    print(f"  [understat] fetching {league} {season} players...")
    url = f"{UNDERSTAT_BASE}/league/{league}/{season}"
    try:
        async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=TIMEOUT) as client:
            resp = await _get(client, url)

        players_raw = _extract_understat_json(resp.text, "playersData")
        players = list(players_raw.values()) if isinstance(players_raw, dict) else players_raw

        result = [
            {
                "name": p.get("player_name"),
                "team": p.get("team_title"),
                "position": p.get("position"),
                "goals": p.get("goals"),
                "xG": round(float(p.get("xG", 0)), 2),
                "assists": p.get("assists"),
                "xA": round(float(p.get("xA", 0)), 2),
                "minutes": p.get("time"),
                "shots": p.get("shots"),
            }
            for p in players
        ]
        _cache_set(key, result)
        return result
    except (httpx.HTTPStatusError, httpx.RequestError, ValueError, TypeError) as e:
        print(f"  [understat] error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 3 — FBref
# ═══════════════════════════════════════════════════════════════════════════════

FBREF_BASE = "https://fbref.com"


async def fetch_fbref_player(player_name: str) -> dict:
    """Search FBref for a player and return their most recent season stats."""
    key = f"fbref:{player_name.lower().strip()}"
    if cached := _cache_get(key):
        return cached  # type: ignore[return-value]

    print(f"  [fbref] fetching '{player_name}'...")
    encoded = player_name.replace(" ", "+")
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, headers=BROWSER_HEADERS, timeout=TIMEOUT
        ) as client:
            resp = await _get(client, f"{FBREF_BASE}/search/search.fcgi?search={encoded}")
            soup = BeautifulSoup(resp.text, "lxml")

            if "/en/players/" in str(resp.url):
                result = _parse_fbref_page(soup, str(resp.url))
                _cache_set(key, result)
                return result

            for item in soup.select("div.search-item"):
                link = item.select_one("div.search-item-name a")
                if link and "/en/players/" in link.get("href", ""):
                    player_url = FBREF_BASE + link["href"]
                    pr = await _get(client, player_url)
                    result = _parse_fbref_page(BeautifulSoup(pr.text, "lxml"), player_url)
                    _cache_set(key, result)
                    return result
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        return {"error": str(e), "source": "FBref"}

    return {"error": f"'{player_name}' not found on FBref.", "source": "FBref"}


def _parse_fbref_page(soup: BeautifulSoup, url: str) -> dict:
    """Extract key stats from an FBref player page using data-stat attributes."""
    heading = soup.select_one("h1 span") or soup.select_one("h1")
    name = heading.get_text(strip=True) if heading else ""
    position, club, nationality = "", "", ""
    if meta := soup.select_one("div#meta"):
        for p in meta.find_all("p"):
            t = p.get_text(" ", strip=True)
            if "Position:" in t:
                position = t.split("Position:")[-1].strip().split("▪")[0].strip()
            if "National Team:" in t:
                nationality = t.split("National Team:")[-1].strip()

    stats: dict = {}
    for table in soup.find_all("table"):
        for row in reversed(table.select("tbody tr:not(.thead):not(.over_header)")):
            if "partial_table" in row.get("class", []):
                continue
            cells = {
                td["data-stat"]: td.get_text(strip=True)
                for td in row.find_all("td")
                if td.get("data-stat")
            }
            if "goals" in cells and cells.get("season"):
                stats = {
                    "season": cells.get("season"),
                    "squad": cells.get("squad", club),
                    "competition": cells.get("comp"),
                    "matches": cells.get("games"),
                    "minutes": cells.get("minutes"),
                    "goals": cells.get("goals"),
                    "assists": cells.get("assists"),
                    "xG": cells.get("xg"),
                    "xA": cells.get("xg_assist"),
                    "progressive_carries": cells.get("progressive_carries"),
                }
                club = stats["squad"] or club
                break
        if stats:
            break

    return {
        "player": name,
        "club": club,
        "position": position,
        "nationality": nationality,
        "stats": stats,
        "source": "FBref",
        "url": url,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SOURCE 4 — FootyStats
# ═══════════════════════════════════════════════════════════════════════════════

FOOTYSTATS_BASE = "https://footystats.org"

FOOTYSTATS_LEAGUES: dict[str, str] = {
    "epl": "/england/premier-league/formation-stats",
    "premier league": "/england/premier-league/formation-stats",
    "la liga": "/spain/la-liga/formation-stats",
    "bundesliga": "/germany/bundesliga/formation-stats",
    "serie a": "/italy/serie-a/formation-stats",
    "ligue 1": "/france/ligue-1/formation-stats",
}
DEFAULT_LEAGUE_PATH = "/england/premier-league/formation-stats"


async def fetch_footystats_formation(formation: str, league: str = "epl") -> dict:
    """
    Scrape FootyStats formation stats for a given formation.
    Returns win rate, goals scored/conceded, and xG for teams using that formation.
    """
    key = f"footystats:{league}:{formation}"
    if cached := _cache_get(key):
        return cached  # type: ignore[return-value]

    league_path = FOOTYSTATS_LEAGUES.get(league.lower().strip(), DEFAULT_LEAGUE_PATH)
    url = FOOTYSTATS_BASE + league_path
    print(f"  [footystats] fetching formation stats from {url}...")

    try:
        async with httpx.AsyncClient(
            follow_redirects=True, headers=BROWSER_HEADERS, timeout=TIMEOUT
        ) as client:
            resp = await _get(client, url)

        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("table tbody tr")
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if not cells:
                continue
            row_formation = cells[0].strip()
            normalised = row_formation.replace("–", "-").replace(" ", "")
            if normalised == formation.replace(" ", ""):
                result: dict = {
                    "formation": formation,
                    "league": league.upper(),
                    "games_played": cells[1] if len(cells) > 1 else "",
                    "win_pct": cells[2] if len(cells) > 2 else "",
                    "draw_pct": cells[3] if len(cells) > 3 else "",
                    "loss_pct": cells[4] if len(cells) > 4 else "",
                    "goals_scored_pg": cells[5] if len(cells) > 5 else "",
                    "goals_conceded_pg": cells[6] if len(cells) > 6 else "",
                    "source": "FootyStats",
                    "source_url": url,
                }
                _cache_set(key, result)
                return result

        return {
            "error": f"Formation '{formation}' not found in FootyStats {league} table.",
            "source": "FootyStats",
            "source_url": url,
        }
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        return {"error": str(e), "source": "FootyStats"}
