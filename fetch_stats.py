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
  .nav {{
    display: flex; gap: .6rem; align-items: center; justify-content: center;
    flex-wrap: wrap; margin: 0 0 1.5rem;
  }}
  .nav button, .nav select {{
    font: inherit; font-weight: bold; padding: .5rem 1rem;
    background: var(--yellow); color: var(--ink);
    border: 3px solid var(--ink); border-radius: 10px;
    box-shadow: 4px 4px 0 var(--ink); cursor: pointer;
  }}
  .nav button:disabled {{ opacity: .4; cursor: default; }}
  h4 {{ margin: .9rem 0 .2rem; }}
  .updated {{ text-align: center; color: var(--paper); font-size: .85rem; margin-top: 2rem; opacity: .85; }}
</style>
</head>
<body>
<header>
  <h1>🏐 Courtside Kiki</h1>
  <p>Daily D1 Women's Volleyball Stats — <span id="dateLabel">{date_display}</span></p>
</header>
<main>
<div class="nav">
  <button id="prev">&larr; Older</button>
  <select id="picker"></select>
  <button id="next">Newer &rarr;</button>
</div>
<div id="content">{sections}</div>
</main>
<script>
(async function () {{
  const picker = document.getElementById('picker');
  const content = document.getElementById('content');
  const label = document.getElementById('dateLabel');
  const prev = document.getElementById('prev');
  const next = document.getElementById('next');
  let days = [];
  try {{
    days = await (await fetch('days/manifest.json', {{cache: 'no-store'}})).json();
  }} catch (e) {{
    content.innerHTML = '<div class="card"><p class="empty">No days loaded yet.</p></div>';
    return;
  }}
  days.forEach(d => {{
    const o = document.createElement('option');
    o.value = d; o.textContent = d; picker.appendChild(o);
  }});
  async function show(d) {{
    picker.value = d;
    label.textContent = d;
    const i = days.indexOf(d);
    prev.disabled = i >= days.length - 1;
    next.disabled = i <= 0;
    content.innerHTML = '<p class="empty" style="color:#fff">Loading…</p>';
    try {{
      content.innerHTML = await (await fetch('days/' + d + '.html', {{cache: 'no-store'}})).text();
    }} catch (e) {{
      content.innerHTML = '<div class="card"><p class="empty">Could not load ' + d + '.</p></div>';
    }}
    history.replaceState(null, '', '#' + d);
  }}
  picker.onchange = () => show(picker.value);
  prev.onclick = () => show(days[days.indexOf(picker.value) + 1]);
  next.onclick = () => show(days[days.indexOf(picker.value) - 1]);
  const fromHash = location.hash.slice(1);
  show(days.includes(fromHash) ? fromHash : days[0]);
}})();
</script>
<p class="updated">Last refreshed {timestamp} · data via ncaa.com</p>
</body>
</html>
"""

GAME_TEMPLATE = """
<div class="game">
  <div class="matchup">
    <span>{away} @ {home}</span>
    <span class="score">{away_score} &ndash; {home_score}</span>
  </div>
  <div class="empty">{status}</div>
  {body}
</div>
"""

GAME_BODY_TEMPLATE = """
  <h4>Game Leaders</h4>
  {game_leaders_html}
  <h4>Set-by-Set</h4>
  {set_html}
  <h4>Team Totals</h4>
  {team_stats_html}
