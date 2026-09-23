# Courtside Kiki — Daily Volleyball Stats Dashboard

Pulls D1 women's volleyball scores, box scores, and national stat
leaders every day and publishes them to a free webpage — no manual
steps once it's set up.

## What it does

1. `fetch_stats.py` calls the free [ncaa-api](https://github.com/henrygd/ncaa-api)
   for the day's scoreboard, each game's box score, and national
   individual stat leaders.
2. It renders everything into `docs/index.html` — a single
   Courtside-Kiki-styled page.
3. A GitHub Actions workflow (`.github/workflows/daily.yml`) runs
   that script automatically every morning and commits the updated
   page.
4. GitHub Pages serves `docs/index.html` at a permanent URL.

## One-time setup (10 minutes)

1. **Create a new repo on GitHub** (public or private both work),
   e.g. `courtside-kiki-stats`.
2. **Upload these files** to it, keeping the folder structure:
   - `fetch_stats.py`
   - `.github/workflows/daily.yml`
   - `README.md`
   (Easiest way: on GitHub, "Add file" → "Upload files," drag all three/four
   in — GitHub will recreate the `.github/workflows/` folder for you
   automatically as long as the file path is preserved.)
3. **Turn on GitHub Pages:**
   - Go to the repo's **Settings → Pages**
   - Under "Build and deployment," set **Source** to
     **"Deploy from a branch"**
   - Branch: `main`, folder: `/docs` → Save
   - GitHub will give you a URL like
     `https://<your-username>.github.io/courtside-kiki-stats/`
     — that's your permanent dashboard link.
4. **Kick off the first run manually** so you don't have to wait for
   tomorrow morning:
   - Go to the repo's **Actions** tab
   - Click **"Daily Volleyball Stats"** in the left sidebar
   - Click **"Run workflow"** → **"Run workflow"**
   - Give it a minute, then refresh your Pages URL.

After that, it runs on its own every day at the time set in
`daily.yml` (currently 11:00 UTC / ~7am ET — edit the `cron` line to
change it).

## If the first run looks off

This was built without the ability to test live against the NCAA
data feed, so the request patterns are solid (they're the API's
documented routes) but the exact JSON field names inside each
response are best-effort. Two things that make fixing it fast:

- The workflow also commits the **raw JSON** it received to
  `data/raw/` — so if a section looks empty or wrong, that raw file
  shows exactly what came back.
- Paste that raw JSON back and it's a quick, targeted fix to the
  parsing in `fetch_stats.py` — no need to redo any of the setup.

## Adding more stat categories

`STAT_CATEGORIES` near the top of `fetch_stats.py` currently tracks
Kills, Assists, and Aces per set. To add Digs, Blocks, or Hitting
Percentage:

1. Go to https://www.ncaa.com/stats/volleyball-women/d1
2. Pick the stat from the "Individual Statistics" dropdown
3. Copy the number at the end of the URL
   (`.../current/individual/<NUMBER>`)
4. Add a line to `STAT_CATEGORIES` in `fetch_stats.py`, e.g.:
   `"Digs Per Set": 123,`
