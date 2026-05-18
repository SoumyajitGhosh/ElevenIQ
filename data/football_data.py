"""
Mock football data — players, formations, and tactical roles.

In a real project this would come from a database or API (e.g. FBref, Opta).
Keeping it static here so the project runs with zero external dependencies.
"""

PLAYERS: dict = {
    "erling haaland": {
        "name": "Erling Haaland",
        "club": "Manchester City",
        "position": "Striker",
        "stats": {
            "goals": 36,
            "assists": 8,
            "xG": 31.2,
            "shots_per_game": 4.1,
            "aerial_duels_won_pct": 62,
            "press_intensity": "Low",
            "pace": 95,
            "finishing": 97,
        },
        "roles": ["Target Man", "Advanced Forward"],
        "summary": (
            "Elite goal-scorer with exceptional movement and finishing. "
            "Low pressing workrate but devastating in the box."
        ),
    },
    "kevin de bruyne": {
        "name": "Kevin De Bruyne",
        "club": "Manchester City",
        "position": "Central Midfielder",
        "stats": {
            "goals": 7,
            "assists": 16,
            "key_passes_per_game": 3.2,
            "xA": 13.8,
            "pass_accuracy_pct": 88,
            "press_intensity": "High",
            "vision": 98,
            "long_passing": 96,
        },
        "roles": ["Box-to-Box Midfielder", "Deep-Lying Playmaker"],
        "summary": (
            "World-class playmaker with elite vision, passing range, and work rate. "
            "The engine of City's attack."
        ),
    },
    "virgil van dijk": {
        "name": "Virgil van Dijk",
        "club": "Liverpool",
        "position": "Centre-Back",
        "stats": {
            "goals": 4,
            "assists": 2,
            "aerial_duels_won_pct": 78,
            "tackles_per_game": 2.1,
            "interceptions_per_game": 1.8,
            "pass_accuracy_pct": 91,
            "defensive_line_control": "Elite",
            "composure": 95,
        },
        "roles": ["Ball-Playing Defender", "Sweeper"],
        "summary": (
            "Commanding centre-back who dominates aerially and builds play "
            "from the back with composure."
        ),
    },
    "jude bellingham": {
        "name": "Jude Bellingham",
        "club": "Real Madrid",
        "position": "Attacking Midfielder",
        "stats": {
            "goals": 23,
            "assists": 12,
            "key_passes_per_game": 2.4,
            "press_intensity": "High",
            "xG": 18.1,
            "xA": 10.5,
            "dribbles_per_game": 2.9,
            "defensive_contribution": "High",
        },
        "roles": ["Box-to-Box Midfielder", "Shadow Striker", "Number 10"],
        "summary": (
            "Dynamic all-action midfielder who contributes at both ends. "
            "Scores, creates, and presses relentlessly."
        ),
    },
    "trent alexander-arnold": {
        "name": "Trent Alexander-Arnold",
        "club": "Liverpool",
        "position": "Right Back",
        "stats": {
            "goals": 5,
            "assists": 14,
            "key_passes_per_game": 2.8,
            "crosses_per_game": 3.4,
            "pass_accuracy_pct": 85,
            "press_intensity": "Medium",
            "attacking_contribution": "Elite",
        },
        "roles": ["Inverted Full-Back", "Overlapping Full-Back"],
        "summary": (
            "One of the most creative full-backs ever. "
            "Exceptional delivery and range of passing."
        ),
    },
}

FORMATIONS: dict = {
    "4-3-3": {
        "shape": "4-3-3",
        "structure": "4 defenders, 3 midfielders, 3 forwards",
        "strengths": [
            "Wide attacking presence through wingers",
            "Natural pressing shape with 3 forwards",
            "Flexible midfield triangle — pivot or 3 box-to-box options",
        ],
        "weaknesses": [
            "Vulnerable to midfield overloads if opponents play 3 or 4 in the middle",
            "Full-backs must cover wide defensively, leaving space in behind",
        ],
        "best_for": "Teams with quick direct wingers and a high-press philosophy",
        "famous_users": ["Manchester City (Guardiola)", "Liverpool (Klopp)"],
    },
    "4-2-3-1": {
        "shape": "4-2-3-1",
        "structure": "4 defenders, 2 defensive midfielders, 3 attacking midfielders, 1 striker",
        "strengths": [
            "Double pivot shields the back four effectively",
            "Versatile number 10 role can be a creator or high-presser",
            "Good balance between compactness and attacking output",
        ],
        "weaknesses": [
            "Can be congested centrally if all 3 attacking mids drift inside",
            "Wingers can be isolated without supporting full-backs",
        ],
        "best_for": "Teams with a creative no.10 and strong defensive midfielders",
        "famous_users": ["Chelsea (Ancelotti era)", "Spain national team"],
    },
    "3-4-3": {
        "shape": "3-4-3",
        "structure": "3 centre-backs, 2 wing-backs, 2 central midfielders, 3 forwards",
        "strengths": [
            "Wing-backs provide width in attack AND track back to form a 5-man defence",
            "3-man backline frees up an extra body in midfield",
            "Overloads opponents in central areas",
        ],
        "weaknesses": [
            "Demands elite athletic wing-backs with enormous work rate",
            "Susceptible to pace in behind if wing-backs are caught high",
        ],
        "best_for": "Teams with athletic wing-backs and dominant, ball-playing centre-backs",
        "famous_users": ["Chelsea (Conte)", "Inter Milan (Conte)"],
    },
    "4-4-2": {
        "shape": "4-4-2",
        "structure": "4 defenders, 4 midfielders, 2 strikers",
        "strengths": [
            "Two strikers create a constant central threat and partnership",
            "Solid defensive block of 8 players behind the ball",
            "Simple to execute — every player's role is clear",
        ],
        "weaknesses": [
            "Easily overrun in midfield by 3-man midfields",
            "Limited creativity in the no.10 zone between the lines",
        ],
        "best_for": "Teams built around a strike partnership and direct, vertical play",
        "famous_users": ["Classic England teams", "Atletico Madrid (compact block variant)"],
    },
}