"""


# Per-game leaders, using the confirmed box score field names.
# (field in playerStats, label shown)
LEADER_FIELDS = [
    ("kills", "Kills"),
    ("assists", "Assists"),
    ("digs", "Digs"),
    ("serviceAces", "Aces"),
    ("totalBlocks", "Blocks"),
    ("points", "Points"),
]
MIN_ATTEMPTS_FOR_HITTING = 10


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _team_name_map(boxscore_json):
    return {
        str(t.get("teamId")): (t.get("nameShort") or t.get("nameFull") or "?")
        for t in (boxscore_json.get("teams") or [])
    }


def compute_game_leaders(boxscore_json):
    """Return [(label, [(player, team, value), ...ties]), ...] for this game."""
    if not boxscore_json:
        return []
    names = _team_name_map(boxscore_json)
    players = []
    for tb in boxscore_json.get("teamBoxscore") or []:
        team = names.get(str(tb.get("teamId")), "")
        for p in tb.get("playerStats") or []:
            full = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip() or "?"
            players.append((full, team, p))

    out = []
    for field, label in LEADER_FIELDS:
        vals = [(n, t, _num(p.get(field))) for n, t, p in players]
        vals = [v for v in vals if v[2] is not None]
        if not vals:
            continue
        top = max(v[2] for v in vals)
        if top > 0:
            out.append((label, [v for v in vals if v[2] == top]))

    # Hitting % only counts with enough swings to mean something
    hp = []
    for n, t, p in players:
        att, pct = _num(p.get("attackAttempts")), _num(p.get("hittingPercentage"))
        if att is not None and pct is not None and att >= MIN_ATTEMPTS_FOR_HITTING:
            hp.append((n, t, pct))
    if hp:
        top = max(v[2] for v in hp)
        out.append((f"Hitting % (min {MIN_ATTEMPTS_FOR_HITTING} att.)", [v for v in hp if v[2] == top]))
    return out


def render_game_leaders_table(leaders):
    if not leaders:
        return ""
    rows = []
    for label, tied in leaders:
        who = " / ".join(f"{n} ({t})" for n, t, _ in tied)
        val = tied[0][2]
        val_s = f"{val:.3f}" if "Hitting" in label else f"{val:g}"
        rows.append(f"<tr><td>{label}</td><td>{who}</td><td>{val_s}</td></tr>")
    return f"<table><tr><th>Stat</th><th>Leader</th><th>Value</th></tr>{''.join(rows)}</table>"


def render_set_table(boxscore_json):
    """Set-by-set attacking (kills / errors / attempts / hitting %) per team.
    The feed does not include set point scores, so this is what it offers."""
    if not boxscore_json:
        return ""
    names = _team_name_map(boxscore_json)
    per_team = []
    for tb in boxscore_json.get("teamBoxscore") or []:
        sets = (tb.get("teamStats") or {}).get("sets") or []
        per_team.append((names.get(str(tb.get("teamId")), "?"), sets))
    if not per_team or not any(s for _, s in per_team):
        return ""
    n_sets = max(len(s) for _, s in per_team)
    head = "".join(f"<th>Set {i + 1}</th>" for i in range(n_sets))
    rows = []
    for name, sets in per_team:
        cells = []
        for i in range(n_sets):
            s = sets[i] if i < len(sets) else None
            if s:
                cells.append(f"<td>{s.get('kills', '-')}-{s.get('attackErrors', '-')}-{s.get('attackAttempts', '-')}"
                             f"<br><small>{s.get('hittingPercentage', '-')}</small></td>")
            else:
                cells.append("<td>-</td>")
        rows.append(f"<tr><td>{name}</td>{''.join(cells)}</tr>")
    return (f"<table><tr><th>Attacking (K-E-TA / hit %)</th>{head}</tr>{''.join(rows)}</table>")


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


def _side_label(game, side):
    t = game.get(side, {}) or {}
    name = (t.get("names") or {}).get("short") or side.title()
    rank = t.get("rank")
    label = f"#{rank} {name}" if rank else name
    return f"<strong>{label}</strong>" if t.get("winner") else label


def _status_text(game):
    state = game.get("gameState")
    if state == "final":
        return "Final"
    if state == "pre":
        return f"Starts {game.get('startTime', '')}".strip()
    return f"Live &middot; {game.get('currentPeriod', '')}".strip()


def render_games_section(games, boxscores, team_stats_map):
    if not games:
        return '<div class="card"><h2>Games</h2><p class="empty">No D1 women\'s volleyball games found for this date.</p></div>'
    html_games = []
    for game in games:
        gid = game_id_of(game)
        box = boxscores.get(gid)
        if game.get("gameState") == "pre" or not box:
            body = '<p class="empty">Stats appear once the match is underway.</p>' \
                if game.get("gameState") == "pre" else '<p class="empty">Stats not available for this match.</p>'
        else:
            gl = render_game_leaders_table(compute_game_leaders(box)) \
                or '<p class="empty">Player leaders not available.</p>'
            body = GAME_BODY_TEMPLATE.format(
                game_leaders_html=gl,
                set_html=render_set_table(box) or '<p class="empty">Set data not available.</p>',
                team_stats_html=render_team_stats_table(team_stats_map.get(gid)),
            )
        html_games.append(GAME_TEMPLATE.format(
            away=_side_label(game, "away"), home=_side_label(game, "home"),
            away_score=team_score(game, "away"), home_score=team_score(game, "home"),
            status=_status_text(game), body=body,
        ))
    return f'<div class="card"><h2>Games &amp; Box Scores</h2>{"".join(html_games)}</div>'


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


def build_day(date):
    """Fetch one day and write its fragment to docs/days/<date>.html."""
    scoreboard = get_scoreboard(date)
    games = extract_games(scoreboard)

    boxscores, team_stats_map = {}, {}
    probed = False
    for game in games:
        gid = game_id_of(game)
        if gid and game.get("gameState") != "pre":  # nothing to fetch before first serve
            boxscores[gid] = get_boxscore(gid)
            team_stats_map[gid] = get_team_stats(gid)
            if not probed and game.get("gameState") == "final":
                # One-off probe: save the base game record so we can look for
                # set point scores (25-20 style), which boxscore lacks.
                time.sleep(REQUEST_DELAY_SECONDS)
                info = api_get(f"/game/{gid}")
                if info:
                    dump_raw(f"gameinfo_{gid}", info)
                probed = True

    sections = render_games_section(games, boxscores, team_stats_map)

    os.makedirs("docs/days", exist_ok=True)
    with open(f"docs/days/{date.isoformat()}.html", "w") as f:
        f.write(sections)
    log(f"Wrote docs/days/{date.isoformat()}.html ({len(games)} games found)")


def update_manifest_and_shell():
    """List every day page we have (newest first) and (re)write the shell."""
    days = sorted(
        (p[:-5] for p in os.listdir("docs/days")
         if p.endswith(".html") and p[:4].isdigit()),
        reverse=True,
    )
    with open("docs/days/manifest.json", "w") as f:
        json.dump(days, f)
    shell = PAGE_TEMPLATE.format(
        date_display="",
        sections='<p class="empty" style="color:#fff">Loading…</p>',
        timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
    )
    with open("docs/index.html", "w") as f:
        f.write(shell)
    log(f"Manifest now lists {len(days)} day(s)")


def parse_dates(argv):
    """No args: last 7 days (today back through 6 days ago). One arg: that
    date. Two args: inclusive range."""
    today = datetime.date.today()
    if len(argv) == 0:
        return [today - datetime.timedelta(days=i) for i in range(6, -1, -1)]
    start = datetime.date.fromisoformat(argv[0])
    end = datetime.date.fromisoformat(argv[1]) if len(argv) > 1 else start
    if end < start:
        start, end = end, start
    return [start + datetime.timedelta(days=i) for i in range((end - start).days + 1)]


if __name__ == "__main__":
    for d in parse_dates([a for a in sys.argv[1:] if a]):
        build_day(d)
    update_manifest_and_shell()
