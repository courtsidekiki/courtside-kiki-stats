#!/usr/bin/env python3
"""
Courtside Kiki — Daily NCAA D1 Women's Volleyball Stats Dashboard
====================================================================

Pulls, for a given date (default: today):
  - Scoreboard (every D1 women's volleyball game that day)
  - Box score + team stats for each game
  - National individual stat leaders (kills, assists, aces, and
    whatever else is configured in STAT_CATEGORIES below)

...and renders it all into a single static HTML dashboard at
docs/index.html, which GitHub Pages serves for free.

Data source: the free, open-source ncaa-api project
(https://github.com/henrygd/ncaa-api), which mirrors ncaa.com's
scoreboard/stats/game pages as JSON. Public instance:
https://ncaa-api.henrygd.me  (rate-limited to 5 req/sec — this
script is polite and sleeps a bit between calls).

FIRST RUN / TUNING NOTE
------------------------
This was written without live network access to test against, so
the NCAA_API_BASE routes and query patterns come straight from the
ncaa-api README, and the JSON parsing below is written defensively
(it tries several common key names and falls back gracefully rather
than crashing). The individual stat-category IDs in STAT_CATEGORIES
were confirmed by inspecting live ncaa.com stat pages — if a
category ever looks empty or wrong, go to
https://www.ncaa.com/stats/volleyball-women/d1 , pick that stat from
the dropdown, and copy the number that appears in the URL
(.../individual/<NUMBER>) into STAT_CATEGORIES below.

If the very first run produces something that looks off, save the
raw JSON this script writes to data/raw/ and send it back — it's a
five-minute fix to adjust the parsing to match the real shape.
"""

import json
import os
import sys
import time
import datetime
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

NCAA_API_BASE = "https://ncaa-api.henrygd.me"
SPORT = "volleyball-women"
DIVISION = "d1"

# Confirmed national individual stat-leader category IDs for D1 women's
# volleyball on ncaa.com. Add/adjust as needed (see note above).
STAT_CATEGORIES = {
    "Kills Per Set": 552,
    "Assists Per Set": 3,
    "Aces Per Set": 42,
    # "Digs Per Set": None,        # fill in once confirmed
    # "Blocks Per Set": None,      # fill in once confirmed
    # "Hitting Percentage": None,  # fill in once confirmed
}

REQUEST_DELAY_SECONDS = 0.3  # be polite to the free public API
TIMEOUT_SECONDS = 20


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr)


def api_get(path):
    """GET a path from the ncaa-api and return parsed JSON, or None on failure."""
    url = f"{NCAA_API_BASE}{path}"
    req = Request(url, headers={"User-Agent": "courtside-kiki-stats/1.0"})
    try:
        with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            raw = resp.read()
        data = json.loads(raw)
        return data
    except HTTPError as e:
        log(f"HTTP {e.code} for {url}")
    except URLError as e:
        log(f"Network error for {url}: {e}")
    except json.JSONDecodeError:
        log(f"Non-JSON response for {url}")
    except Exception as e:
        log(f"Unexpected error for {url}: {e}")
    return None


def dump_raw(name, data):
    """Save raw JSON for debugging/tuning."""
    os.makedirs("data/raw", exist_ok=True)
    path = f"data/raw/{name}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def get_scoreboard(date):
    path = f"/scoreboard/{SPORT}/{DIVISION}/{date.year}/{date.month:02d}/{date.day:02d}"
    data = api_get(path)
    if data:
        dump_raw(f"scoreboard_{date.isoformat()}", data)
    return data


def extract_games(scoreboard_json):
    """Pull a flat list of games out of whatever shape the scoreboard returned."""
    if not scoreboard_json:
        return []
    # ncaa-api scoreboard responses are typically {"games": [{"game": {...}}, ...]}
    games_raw = scoreboard_json.get("games") or scoreboard_json.get("data") or []
    games = []
    for g in games_raw:
        game = g.get("game", g) if isinstance(g, dict) else g
        games.append(game)
    return games


def game_id_of(game):
    for key in ("gameID", "gameId", "id", "url"):
        val = game.get(key)
        if val:
            # "url" sometimes looks like "/game/6305900"
            if key == "url" and isinstance(val, str):
                return val.rstrip("/").split("/")[-1]
            return str(val)
    return None


