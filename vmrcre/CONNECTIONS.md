# Pluggable VMRCRE connections ("Connect to… ▾")

Generalises the CBGM tool's single hard-wired NTVMR backend into a list of
selectable VMRCRE instances (NTVMR, CoptOT, …). "Not connected" is the vanilla
upstream mode, which also makes NTVMR integration genuinely opt-in.

## Decisions (2026-06-27)

- **Single active connection at a time.** You are connected to one backend;
  picking another switches to it. One session at a time. Projects imported from
  a *non-active* backend stay visible but are read-only online ("reconnect to
  *X* to save") and editable offline via their per-project `.conf` identity.
- **Registry = shipped defaults + deployment config.** Built-in defaults for
  `ntvmr` and `coptot`; a deployment adds/overrides via config/env. No
  user-facing "add a connection" UI (yet).
- **Project list shows everything, grouped by connection.** Every locally
  mounted project is listed and badged by the backend it came from; the active
  connection additionally fetches its live project list.
- **No "Disconnect" button.** It earns its keep nowhere in a hosted deploy:
  switching backends implicitly leaves the previous one, going offline is handled
  by the unreachable-fallback, and logout was deliberately dropped (`ac3be00`).
  "Standalone" is meaningful only as the *unconfigured/upstream default* (or the
  natural initial state when a deploy lists backends but sets no default — the
  menu just prompts you to pick one).

## Model

**Connection registry** — global config `CBGM_CONNECTIONS`, a list of
`{id, label, api_url, site_url}`. Shipped defaults:

| id | label | api_url | site_url |
|----|-------|---------|----------|
| `ntvmr`  | NTVMR  | `https://ntvmr.uni-muenster.de/community/vmr/api/` | `https://ntvmr.uni-muenster.de/` |
| `coptot` | CoptOT | `https://coptot.manuscriptroom.com/community/vmr/api/` | `https://coptot.manuscriptroom.com/` |

`CBGM_DEFAULT_CONNECTION` names the id that is active before the user chooses.
Empty string = start standalone. Base ships `ntvmr` (preserves today's
behaviour); the **B2 toggle** for an upstream/standalone build is to set it `''`.

**Server resolver — `active_connection()`** (one place, used by
`ntvmr_api_url()`):

1. Instance sub-app bound to a connection (its `.conf` `CONNECTION_ID`) → that.
2. Root/info app → the `cbgmConnection=<id>` cookie → registry lookup.
3. Else → `CBGM_DEFAULT_CONNECTION` (may be empty → standalone, no NTVMR calls).

Back-compat: a deploy with only the legacy `NTVMR_API_URL` set (no
`CBGM_CONNECTIONS`) synthesises a single `ntvmr` connection from it, so existing
single-backend installs are unchanged.

**Cookies (single-active):** `cbgmConnection=<id>` (which backend) + the existing
session cookie (that backend's hash). Switching = set `cbgmConnection`, clear the
session, re-run the SSO dance against the new backend's domain.

**Per-project binding:** `_write_instance_conf` persists `CONNECTION_ID` +
`NTVMR_API_URL`, so an opened project resolves its own backend regardless of the
active connection.

**Client:** `connections.json` (registry + active id) drives a "Connect to… ▾"
menu in the page header; the active connection's `api_url` replaces the single
`window.ntvmr_api_url` for the SSO probe/redirect, login link, and site link.

## Behaviour matrix

| State | Project list | Editing |
|---|---|---|
| Not connected (no default) | locally-mounted only, grouped by origin | offline rules (conf identity) |
| Connected + online | active backend live list + all mounted, grouped/badged | active: full; others: reconnect-to-save |
| Connected + offline | all mounted, grouped | conf identity per project |

## Phasing

1. **Backend abstraction (server)** — registry + `active_connection()` +
   `connections.json` + `ntvmr_api_url()` via the resolver + persist
   `CONNECTION_ID`/`NTVMR_API_URL` in instance confs. NTVMR default-active →
   zero behaviour change; standalone (`default=''`) drops out for free (closes
   B2). *No UI change.*
2. **"Connect to…" menu (client)** — the dropdown, switching, the
   `cbgmConnection` cookie, standalone empty-state; `window.ntvmr_api_url` →
   active-connection resolution.
3. **Multi-backend list** — grouping/badging by connection, reconnect-to-save,
   CoptOT as a live second connection.
