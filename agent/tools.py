from langchain_core.tools import tool
from data.football_data import FORMATIONS, PLAYERS, ROLES

# ── Tool 1: Player Stats ──────────────────────────────────────────────────────

@tool
def get_player_stats(player_name: str) -> dict:
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

    # Partial name matching — "haaland" hits "erling haaland"
    matched_data = None
    for player_key, player_data in PLAYERS.items():
        if key in player_key or any(key in part for part in player_key.split()):
            matched_data = player_data
            break

    if matched_data is None:
        available = [p["name"] for p in PLAYERS.values()]
        return {
            "error": f"No data found for '{player_name}'.",
            "available_players": available,
        }

    return {
        "player": matched_data["name"],
        "club": matched_data["club"],
        "position": matched_data["position"],
        "stats": matched_data["stats"],
        "roles": matched_data["roles"],
        "summary": matched_data["summary"],
    }


# ── Tool 2: Formation Comparison ──────────────────────────────────────────────

@tool
def compare_formations(formation_a: str, formation_b: str) -> dict:
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
    fa = FORMATIONS.get(formation_a.strip())
    fb = FORMATIONS.get(formation_b.strip())

    errors = []
    if fa is None:
        errors.append(f"Formation '{formation_a}' not found.")
    if fb is None:
        errors.append(f"Formation '{formation_b}' not found.")
    if errors:
        return {
            "error": " ".join(errors),
            "available_formations": list(FORMATIONS.keys()),
        }

    return {
        "formation_a": fa,
        "formation_b": fb,
        "summary": (
            f"Comparing {formation_a} vs {formation_b}: "
            f"'{fa['best_for']}' — versus — '{fb['best_for']}'"
        ),
    }


# ── Tool 3: Role Scouting ─────────────────────────────────────────────────────

@tool
def scout_role(role_name: str) -> dict:
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

    role_data = ROLES.get(key)

    # Partial match fallback — "box-to-box" hits "box-to-box midfielder"
    if role_data is None:
        for role_key, data in ROLES.items():
            if key in role_key:
                role_data = data
                break

    if role_data is None:
        return {
            "error": f"Role '{role_name}' not found.",
            "available_roles": list(ROLES.keys()),
        }

    return role_data