# crosswire/cbgm-db-server

The PostgreSQL database server for a self-hosted, **data-less** deployment of
the **Coherence-Based Genealogical Method (CBGM)** tool. It ships **only an
empty CBGM schema template** (`cbgm_template`) — no apparatus data. Each
project's database is cloned from that template and populated on demand when a
user starts CBGM on one of their [NTVMR](https://ntvmr.uni-muenster.de/)
projects.

Use it together with
[`crosswire/cbgm-app-server`](https://hub.docker.com/r/crosswire/cbgm-app-server)
— see that repository's overview for the quick start.

## Quick start

This image is not run on its own; bring up the full stack:

```bash
mkdir cbgm && cd cbgm
curl -O https://raw.githubusercontent.com/scribe777/intf-cbgm/vmrcre-auth-integration/docker/docker-compose.crosswire.yml
docker compose -f docker-compose.crosswire.yml up
```

The compose file references this image as service **`ntg-db-server`** — keep
that service name, since the app server uses it as its `PGHOST`. Per-project
databases persist in the `pgdata` named volume.

## What's inside

- PostgreSQL with the `ntg` role/schema the CBGM tool expects.
- A schema-only `cbgm_template` database (current CBGM schema, `labez` widened
  to `varchar(64)`), restored at first initialization.

## Source

Built from the `vmrcre-auth-integration` branch of the
[intf-cbgm](https://github.com/scribe777/intf-cbgm) repository.