def get_boxscore(game_id):
    if not game_id:
        return None
    time.sleep(REQUEST_DELAY_SECONDS)
    data = api_get(f"/game/{game_id}/boxscore")
    if data:
        dump_raw(f"boxscore_{game_id}", data)
    return data


def get_team_stats(game_id):
    if not game_id:
        return None
    time.sleep(REQUEST_DELAY_SECONDS)
    data = api_get(f"/game/{game_id}/team-stats")
    if data:
        dump_raw(f"teamstats_{game_id}", data)
    return data


def get_stat_leaders(category_id):
    time.sleep(REQUEST_DELAY_SECONDS)
    data = api_get(f"/stats/{SPORT}/{DIVISION}/current/individual/{category_id}")
    if data:
        dump_raw(f"leaders_{category_id}", data)
    return data


def team_names(game):
    home = game.get("home", {}) or {}
    away = game.get("away", {}) or {}
    return (
        home.get("names", {}).get("short") or home.get("names", {}).get("full") or "Home",
        away.get("names", {}).get("short") or away.get("names", {}).get("full") or "Away",
    )


def team_score(game, side):
    t = game.get(side, {}) or {}
    return t.get("score", "-")


# ---------------------------------------------------------------------------
# HTML rendering — Courtside Kiki look: Y2K, bold, high-contrast
# ---------------------------------------------------------------------------

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Courtside Kiki — Daily Volleyball Stats</title>
<style>
  :root {{
    --pink: #ff2d95;
    --purple: #7a2bff;
    --blue: #00e0ff;
    --yellow: #fff200;
    --ink: #0e0e12;
    --paper: #fdfaf3;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0 0 4rem;
    background: linear-gradient(160deg, var(--purple) 0%, var(--pink) 45%, var(--blue) 100%);
    font-family: 'Trebuchet MS', 'Arial Black', system-ui, sans-serif;
    color: var(--ink);
  }}
  header {{
    padding: 2.5rem 1.5rem 1.5rem;
    text-align: center;
    color: var(--paper);
  }}
  header h1 {{
    font-size: clamp(2rem, 6vw, 3.2rem);
    margin: 0;
    letter-spacing: 1px;
    text-shadow: 3px 3px 0 var(--ink);
  }}
  header p {{ opacity: .9; margin: .5rem 0 0; font-weight: bold; }}
  main {{ max-width: 980px; margin: 0 auto; padding: 0 1rem; }}
  .card {{
    background: var(--paper);
    border: 4px solid var(--ink);
    border-radius: 18px;
    box-shadow: 8px 8px 0 var(--ink);
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.75rem;
  }}
  .card h2 {{
    margin-top: 0;
    display: inline-block;
    background: var(--yellow);
    padding: .2rem .8rem;
    border: 3px solid var(--ink);
    border-radius: 8px;
    transform: rotate(-1deg);
  }}
  .game {{
    border-top: 2px dashed #ccc;
    padding: .85rem 0;
  }}
  .game:first-of-type {{ border-top: none; }}
  .matchup {{ display: flex; justify-content: space-between; font-weight: bold; font-size: 1.1rem; }}
  .score {{ color: var(--pink); }}
  table {{ width: 100%; border-collapse: collapse; font-size: .92rem; margin-top: .5rem; }}
  th, td {{ text-align: left; padding: .35rem .5rem; border-bottom: 1px solid #eee; }}
  th {{ background: var(--blue); color: var(--ink); }}
  .empty {{ opacity: .6; font-style: italic; }}
  .updated {{ text-align: center; color: var(--paper); font-size: .85rem; margin-top: 2rem; opacity: .85; }}
</style>
</head>
<body>
<header>
  <h1>🏐 Courtside Kiki</h1>
  <p>Daily D1 Women's Volleyball Stats — {date_display}</p>
</header>
<main>
{sections}
</main>
<p class="updated">Last refreshed {timestamp} · data via ncaa.com</p>
</body>
</html>
"""

GAME_TEMPLATE = """
<div class="game">
  <div class="matchup">
    <span>{away} @ {home}</span>
    <span class="score">{away_score} – {home_score}</span>
  </div>
  <h4>Game Leaders</h4>
  {game_leaders_html}
  <h4>Team Stats</h4>
  {team_stats_html}
</div>
"""


# Stat fields (as they commonly appear in ncaa.com box scores) we want to
# crown a "leader" for, within a single game.
GAME_LEADER_STATS = ["Kills", "Assists", "Digs", "Aces", "Blocks", "Block Solos", "Block Assists", "Points"]

NAME_KEYS = ("Name", "name", "PlayerName", "player_name", "Player")


def find_player_rows(obj, found=None):
    """
    Recursively hunt through a box score JSON blob (whose exact shape is
    unconfirmed) for lists of dicts that look like individual player stat
    lines: something with a name-like field plus at least one numeric stat.
    """
    if found is None:
        found = []
    if isinstance(obj, dict):
        has_name = any(k in obj for k in NAME_KEYS)
        has_number = any(isinstance(v, (int, float)) for v in obj.values())
        if has_name and has_number:
            found.append(obj)
        else:
            for v in obj.values():
                find_player_rows(v, found)
    elif isinstance(obj, list):
        for item in obj:
            find_player_rows(item, found)
    return found


def player_name(row):
    for k in NAME_KEYS:
        if row.get(k):
            return row[k]
    return "?"


def player_team(row):
    for k in ("Team", "team", "TeamName"):
        if row.get(k):
            return row[k]
    return ""


def compute_game_leaders(boxscore_json):
    """Return {stat_label: (player_name, team, value)} for the top
    performer in each tracked stat, for this single game."""
    rows = find_player_rows(boxscore_json)
    leaders = {}
    for stat in GAME_LEADER_STATS:
        best = None
        for row in rows:
            val = row.get(stat)
            if isinstance(val, str):
                try:
                    val = float(val)
                except ValueError:
                    continue
            if isinstance(val, (int, float)):
                if best is None or val > best[2]:
                    best = (player_name(row), player_team(row), val)
        if best and best[2] > 0:
            leaders[stat] = best
    return leaders


def render_game_leaders_table(leaders):
    if not leaders:
        return ""
    rows = "".join(
        f"<tr><td>{stat}</td><td>{name}</td><td>{team}</td><td>{val:g}</td></tr>"
        for stat, (name, team, val) in leaders.items()
    )
    return f"<table><tr><th>Stat</th><th>Leader</th><th>Team</th><th>Value</th></tr>{rows}</table>"


# Key names (matched as substrings, case-insensitive) that are metadata/
# plumbing rather than actual stats — filtered out of the Team Stats table.
NOISE_KEY_PATTERNS = [
    "seoname", "sportcode", "url", "logo", "color", "slug", "id",
    "image", "link", "abbrev", "mascot", "conference", "division",
    "sport", "gender", "seo", "code",
]


def is_noise_key(key):
    k = key.lower()
    return any(p in k for p in NOISE_KEY_PATTERNS)


# Team totals, in display order, mapped from the confirmed real field names
# (see teamStats inside each team-stats JSON response).
TEAM_STAT_FIELDS = [
    ("points", "Points"),
    ("kills", "Kills"),
    ("attackAttempts", "Attack Attempts"),
    ("attackErrors", "Attack Errors"),
    ("hittingPercentage", "Hitting %"),
    ("assists", "Assists"),
    ("digs", "Digs"),
    ("serviceAces", "Service Aces"),
    ("serviceErrors", "Service Errors"),
    ("serveAttempts", "Serve Attempts"),
    ("setErrors", "Set Errors"),
    ("setAttempts", "Set Attempts"),
    ("receptionAttempts", "Reception Attempts"),
    ("receptionErrors", "Reception Errors"),
    ("blockSolos", "Block Solos"),
    ("blockAssists", "Block Assists"),
    ("blockingErrors", "Blocking Errors"),
    ("totalBlocks", "Total Blocks"),
]


def render_team_stats_table(team_stats_json):
    if not team_stats_json:
        return '<p class="empty">Team stats not available for this game.</p>'

    teams = team_stats_json.get("teams") or []
    team_names_by_id = {
        str(t.get("teamId")): (t.get("nameShort") or t.get("nameFull") or "?")
        for t in teams
    }
    boxscore = team_stats_json.get("teamBoxscore") or []
    if not boxscore:
        return '<p class="empty">Team stats not available for this game.</p>'

    # Preserve column order: home team first if we can tell, else as given.
    entries = []
    for tb in boxscore:
        tid = str(tb.get("teamId"))
        stats = tb.get("teamStats") or {}
        entries.append((team_names_by_id.get(tid, tid), stats))

    header = "".join(f"<th>{name}</th>" for name, _ in entries)
    body_rows = []
    for field, label in TEAM_STAT_FIELDS:
        cells = "".join(f"<td>{stats.get(field, '-')}</td>" for _, stats in entries)
        body_rows.append(f"<tr><td>{label}</td>{cells}</tr>")

    return f"<table><tr><th>Stat</th>{header}</tr>{''.join(body_rows)}</table>"


def _unused_generic_team_stats_table(team_stats_json):
    if not team_stats_json:
        return '<p class="empty">Team stats not available for this game.</p>'
    # Defensive: shape unconfirmed, so just pretty-print whatever key/value
    # pairs we can find rather than guessing wrong and hiding data.
    rows = []
    def walk(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    walk(v, f"{prefix}{k} ")
                else:
                    if not is_noise_key(k):
                        rows.append((f"{prefix}{k}", v))
        elif isinstance(obj, list):
            for item in obj:
                walk(item, prefix)
    walk(team_stats_json)
    if not rows:
        return '<p class="empty">Team stats not available for this game.</p>'
    body = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows[:40])
    return f"<table><tr><th>Stat</th><th>Value</th></tr>{body}</table>"


def render_games_section(games, boxscores, team_stats_map):
    if not games:
        return '<div class="card"><h2>Games</h2><p class="empty">No D1 women\'s volleyball games found for this date.</p></div>'
    html_games = []
    for game in games:
        home, away = team_names(game)
        home_score = team_score(game, "home")
        away_score = team_score(game, "away")
        gid = game_id_of(game)
        ts_html = render_team_stats_table(team_stats_map.get(gid))
        leaders = compute_game_leaders(boxscores.get(gid))
        gl_html = render_game_leaders_table(leaders) or '<p class="empty">Player leaders not available for this game.</p>'
        html_games.append(GAME_TEMPLATE.format(
            away=away, home=home,
            away_score=away_score, home_score=home_score,
            game_leaders_html=gl_html,
            team_stats_html=ts_html,
        ))
    return f'<div class="card"><h2>Today\'s Games & Box Scores</h2>{"".join(html_games)}</div>'


def render_leaders_section(leaders_by_category):
    blocks = []
    for label, data in leaders_by_category.items():
        rows_html = '<p class="empty">Not available.</p>'
        if data:
            entries = data.get("data") or data.get("stats") or []
            rows = []
            for e in entries[:10]:
                if isinstance(e, dict):
                    name = e.get("Name") or e.get("name") or "?"
                    team = e.get("Team") or e.get("team") or ""
                    val = e.get("Per Set") or e.get("value") or ""
                    rows.append(f"<tr><td>{name}</td><td>{team}</td><td>{val}</td></tr>")
            if rows:
                rows_html = f"<table><tr><th>Player</th><th>Team</th><th>{label}</th></tr>{''.join(rows)}</table>"
        blocks.append(f"<div><h3>{label}</h3>{rows_html}</div>")
    return f'<div class="card"><h2>National Stat Leaders</h2>{"".join(blocks)}</div>'


def build_dashboard(date):
    scoreboard = get_scoreboard(date)
    games = extract_games(scoreboard)

    boxscores, team_stats_map = {}, {}
    for game in games:
        gid = game_id_of(game)
        if gid:
            boxscores[gid] = get_boxscore(gid)
            team_stats_map[gid] = get_team_stats(gid)

    leaders_by_category = {
        label: get_stat_leaders(cat_id) for label, cat_id in STAT_CATEGORIES.items()
    }

    sections = render_games_section(games, boxscores, team_stats_map)
    sections += render_leaders_section(leaders_by_category)

    html = PAGE_TEMPLATE.format(
        date_display=date.strftime("%A, %B %-d, %Y") if os.name != "nt" else date.strftime("%A, %B %d, %Y"),
        sections=sections,
        timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
    )

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w") as f:
        f.write(html)
    log(f"Wrote docs/index.html for {date.isoformat()} ({len(games)} games found)")


if __name__ == "__main__":
    target_date = datetime.date.today()
    if len(sys.argv) > 1:
        target_date = datetime.date.fromisoformat(sys.argv[1])
    build_dashboard(target_date)
