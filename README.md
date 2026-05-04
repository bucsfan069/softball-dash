# Class B North Softball Dashboard

A lightweight dashboard for tracking Maine high school softball — built around
Lawrence High School and the rest of **Class B North**. Pulls data from the
Maine Principals' Association, calculates Heal Points, and renders a coaching-
friendly view of standings, schedules, opponent scouting, and head-to-head
history.

## What you get

- **Heal Point standings** with both the Preliminary Index (PI) and Tournament
  Index (TI). TI is what MPA uses for playoff seeding, so this is the number
  coaches care about.
- **Schedule & results** view, filterable by team and by
  past/upcoming/all.
- **Opponent scouting cards** for every Class B North team, with a deep-link
  to their MaxPreps page for extra context.
- **Head-to-head comparison** — pick any two teams to see their records, TI,
  playoff seed, head-to-head history, and common opponents.
- **"What-if" projection engine** (in `scraper/heal_points.py`) that lets you
  simulate remaining games and see how the standings would change.

## Architecture

It's deliberately simple: a Python scraper writes JSON, a static site reads
it. No database, no backend server.

```
softball-dash/
├── scraper/
│   ├── config.py              # Team list, URL params, season dates
│   ├── fetch_mpa.py           # HTTP fetcher w/ cache + polite delays
│   ├── parse_mpa.py           # HTML parsers (BeautifulSoup)
│   ├── heal_points.py         # PI + TI calculation engine
│   ├── build_data.py          # Orchestrator → writes JSON
│   ├── seed_demo_data.py      # Generates demo data for first-time setup
│   ├── test_heal_points.py    # Unit tests for the math
│   └── requirements.txt
├── site/
│   ├── index.html
│   ├── assets/styles.css
│   ├── assets/app.js
│   └── data/                  # JSON written by the scraper
└── .github/workflows/refresh.yml   # Scheduled refresh + Pages deploy
```

## Quickstart (local)

```bash
cd scraper
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Optional: generate demo data so the dashboard renders before the first
# live scrape.
python seed_demo_data.py

# Run the unit tests for the Heal Point math.
python test_heal_points.py

# Pull live data for the current season (requires network access to mpareports.com).
python build_data.py

# Or backfill a specific past season:
python build_data.py --year 2024
```

Then serve the site with the built-in dev server (enables the Refresh button):

```bash
python3 serve.py
# Open http://localhost:8000
```

The dev server also exposes `POST /api/refresh` which the "Refresh" button in the
dashboard header uses to re-run the scraper for the selected season without leaving
the browser.

## Heal Point formula (for reference)

```
POINTS_PER_WIN = { A: 40, B: 35, C: 30, D: 25 }

PreliminaryIndex  = Σ POINTS_PER_WIN[opp_class] / scheduled_games
                    (1.0 if the team has no wins)

TournamentIndex   = Σ opponent.PreliminaryIndex (for each win)
                    / scheduled_games × 10
```

TI is what determines seeding within a region (e.g. Class B North). Higher
is better.

## Deploying

The dashboard is static — any host works:

- **GitHub Pages** (recommended): the included GitHub Actions workflow
  refreshes the data three times a day and redeploys automatically.
- **Netlify / Vercel**: point at the `site/` folder.
- **Local only**: just keep running `python -m http.server` in `site/`.

### GitHub Pages setup

1. Push this repo to GitHub.
2. In repo settings, enable Pages and set the source to "GitHub Actions".
3. The `refresh.yml` workflow runs at 6am / 4pm / 10pm Eastern by default.
   Edit the cron schedule if you want different times.
4. You can manually trigger a refresh from the **Actions** tab at any time.

## Maintenance notes

- **The team list** in `config.py` needs to be updated each spring, because
  Maine reclassifies high schools by enrollment every two years. Double
  check the Class B North roster at the start of the season.
- **MPA report IDs** (sport / classification / region) occasionally change
  between seasons. If the scraper returns empty data, open the MPA
  softball rankings page in your browser, copy the URL, and update
  `config.py`.
- **MaxPreps scouting links** are URL-guessed from team slugs. If a team's
  MaxPreps page is at a different URL, just edit the `maxpreps_slug` field
  in `config.py`.

## Coach's quick guide (for your wife's staff)

Three numbers matter most:

1. **TI (Tournament Index)** — seeding. Win a game against a strong
   opponent and TI jumps more than a win against a weak one.
2. **PI (Preliminary Index)** — how much raw Heal Point value you've
   accumulated. Every win counts the same in PI based on the opponent's
   class; opponent strength doesn't enter until TI.
3. **Strength of schedule** — the opponents you haven't played yet
   determine your TI ceiling. Use the Head-to-Head view to eyeball
   remaining opponents.

Playoff seeding in Class B North: top 8 TIs qualify for the tournament;
seeds are set in descending TI order.

## License & data sourcing

Data is fetched from public MPA pages with polite request spacing and a
descriptive user-agent. Please don't pound their servers — the built-in
cache and 1.5s delay are there for a reason. For any redistribution of
this data, verify you're complying with MPA's terms.
