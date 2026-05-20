from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun

from agent.scrapers import fetch_formation_wiki, fetch_player_fbref, fetch_role_wiki

_ddg_search = DuckDuckGoSearchRun()

# ── Tool 1: Player Stats ──────────────────────────────────────────────────────

@tool
async def get_player_stats(player_name: str) -> dict:
    """Get detailed statistics and a scouting report for a football player.

    Use when the user asks about:
    - A specific player's performance numbers or ratings
    - Scouting a particular player
    - What position or tactical roles a player can fill
    - Comparing a player's key metrics

    Args:
        player_name: Full or partial player name.
                     Examples: "Haaland", "De Bruyne", "Bellingham"

    Returns:
        Player stats, tactical roles, club, and an analyst summary.
    """
    key = player_name.lower().strip()

    return {
        "stats": await fetch_player_fbref(player_name),
        "fallback": True,
        "player_name": player_name,
    }


# ── Tool 2: Formation Comparison ──────────────────────────────────────────────

@tool
async def compare_formations(formation_a: str, formation_b: str) -> dict:
    """Compare two tactical formations head-to-head like a tactical analyst.

    Use when the user asks about:
    - Differences or matchups between two formations
    - Which formation suits a particular style of play
    - How a system's strengths and weaknesses stack up
    - Questions like "4-3-3 vs 4-2-3-1 — what's the difference?"

    Args:
        formation_a: First formation string.  Examples: "4-3-3", "4-2-3-1"
        formation_b: Second formation string. Examples: "3-4-3", "4-4-2"

    Returns:
        Side-by-side tactical breakdown including strengths, weaknesses,
        best use case, and famous clubs that used each system.
    """
    return {
        "formation_a": await fetch_formation_wiki(formation_a),
        "formation_b": await fetch_formation_wiki(formation_b),
        "summary": (
            f"Comparing {formation_a} vs {formation_b}: "
            f"'{fa['best_for']}' — versus — '{fb['best_for']}'"
        ),
    }


# ── Tool 3: Role Scouting ─────────────────────────────────────────────────────

@tool
async def scout_role(role_name: str) -> dict:
    """Get a detailed scouting profile for a tactical football role.

    Use when the user asks about:
    - What attributes or qualities a specific role demands
    - How a role functions within a team's tactical system
    - What kind of player profile fits a role
    - Questions like "what makes a good target man?" or "explain inverted winger"

    Args:
        role_name: Name of the tactical role (case-insensitive).
                   Examples: "target man", "deep-lying playmaker",
                             "inverted winger", "box-to-box midfielder",
                             "ball-playing defender"

    Returns:
        Key attributes, tactical function, best system fit, and real player examples.
    """
    key = role_name.lower().strip()

    return {
        "stats": await fetch_role_wiki(role_name),
        "fallback": True,
    }

# ── Tool 4: Web Search Fallback (DuckDuckGo) ─────────────────────────────────

@tool
async def search_football_web(query: str) -> str:
    """Search the web for football information not covered by the other tools.

    Use this tool when:
    - get_player_stats returns fallback=True (player not on FBref)
    - compare_formations returns fallback=True (formation not on Wikipedia)
    - scout_role returns fallback=True (role not found)
    - The user asks about recent transfers, injuries, or match results
    - The user asks about managers, clubs, tournaments, or history
    - You need to cross-check or enrich data from another tool

    This is your general-purpose fallback. Always try the specific tools
    (get_player_stats, compare_formations, scout_role) before using this.

    Args:
        query: A focused football search query — be specific.
               Good: "Lamine Yamal 2025 stats goals assists La Liga"
               Bad:  "football player stats" (too vague)

    Returns:
        Raw web search results. Synthesise them into a clear analyst answer.
    """
    return _ddg_search.run(query)