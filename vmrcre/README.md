# VMRCRE / NTVMR integration

This directory holds the work that integrates the CBGM "Genealogical Queries"
tool into the [NTVMR](https://ntvmr.uni-muenster.de/) (New Testament Virtual
Manuscript Room) — the platform behind the *Editio Critica Maior*.

The long-term goal is for a finished Greek-apparatus project in the NTVMR to
"Start CBGM" and begin genealogical work directly, eventually sharing one
apparatus data structure between both tools. We get there in steps:

1. **Light** — import VMRCRE apparatus data into a CBGM database
   (`scripts/python/ntvmrimport.py`, on branch `vmrcre-data-import`).
2. **Medium** — run the tool inside the NTVMR using NTVMR authentication and
   roles (**implemented here**; see *Authentication* below).
3. **Mostly full** — add a `project_id` for multitenancy (one instance, many
   projects).
4. **More full** — remove PostgreSQL-only features so the tool can run on the
   NTVMR's relational database (MySQL).
5. **Full** — agree a common Greek-apparatus format both tools store.

## Authentication (NTVMR single sign-on) — implemented

The tool no longer keeps its own user database for hosted use. Instead it
trusts the NTVMR session and delegates role checks to the NTVMR.

How it works (all in `server/login.py`, wired up in `server/__main__.py`):

- A flask-login **`request_loader`** reads the NTVMR session cookie
  (`NTVMR_SESSION_COOKIE`, default `ntvmrSession`), calls
  `…/api/auth/session/check/` with that `sessionHash`, and on a `<user>`
  response builds an **`NtvmrUser`** from `internalUserID` + `userName`.
  This is the single-sign-on: a logged-in NTVMR user is a logged-in CBGM user.
- `NtvmrUser.has_role(name)` delegates to `…/api/auth/hasrole`, checking the
  NTVMR role **`<NTVMR_ROLE_PREFIX><name>`** (default prefix `CBGM `, so the
  tool's `editor` role is the NTVMR role `CBGM editor`). Because the existing
  access layer (`login.user_can_read/write`, `edit_auth`, etc.) already calls
  `current_user.has_role(...)`, **no other server code needed changing** — this
  is a cleaner seam than the original 2018 patch, which edited every call site.
- The Vue client sends the cookie cross-origin via
  `axios.defaults.withCredentials = true` and points `api.conf.js` at the
  NTVMR-proxied API base (e.g. `…/community/vmr/api/cbgm/<instance>/`).

### Configuration

Set these per-instance in `instance/*.conf` (defaults in
`server/__main__.py:Config`):

| key | default | meaning |
|-----|---------|---------|
| `NTVMR_API_URL`        | `https://ntvmr.uni-muenster.de/community/vmr/api/` | NTVMR API base |
| `NTVMR_SESSION_COOKIE` | `ntvmrSession` | name of the NTVMR session cookie |
| `NTVMR_ROLE_PREFIX`    | `CBGM ` | prefix mapping tool roles → NTVMR roles |
| `NTVMR_PROJECT_NAME`   | *(unset)* | if set, `has_role` is scoped to this NTVMR project |

`auth/hasrole` accepts `projectID`/`projectName`/`userGroupName` scoping, so
`NTVMR_PROJECT_NAME` is the hook for step 3: roles checked **within a specific
project** rather than globally. Leave it unset for global `CBGM <role>` checks.

To enable a role gate, set the standard CBGM access keys to a role name, e.g.
`WRITE_ACCESS = 'editor'` → requires NTVMR role `CBGM editor`.

### Known follow-ups / risks

- **Edit attribution**: edits set `ntg.user_id` to the NTVMR `internalUserID`.
  The book DB's transaction-time-state tables record this as an integer; verify
  there is no foreign key into the local `user` table before relying on it.
- **`auth/session/check` response shape** is assumed to be `<user
  internalUserID=… userName=…>` (matches the 2018 patch); confirm at runtime.
- The earlier hand-rolled service at
  `vmrcre/webapp/vmr/api/cbgm/ntvmr/user/index.jsp` (iframe SSO returning
  CBGM-shaped JSON) is **superseded** by the standard `auth/*` endpoints used
  here and can be retired.

## Provenance

- `ntg-auth-2018.patch` — the verbatim uncommitted diff recovered from the
  `~/src/ntg` working tree (the original auth integration against the 2018
  CCeH codebase, by Troy Griffitts). Kept for intent/history; **superseded** by
  the port in `server/`. The `~/src/ntg` and `~/src/ntg.try` checkouts can be
  removed once this branch is confirmed.
- `ntg-README.fixes` — the original `ntg` install/setup notes (PostgreSQL,
  `mk_users`, MySQL `.my.cnf`, client build), kept for reference.