ROLES: dict = {
    "target man": {
        "role": "Target Man",
        "position": "Striker",
        "key_attributes": [
            "Aerial ability — heading and hold-up play",
            "Physical strength to shield ball from defenders",
            "Finishing in tight spaces",
            "First-touch lay-offs to incoming midfielders",
        ],
        "tactical_function": (
            "Wins aerial duels, holds the ball up, and acts as the team's focal point. "
            "Relieves defensive pressure by giving the team an outlet ball."
        ),
        "ideal_for_system": "4-4-2 or any direct system with wide crossing",
        "example_players": ["Erling Haaland", "Harry Kane", "Robert Lewandowski"],
    },
    "deep-lying playmaker": {
        "role": "Deep-Lying Playmaker",
        "position": "Central / Defensive Midfielder",
        "key_attributes": [
            "Long passing range and accuracy",
            "Vision to pick passes early under pressure",
            "Composure on the ball in tight spaces",
            "Positional discipline — knows when NOT to move forward",
        ],
        "tactical_function": (
            "Sits deep to receive from defenders and distribute quickly. "
            "The metronome — dictates tempo, switches play, and breaks lines."
        ),
        "ideal_for_system": "4-3-3 as the pivot, or the anchor in a 4-2-3-1 double pivot",
        "example_players": ["Sergio Busquets", "Rodri", "Andrea Pirlo"],
    },
    "inverted winger": {
        "role": "Inverted Winger",
        "position": "Wide Forward",
        "key_attributes": [
            "Pace and dribbling to beat defenders 1v1",
            "Strong foot opposite to the wing they play on",
            "Long-range shooting to punish defenders who show them inside",
            "Off-the-ball movement to create space for full-back overlaps",
        ],
        "tactical_function": (
            "Starts wide but cuts inside onto their stronger foot to shoot or play the killer pass. "
            "Overloads central areas while the full-back provides width."
        ),
        "ideal_for_system": "4-3-3 or 4-2-3-1 with an overlapping full-back covering behind",
        "example_players": ["Arjen Robben", "Mohamed Salah", "Leroy Sane"],
    },
    "box-to-box midfielder": {
        "role": "Box-to-Box Midfielder",
        "position": "Central Midfielder",
        "key_attributes": [
            "Elite stamina and work rate — covers every inch of the pitch",
            "Defensive awareness to track runners and win the ball back",
            "Late runs into the box for goals",
            "Pressing intensity to win the ball high up the pitch",
        ],
        "tactical_function": (
            "The engine of the team. Wins the ball defensively, then drives forward "
            "to support attacks. The most physically demanding role in midfield."
        ),
        "ideal_for_system": "Any 3-man midfield — particularly 4-3-3 or 4-2-3-1",
        "example_players": ["Frank Lampard", "Jude Bellingham", "Kevin De Bruyne"],
    },
    "ball-playing defender": {
        "role": "Ball-Playing Defender",
        "position": "Centre-Back",
        "key_attributes": [
            "Composure and confidence on the ball",
            "Short and long passing — can play out from the back",
            "Ability to carry the ball into midfield under pressure",
            "Positional intelligence — reads the game before pressing",
        ],
        "tactical_function": (
            "Not just a defender — actively starts attacks. Breaks defensive lines "
            "with passes or forward carries, turning defence into attack quickly."
        ),
        "ideal_for_system": "High-press possession teams — 4-3-3 or 3-4-3",
        "example_players": ["Virgil van Dijk", "Ruben Dias", "David Luiz"],
    },
}
