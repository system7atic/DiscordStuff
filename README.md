# DiscordStuff

Personal automation that watches external sources and alerts you through Discord. Built so the alerting channel and the individual watchers are decoupled: Discord is a `Notifier` implementation (see `src/discordstuff/notifications/`), and each watcher is a `Job` (see `src/discordstuff/jobs/`) that can be turned on or off via config, independent of the others.

See `CONTEXT.md` for the glossary (Notifier, Job, Theatre, Bookable, etc.).

## Architecture

```
src/discordstuff/
├── config.py            # env-driven, immutable Config
├── main.py               # entrypoint: wires everything together
├── scheduler.py          # generic JobScheduler — runs enabled jobs on an interval
├── notifications/
│   ├── base.py           # Notifier protocol (the "black box")
│   └── discord_notifier.py
├── jobs/
│   ├── base.py           # Job protocol
│   └── cineplex/         # first Job: Cineplex ticket-availability alerts
│       ├── client.py     # Cineplex API wrapper
│       ├── repository.py # notified_movies persistence
│       └── job.py
└── db/
    ├── connection.py      # asyncpg pool + migration runner
    └── migrations/
```

Adding a new Job means adding a new package under `jobs/` and registering it in `main.py`'s `build_jobs`. It only needs to accept a `Notifier` in `run()` — it never talks to Discord directly.

## Running

Two deployments of this project are expected: your own machine, pointed at a test Discord server, for development; and a friend's server, pointed at the real Discord server, for prod. Each is a fully independent stack — its own `.env`, its own `db_data` volume, its own bot token/channel.

`ENABLED_JOBS` in `.env` is a comma-separated list. Clear it (or remove `cineplex` from it) to turn a job off without touching code.

### Dev (your machine)

Rebuilding the app's Docker image on every code change is slow, so for dev only run Postgres through Docker and run the app bare:

```bash
cp .env.example .env
# fill in .env, but set DATABASE_URL to the host-exposed port:
#   DATABASE_URL=postgresql://discordstuff:discordstuff@localhost:5435/discordstuff

docker compose up db -d          # Postgres only, exposed on localhost:5435
pip install -e ".[dev]"
python -m discordstuff.main      # run the app directly, reads .env via python-dotenv
```

`localhost:5435` is also how you'd point pgAdmin (or any DB client) at this project's database — ports 5432–5434 were already taken by other local projects, hence 5435.

### Prod (friend's server)

```bash
cp .env.example .env
# fill in .env — DATABASE_URL stays as the compose default (postgresql://discordstuff:discordstuff@db:5432/discordstuff)
docker compose up --build -d
```

To deploy an update later: `git pull && docker compose up -d --build`.

## Cineplex job setup

This job polls Cineplex's unofficial JSON API for movies that just went on sale (regular, advance, or coming-soon) at one specific theatre, and posts a Discord message for each.

**Status: skeleton only.** `CineplexClient` and `CineplexJob` raise `NotImplementedError` — the actual response field names and whether server-side requests get past Cineplex's bot protection (Imperva/Incapsula) haven't been verified yet. See inline comments in `src/discordstuff/jobs/cineplex/client.py` and `job.py`.

Config needed in `.env`:

- `CINEPLEX_API_KEY` — the `Ocp-Apim-Subscription-Key` header value. It's a public front-end key, not a per-user secret: open cineplex.com in Chrome, open DevTools → Network, click any `apis.cineplex.com` request, and copy the header from Request Headers. If the job starts erroring with 401/403, this key was likely rotated — grab a fresh one.
- `CINEPLEX_THEATRE_ID` — the theatre to watch. Not yet known; find it via the `/v1/theatres` endpoint once the client is implemented.
- `CINEPLEX_CITY`, `CINEPLEX_REGION`, `CINEPLEX_REGION_CODE`, `CINEPLEX_POSTAL_CODE`, `CINEPLEX_LATITUDE`, `CINEPLEX_LONGITUDE` — location query params the site sends; set these to match your theatre's area.

Known endpoints (base `https://apis.cineplex.com/prod/cpx/theatrical/api`):

- `GET /v1/movies/bookable?language=en` — all movies currently purchasable anywhere.
- `GET /v1/theatres?language=en&filmId={id}&...location...` — theatres near a location selling a given film.
- `GET /v1/dates/bookable?filmId={id}` — dates with tickets on sale for a film.

This is personal-use-only automation against an undocumented, unofficial API whose terms of use prohibit automated access — keep polling to at most hourly with a handful of requests per run, and expect it to break without notice.

## Development

```bash
pip install -e ".[dev]"
pytest
```
