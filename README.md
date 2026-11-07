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
│   └── discord/
│       ├── client.py     # barebones discord.Client + command tree wrapper
│       ├── builder.py    # builds a client and registers commands onto it
│       ├── commands.py   # slash command definitions
│       ├── constants.py  # fabricated sample data for /test-bookable-movies
│       ├── messages.py   # mention/embed/layout rendering
│       └── notifier.py   # DiscordNotifier
├── jobs/
│   ├── base.py           # Job protocol
│   └── cineplex/         # first Job: Cineplex ticket-availability alerts
│       ├── client.py          # Cineplex API wrapper
│       ├── bookable_movies.py # movie/batch domain types + grouping logic
│       └── job.py
├── repository/
│   └── cineplex/
│       ├── bookable_movie_subscribers.py # bookable_movie_subscribers persistence
│       └── notified_movies.py            # notified_movies persistence
└── db/
    ├── connection.py      # asyncpg pool + migration runner
    └── migrations/
```

Adding a new Job means adding a new package under `jobs/` and registering it in `main.py`'s `build_jobs`. It only needs to accept a `Notifier` in `run()` — it never talks to Discord directly.

## Running

Two deployments of this project are expected: your own machine, pointed at a test Discord server, for development; and a separate server, pointed at the real Discord server, for prod. Each is a fully independent stack — its own `.env`, its own `db_data` volume, its own bot token/channel.

`ENABLED_JOBS` in `.env` is a comma-separated list. Clear it (or remove `cineplex` from it) to turn a job off without touching code.

`APP_ENV` in `.env` should be `dev` or `prod` (defaults to `prod` if unset). Dev-only slash commands like `/test-bookable-movies` are only registered when it's `dev`, so they never show up on the real bot.

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

Tracks which movies become newly bookable at a fixed, small set of watched theatres and posts a Discord message for each one. Runs hourly, filtering out special-event listings and international/subtitled releases so subscribers only hear about things they'd actually want to book. Needs no configuration — the watched theatres, exclusion rules, and notified-movie tracking all live under `src/discordstuff/jobs/cineplex/`.

## Development

```bash
pip install -e ".[dev]"
pytest
```
