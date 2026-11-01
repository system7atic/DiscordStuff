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

Two deployments of this project are expected: your own machine, pointed at a test Discord server, for development; and a separate server, pointed at the real Discord server, for prod. Each is a fully independent stack — its own `.env`, its own `db_data` volume, its own bot token/channel.

`ENABLED_JOBS` in `.env` is a comma-separated list. Clear it (or remove `cineplex` from it) to turn a job off without touching code.

### Development

Rebuilding the app's Docker image on every code change is slow, so for dev only run Postgres through Docker and run the app bare:

```bash
cp .env.example .env
# fill in .env, but set DATABASE_URL to the host-exposed port:
#   DATABASE_URL=postgresql://discordstuff:discordstuff@localhost:5435/discordstuff

make dev-db   # Postgres only, exposed on localhost:5435
make dev      # pip install -e ".[dev]", then run the app directly, reads .env via python-dotenv
```

`localhost:5435` is also how you'd point pgAdmin (or any DB client) at this project's database — ports 5432–5434 were already taken by other local projects, hence 5435.

### Prod

The prod server pulls the prebuilt image from GHCR instead of building from source, so it only needs `docker-compose.yml` and `.env` (no git clone required):

```bash
cp .env.example .env
# fill in .env — DATABASE_URL stays as the compose default (postgresql://discordstuff:discordstuff@db:5432/discordstuff)
make pull-up
```

To publish a new image after a code change (from your dev machine): `make push`. To deploy that update on the prod server: `make pull-up`. To stop the stack: `make down`.

`make build-up` still works for building the image from local source directly on a host — useful if you don't want to go through GHCR.

## Cineplex job

Tracks which movies become newly bookable (regular, advance, or coming-soon) at one specific theatre — that is, movies that weren't bookable there before but are now — and posts a Discord message for each. Polls Cineplex's unofficial JSON API hourly to check. No config needed — see `src/discordstuff/jobs/cineplex/`:

- `location.py` — the one theatre this watches (SilverCity Riverport Cinemas, Richmond BC, `theatreId=1409`) and its location query params. Single-theatre use case, so this is a hardcoded constant rather than env config.
- `client.py` — the API wrapper. The `Ocp-Apim-Subscription-Key` header is a public front-end key, not a per-user secret: Cineplex hardcodes it into their own Next.js app bundle, so the client fetches `cineplex.com`, finds the `_app-*.js` chunk, and regexes the key out of it — no manual DevTools copying needed. On a 401/403 it re-discovers the key once and retries automatically before giving up.
- `repository.py` — `notified_movies` persistence. A movie is marked notified only once it's confirmed bookable at the one watched theatre (not just bookable somewhere). First run seeds the table silently from whatever's already on sale there, so you don't get a flood of pings for things that were already available.
- `job.py` — ties it together: skips special-event listings (`isEvent`) and international/subtitled releases (`is_international` — detected via the `"International"` genre tag and/or a title pattern like `"(Hindi w/e.s.t.)"`, verified against all 106 currently-bookable titles on 2026-10-31 with zero false positives/negatives), raises instead of silently continuing on an empty movie list or an API/parsing failure (the scheduler turns any raised exception into a Discord error alert automatically).

Verified against the live API on 2026-10-31: response shapes for `/v1/movies/bookable`, `/v1/theatres`, `/v1/dates/bookable`; that plain server-side requests (no browser, no special headers beyond the subscription key) aren't blocked by Cineplex's Imperva/Incapsula bot protection from this network.

This is personal-use-only automation against an undocumented, unofficial API whose terms of use prohibit automated access — keep polling to at most hourly with a handful of requests per run, and expect it to break without notice. If the prod server's IP turns out to be blocked by Imperva (datacenter IPs are more likely to be flagged than residential ones), that's the one thing not yet verified — it can only be tested by actually running the job there.

## Development

```bash
pip install -e ".[dev]"
pytest
```
