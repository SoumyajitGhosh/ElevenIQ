"""
Each tool calls a specific data source — no LLM search involved.

  get_player_stats  → SofaScore (stats) + Understat (xG)
  get_player_xg     → Understat only (deeper xG breakdown)
  compare_formations→ FootyStats (formation win/goal stats per league)
  scout_role        → Understat league players filtered by position
"""

from langchain_core.tools import tool

from agent.scrapers import (
    fetch_footystats_formation,
    fetch_sofascore_player,
    fetch_understat_league_players,
    fetch_understat_player_xg,
    fetch_fbref_player,
)


# ── Tool 1: Player Stats (SofaScore primary, Understat xG enrichment) ─────────

@tool
async def get_player_stats(player_name: str) -> dict:
    """Get live stats for a football player from SofaScore and Understat.

    Use for:
    - Goals, assists, rating, minutes for any player this season
    - xG and xA (expected goals and assists)
    - Club, position, nationality

    Args:
        player_name: Full or partial name. Examples: "Haaland", "Pedri", "Bellingham"
    """
    sofa  = await fetch_sofascore_player(player_name)
    xg    = await fetch_understat_player_xg(player_name)

    # Merge: SofaScore for match stats, Understat for xG layer
    return {
        "player":      sofa.get("player", player_name),
        "team":        sofa.get("team", ""),
        "position":    sofa.get("position", ""),
        "nationality": sofa.get("nationality", ""),
        "match_stats": sofa.get("stats", {}),
        "xg_stats":    {k: v for k, v in xg.items()
                        if k in ("xG", "xA", "npxG", "shots", "key_passes")},
        "sources":     ["SofaScore", "Understat"],
    }


# ── Tool 2: xG Breakdown (Understat deep-dive) ────────────────────────────────

@tool
async def get_player_xg(player_name: str) -> dict:
    """Get detailed expected goals (xG) and xA breakdown for a player from Understat.

    Use when the user wants a deeper look at shot quality and chance creation —
    not just raw goals/assists but xG overperformance, npxG, etc.

    Args:
        player_name: Player name. Examples: "Haaland", "Mbappe", "Salah"
    """
    return await fetch_understat_player_xg(player_name)


# ── Tool 3: Formation Comparison (FootyStats) ─────────────────────────────────

@tool
async def compare_formations(formation_a: str, formation_b: str, league: str = "epl") -> dict:
    """Compare two formations using real league stats from FootyStats.

    Returns win rate, goals scored/conceded per game for teams
    using each formation in the specified league.

    Args:
        formation_a: e.g. "4-3-3", "3-4-3"
        formation_b: e.g. "4-2-3-1", "4-4-2"
        league:      League to pull stats from. Options: "epl", "la liga",
                     "bundesliga", "serie a", "ligue 1". Default: "epl"
    """
    fa, fb = await fetch_footystats_formation(formation_a, league), \
             await fetch_footystats_formation(formation_b, league)
    return {"formation_a": fa, "formation_b": fb}


# ── Tool 4: Role Scouting (Understat league players by position) ──────────────

# Maps tactical role names to Understat position codes
# Understat positions: FW, AM, MF, DM, DF, GK
_ROLE_TO_POSITION: dict[str, str] = {
    # Forwards
    "target man":        "FW",
    "false 9":           "FW",
    "false nine":        "FW",
    "complete forward":  "FW",
    "poacher":           "FW",
    "pressing forward":  "FW",
    # Attacking mids / wide
    "trequartista":      "AM",
    "shadow striker":    "AM",
    "number 10":         "AM",
    "inverted winger":   "AM",
    "winger":            "AM",
    "enganche":          "AM",
    # Central mids
    "box-to-box midfielder": "MF",
    "mezzala":           "MF",
    "carrilero":         "MF",
    # Defensive mids
    "regista":           "DM",
    "deep-lying playmaker": "DM",
    "segundo volante":   "DM",
    "anchor":            "DM",
    # Defenders
    "ball-playing defender": "DF",
    "libero":            "DF",
    "sweeper":           "DF",
    "inverted full-back": "DF",
}


@tool
async def scout_role(
    role_name: str,
    league: str = "EPL",
    season: str = "2024",
    top_n: int = 8,
) -> dict:
    """Find the top-performing players for a given tactical role using Understat data.

    Instead of a definition, this returns REAL players who best exemplify
    the role — ranked by xG (for attacking roles) or xA (for creative roles).

    Args:
        role_name: Tactical role. Examples: "regista", "false 9", "inverted winger",
                   "target man", "trequartista", "box-to-box midfielder"
        league:    Understat league code. Options: EPL, La_liga, Bundesliga,
                   Serie_A, Ligue_1. Default: "EPL"
        season:    Season start year. Default: "2024" (= 2024/25 season)
        top_n:     How many players to return. Default: 8
    """
    position_code = _ROLE_TO_POSITION.get(role_name.lower().strip())
    if not position_code:
        known = list(_ROLE_TO_POSITION.keys())
        return {
            "error": f"Role '{role_name}' not mapped to a position.",
            "known_roles": known,
        }

    all_players = await fetch_understat_league_players(league, season)

    # Filter by position and sort by xG (best proxy for role impact)
    filtered = [
        p for p in all_players
        if p.get("position", "").upper() == position_code and p.get("xG", 0) > 0
    ]
    top = sorted(filtered, key=lambda p: p.get("xG", 0), reverse=True)[:top_n]

    return {
        "role":          role_name,
        "mapped_to":     position_code,
        "league":        league,
        "season":        season,
        "top_players":   top,
        "source":        "Understat",
    }
