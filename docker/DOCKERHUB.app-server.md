# crosswire/cbgm-app-server

Run the **Coherence-Based Genealogical Method (CBGM)** tool against your own
[NTVMR](https://ntvmr.uni-muenster.de/) projects. Ships **no data** — you log
in with your NTVMR account, pick a project, and import it on demand.

## Start it

You need **Docker** and an **NTVMR account**.

```bash
curl -O https://raw.githubusercontent.com/scribe777/intf-cbgm/vmrcre-auth-integration/docker/docker-compose.crosswire.yml
docker compose -f docker-compose.crosswire.yml up
```

Then open **http://localhost:8088**:

1. **Log In** (you're sent to the NTVMR and back).
2. Pick a project → **Start CBGM**.
3. Wait for the import, then click **Open**.

That's it — you're in the CBGM tool.

> Already using port 8088? Change the host side of `"8088:5000"` in the compose
> file to any free port and browse there instead.

Stop with `docker compose -f docker-compose.crosswire.yml down`. Your imported
projects persist and reappear next time.

---

<details>
<summary>More: dump files, collaboration, permissions, config</summary>

### The "⋯" menu (per project)
- **Load from CBGM dump file** — provision from an existing CBGM dump instead
  of the NTVMR (e.g. apparatus produced in ITSEE).
- **Reload from NTVMR** — re-import, replacing the local copy.
- **Refresh All Decisions** — apply every decision saved to the NTVMR so
  coherence/affinity analysis spans the whole project.

### Permissions
- Running, importing, loading, and editing locally need only that you're
  **logged in** — no special role.
- **Saving decisions back to the NTVMR** (where other editors see them) needs
  the per-project **`Project CBGM Editor`** role. Decisions save **per user,
  per verse**, so collaborators can hold and compare different decisions on the
  same verse.

### Configuration (compose environment)
| variable | default | meaning |
|----------|---------|---------|
| `NTVMR_API_URL` | `https://ntvmr.uni-muenster.de/community/vmr/api/` | NTVMR to authenticate against and import from |
| `CBGM_SCHEMA_TEMPLATE_DB` | `cbgm_template` | empty schema each project DB is cloned from |
| `CBGM_IMPORT_DELAY` | `0.5` | seconds between apparatus requests |
| `CBGM_START_ROLE` | *(empty)* | if set, NTVMR role (prefixed `CBGM `) required to start an import; empty = any logged-in user |
| `CBGM_SAVE_ROLE` | `Project CBGM Editor` | per-project role required to save decisions to the NTVMR |

### Limitations
- **New Testament only** (Matthew–Revelation).
- NTVMR imports are firsthand Greek witnesses only (per CBGM).

</details>

Pairs with [`crosswire/cbgm-db-server`](https://hub.docker.com/r/crosswire/cbgm-db-server).
Built from [intf-cbgm](https://github.com/scribe777/intf-cbgm); CBGM tool by the
[INTF](https://www.uni-muenster.de/INTF/), NTVMR integration by
[CrossWire](https://crosswire.org/).
