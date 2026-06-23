# CBGM × NTVMR — self-hosted, data-less Docker stack

Run the **Coherence-Based Genealogical Method** tool against your own
[NTVMR](https://ntvmr.uni-muenster.de/) projects. The images ship **no
apparatus data**: you log in with your NTVMR account, pick one of your
projects, click **Start CBGM**, and its apparatus is imported on demand.

Images: `crosswire/cbgm-app-server`, `crosswire/cbgm-db-server`.

## Quick start

```bash
mkdir cbgm && cd cbgm
curl -O https://raw.githubusercontent.com/<org>/intf-cbgm/<branch>/docker/docker-compose.crosswire.yml
docker compose -f docker-compose.crosswire.yml up
```

Then open **http://localhost:5000**:

1. Click **Log In** — you're sent to the NTVMR to sign in, and returned logged in.
2. Your NTVMR projects are listed. Click **Start CBGM** on one.
3. Watch the import progress (a few minutes for a full book). When it finishes
   the row turns into **Open** — click it to work in the CBGM tool.

Stop with `docker compose ... down`. Your imported projects (databases and
their instances) persist in the named volumes and reappear on the next start.

## Requirements

- Docker + Docker Compose.
- An **NTVMR account** that is a member of the project(s) you want to work on.
- The **`CBGM Editor`** role on the NTVMR to start an import (read access is
  `public`).

## Configuration (environment, set in the compose file)

| variable | default | meaning |
|----------|---------|---------|
| `NTVMR_API_URL` | `https://ntvmr.uni-muenster.de/community/vmr/api/` | the NTVMR this instance authenticates against and imports from |
| `CBGM_SCHEMA_TEMPLATE_DB` | `cbgm_template` | the empty schema each project DB is cloned from |
| `CBGM_IMPORT_DELAY` | `0.5` | seconds between apparatus requests (politeness) |
| `CBGM_START_ROLE` | `Editor` | NTVMR role (prefixed `CBGM `) required to start an import |

Persistence: the `pgdata` volume holds the per-project databases; the
`projects` volume holds their instance configs. Both are needed to keep
imported projects across restarts.

## Limitations

- **New Testament only** — CBGM book numbering covers the NT (Matthew–Revelation).
  Old-Testament projects (e.g. Psalms) are not yet supported.
- One CBGM database per project; imports are firsthand Greek witnesses only
  (correctors/versions/fathers are excluded, per CBGM).

## Building & publishing the images (maintainers)

The Vue client is built on the host, then baked into the app image.

```bash
# 1. build the client
cd client && npm install
NODE_OPTIONS=--openssl-legacy-provider ./node_modules/.bin/webpack --config webpack.dev.js
cd ..

# 2. stage sources + build images (see docker/Makefile for the canonical steps)
cd docker
mkdir -p client scripts && cp -a ../server ../ntg_common . \
  && cp -a ../client/build/* client/ && cp -a ../scripts/cceh/* scripts/ \
  && cp ../scripts/python/ntvmrimport.py scripts/
docker build -f Dockerfile          -t crosswire/cbgm-app-server:latest .
docker build -f Dockerfile.db.empty -t crosswire/cbgm-db-server:latest  .

# 3. push to Docker Hub (requires crosswire-org login)
docker login
docker push crosswire/cbgm-app-server:latest
docker push crosswire/cbgm-db-server:latest
```

For multi-arch (amd64 + arm64) use buildx:

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -f Dockerfile -t crosswire/cbgm-app-server:latest --push .
```

The data-less DB image ships `docker/backup/cbgm_template.dump` — a schema-only
dump of the CBGM database. Regenerate it from any populated CBGM database with:

```bash
pg_dump --schema-only -Fc -n ntg <some_cbgm_db> > docker/backup/cbgm_template.dump
```
