# 🧳 Chappa'ai

![Code Quality](https://github.com/t0mer/chappaai/actions/workflows/code-quality.yml/badge.svg)
![Tests](https://github.com/t0mer/chappaai/actions/workflows/test.yml/badge.svg)
![Build Image](https://github.com/t0mer/chappaai/actions/workflows/docker.yml/badge.svg)
![License](https://img.shields.io/github/license/t0mer/chappaai)
<!-- TODO: add a Docker Hub badge once techblog/chappaai is published -->

**Chappa'ai is a trip planner built from a WhatsApp group.** It listens to a WhatsApp group through [OpenWA](https://github.com/rmyndharis/OpenWA) and keeps everything the group posts, so the links, places and ideas shared while planning a trip are not lost in the chat. It never sends a WhatsApp message. Right now Chappa'ai is a **listen-only ingester with a web admin UI**: it stores group messages and reactions in PostgreSQL and lets you manage groups, contacts, sessions and the OpenWA connection. Trip indexing, search and a day-by-day planner (with your own LLM key) are coming in the next phases.

Based on [openwa_llm](https://github.com/t0mer/openwa_llm), originally [wa_llm](https://github.com/ilanbenb/wa_llm).

---

## Table of contents

- [Features](#features)
- [Docker Compose configurations](#-docker-compose-configurations)
- [Prerequisites](#-prerequisites)
- [Quick Start](#quick-start)
- [Admin UI](#admin-ui)
- [API usage](#5-api-usage)
- [Production deployment](#-production-deployment)
- [Developing](#developing)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- 👂 **Listen-only**: stores the text messages and reactions OpenWA delivers (groups and direct chats); the bot never replies or sends anything
- 📂 Persistent message history in PostgreSQL (`pgvector` image, ready for the indexing phase)
- 📱 Several WhatsApp numbers (OpenWA sessions) served from one OpenWA server
- 🖥️ Web admin UI: dashboard, groups, contacts, opt-outs, messages and settings, in light and dark
- 🔐 Signed (HMAC) and deduplicated webhooks; OpenWA credentials encrypted at rest
- ⚡ REST API with Swagger docs (`localhost:8000/docs`)

---

## 🐳 Docker Compose Configurations

This project includes multiple Docker Compose files for different environments:

| File                           | Purpose                                                                        | Usage                                                  |
| ------------------------------ | ------------------------------------------------------------------------------ | ------------------------------------------------------ |
| `docker-compose.yml`           | **Default**. Uses the pre-built `techblog/chappaai` image from Docker Hub (`amd64` and `arm64`) and `.env`. | `docker compose up -d`                                 |
| `docker-compose.dev.yml`       | **Development override**. Builds the `chappaai` service from this checkout (image `chappaai-dev`) and mounts `src/` and `migrations/`. | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build` |
| `docker-compose.prod.yml`      | **Production**. Uses the pre-built `techblog/chappaai` image from Docker Hub and `.env.prod`. Recommended for deployment. | `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d` |
| `docker-compose.local-run.yml` | **Local Execution**. For running the app on the host while PostgreSQL and OpenWA run in Docker. | `docker compose -f docker-compose.local-run.yml up -d` |
| `docker-compose.base.yml`      | **Base Configuration**. Contains shared service definitions.                   | ❌ **Do not use directly**                             |

---

## 📋 Prerequisites

- 🐳 Docker and Docker Compose
- 🐍 Python 3.13+ (only to run or develop outside Docker)
- 🗄️ PostgreSQL with the `pgvector` extension (the compose files run `pgvector/pgvector:pg17`)
- 🔑 Anthropic and Voyage AI API keys (required at startup; used by the upcoming indexing phase)
- 📲 A WhatsApp account for the bot

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/t0mer/chappaai.git
cd chappaai
```

### 2. Create .env file

Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
```

`SETTINGS_ENCRYPTION_KEY` is empty in the example and must be set (generate it as shown in the table below).

#### Environment Variables

| Variable                       | Description                                                                        | Default                                                      |
| ------------------------------ | ---------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `SETTINGS_ENCRYPTION_KEY`      | **Required.** Base64 of 32 random bytes; encrypts the OpenWA API key and webhook secret stored in the database. Generate with `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"`. Back it up with the database (see [Settings and sessions](#settings-and-sessions)) | – |
| `WHATSAPP_HOST`                | *Seed only.* OpenWA base URL (no `/api` suffix), imported on first start           | –                                                            |
| `OPENWA_API_KEY`               | *Seed only* for the app (imported on first start). Compose still passes it to the OpenWA container as its `API_MASTER_KEY` | – |
| `OPENWA_SESSION_ID`            | *Seed only.* `id` of an OpenWA session; becomes the first session on first start   | –                                                            |
| `OPENWA_WEBHOOK_SECRET`        | *Seed only.* HMAC secret for webhook signatures (>= 16 chars)                      | –                                                            |
| `OPENWA_WEBHOOK_URL`           | *Seed only.* Base URL OpenWA posts to; each session registers `<url>/<session id>` | –                                                            |
| `VOYAGE_API_KEY`               | **Required.** Voyage AI key                                                        | –                                                            |
| `VOYAGE_MAX_RETRIES`           | Retries for Voyage API calls                                                       | `5`                                                          |
| `DB_URI`                       | **Required.** PostgreSQL URI (use the `postgresql+asyncpg://` scheme)              | –  (`.env.example`: `postgresql+asyncpg://user:password@localhost:5432/postgres`) |
| `LOG_LEVEL`                    | Log level (`DEBUG`, `INFO`, `ERROR`)                                               | `INFO`                                                       |
| `ANTHROPIC_API_KEY`            | **Required.** Anthropic API key (a real key, starting with `sk-`)                  | –                                                            |
| `LOGFIRE_TOKEN`                | **Required.** Logfire monitoring token (a real Logfire token)                      | –                                                            |
| `MODEL_NAME`                   | LLM model id                                                                       | `anthropic:claude-sonnet-4-6`                                |
| `ADMIN_PASSWORD`               | Admin UI login password. The admin UI is disabled unless both this and `ADMIN_SESSION_SECRET` are set | –                                          |
| `ADMIN_SESSION_SECRET`         | Secret (>= 32 random chars) that signs the admin session cookie; generate with `openssl rand -hex 32`. Changing it logs everyone out | – |
| `ADMIN_COOKIE_SECURE`          | Mark the admin session cookie `Secure`; set to `true` when served over HTTPS       | `false`                                                      |
| `TIMEZONE`                     | IANA time zone in which the dashboard statistics are bucketed (invalid values stop startup) | `Asia/Jerusalem`                                    |
| `PORT`, `HOST`                 | Address the web server listens on (the compose files set `PORT=8000`)             | `5001`, `0.0.0.0`                                            |
| `DEBUG`                        | Debug flag                                                                         | `false`                                                      |

The OpenWA connection (base URL, API key, webhook URL and webhook secret) and the WhatsApp sessions are stored in the database and managed in **Admin > Settings** (see [Settings and sessions](#settings-and-sessions)). The *seed only* variables are read once, on the first start where no connection is stored yet: the connection is imported when `WHATSAPP_HOST`, `OPENWA_API_KEY` and `OPENWA_WEBHOOK_SECRET` are all set, and a session is added when `OPENWA_SESSION_ID` is set. After that, changing them in the env file has no effect on the app. The compose files set `WHATSAPP_HOST` and `OPENWA_WEBHOOK_URL` for you.

### 3. Starting the Services

**Option A: Default (pre-built image from Docker Hub)**

```bash
docker compose up -d
```

The `chappaai` image is pulled from Docker Hub on every `up`.

**Development (build from source)**

Build the admin UI on the host first, because the mounted `src/` supplies `src/admin/static/dist`:

```bash
(cd web && npm ci && npm run build)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

**Option B: Production (pre-built images)**

`OPENWA_API_KEY` (passed to the OpenWA container as `API_MASTER_KEY`) and `SETTINGS_ENCRYPTION_KEY` (passed to the `chappaai` service) must be available to compose interpolation; `docker compose` stops with an error if either is missing. Compose reads `.env` for this, not the `env_file:` entries, so if your keys live only in `.env.prod`, pass it explicitly:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

The `chappaai` service also reads `.env.prod`. The OpenWA API key the app uses comes from **Admin > Settings** (imported from `OPENWA_API_KEY` on the first start only), so if you ever change the OpenWA container's key, enter the new one in Settings too.

### 4. Connect your device

Creating a WhatsApp session and pairing it (QR code) happen in OpenWA; the app only connects to sessions that already exist there. Enable the admin UI first (see [Enabling it](#enabling-it)), because sessions are added in **Admin > Settings**.

1. Start the stack, then create and start a session in OpenWA (use your `OPENWA_API_KEY`):

   ```bash
   curl -s -X POST http://localhost:2785/api/sessions \
     -H "X-API-Key: $OPENWA_API_KEY" -H "Content-Type: application/json" \
     -d '{"name":"chappaai"}'            # note the returned "id"
   curl -s -X POST http://localhost:2785/api/sessions/<id>/start -H "X-API-Key: $OPENWA_API_KEY"
   ```

2. Get the QR code (`GET /api/sessions/<id>/qr` returns a PNG data URL) or use the dashboard at http://localhost:2785, and scan it with your WhatsApp mobile app. Wait until the session status is `ready`.
3. Open `http://localhost:8000/admin/settings` and check the **Connection** (with compose it was imported on the first start: base URL `http://whatsapp:2785`, webhook URL `http://chappaai:8000/webhook`). If it is empty, fill in the base URL, API key, webhook URL and webhook secret and click **Save connection**. Under **Sessions**, add the session with a label of your choice and the OpenWA session `id` from step 1. It becomes active immediately, with no restart: the app syncs its groups and registers its webhook in OpenWA. The session shows its OpenWA status (`ready` once paired), and **Test connection** now checks OpenWA (it needs at least one session).
4. Add the bot's WhatsApp number to the trip groups you want Chappa'ai to follow, then enable them in **Groups** (see the next step).

Repeat steps 1, 2 and 3 for every further WhatsApp number the bot should serve. If `OPENWA_SESSION_ID` was already set on the very first start, that session was added for you and step 3 is only a check.

#### Upgrading from openwa_llm (renamed volumes)

The compose stack was renamed: the app service is now `chappaai` (was `web-server`), the image is `techblog/chappaai` (was `techblog/openwa_llm`) and the named volumes are `chappaai_postgres` and `chappaai_openwa` (were `wa_llm_postgres` and `wa_llm_openwa`). The compose files pin these volume names, so **an existing deployment's `wa_llm_*` volumes are not picked up automatically**: a plain `docker compose up` starts with an empty database and an unpaired OpenWA. To keep your data, either:

- copy the old volumes into the new ones before the first start, for example:

  ```bash
  docker volume create chappaai_postgres
  docker run --rm -v wa_llm_postgres:/from -v chappaai_postgres:/to alpine sh -c "cp -a /from/. /to/"
  # repeat for wa_llm_openwa -> chappaai_openwa
  ```

- or keep using the old volumes by changing the `name:` of `chappaai_postgres` / `chappaai_openwa` under `volumes:` in your compose files to `wa_llm_postgres` / `wa_llm_openwa`.

Also update the stored webhook URL: if the connection in **Admin > Settings** still points at `http://web-server:8000/webhook`, change it to `http://chappaai:8000/webhook` and save (this re-registers every session's webhook). The compose files already allow the `chappaai` host in OpenWA's `SSRF_ALLOWED_HOSTS`.

#### Upgrading from env-only OpenWA settings

Earlier versions read the OpenWA settings from the env file on every start. They now live in the database:

1. **Add `SETTINGS_ENCRYPTION_KEY`** to your env file before upgrading (the web server does not start without it, and compose stops with an error). Generate it as shown in [Settings and sessions](#settings-and-sessions) and back it up.
2. **Keep the old `OPENWA_*` / `WHATSAPP_HOST` values in place for the first start.** The database migration assigns all existing groups and messages to one session created from `OPENWA_SESSION_ID` (it is called `default`; rename it in Settings). On startup the connection is imported from `WHATSAPP_HOST`, `OPENWA_API_KEY`, `OPENWA_WEBHOOK_SECRET` and `OPENWA_WEBHOOK_URL`. If `OPENWA_SESSION_ID` is not set but data exists, the migration creates a disabled `default` session: set its OpenWA session id in Settings and enable it.
3. **Check Admin > Settings** after the first start. From now on, edit the connection there; later changes to those env vars are ignored (except `OPENWA_API_KEY`, which compose still passes to the OpenWA container as `API_MASTER_KEY`).
4. **Delete the old webhook in OpenWA (optional).** Each session now registers its own URL, `<webhook url>/<session id>`, for example `http://chappaai:8000/webhook/<session id>`. A webhook registered earlier at the bare `/webhook` URL keeps being accepted while exactly one session is enabled (with more than one it gets `404`), but OpenWA then delivers every event to both URLs. Both resolve to the same session, and a delivery whose `X-OpenWA-Idempotency-Key` was already processed is skipped, so the duplicate is dropped only if OpenWA sends the same key to both webhooks (not verified). Delete the old registration in OpenWA (its webhooks are listed by `GET /api/sessions/<id>/webhooks`, or use the OpenWA dashboard) so events are not processed twice.

#### Upgrading from the go-whatsapp-web-multidevice (gowa) setup

Earlier versions used [go-whatsapp-web-multidevice](https://github.com/aldinokemal/go-whatsapp-web-multidevice) as the WhatsApp gateway. It has been replaced by OpenWA, so existing deployments need to:

- **Re-pair the bot.** The OpenWA session is new; scan a fresh QR code as described above. Messages, senders, groups and opt-outs in PostgreSQL are unaffected.
- **Update your env file.** Remove `WHATSAPP_BASIC_AUTH_USER` and `WHATSAPP_BASIC_AUTH_PASSWORD`; add `SETTINGS_ENCRYPTION_KEY`, `OPENWA_API_KEY`, `OPENWA_SESSION_ID` and `OPENWA_WEBHOOK_SECRET`; point `WHATSAPP_HOST` at OpenWA (port `2785`, not `3000`). The OpenWA values are imported on the first start, as described in [Upgrading from env-only OpenWA settings](#upgrading-from-env-only-openwa-settings).
- **Expect a new volume.** OpenWA stores its data in `chappaai_openwa`. The old `wa_llm_whatsapp` volume is no longer used and can be removed once you no longer need it.

#### Upgrading from the summary bot

This version removes the bot features of openwa_llm: summaries (on-demand and scheduled), summary schedules and languages, the knowledge base and its Q&A, mention replies, link-spam notices, the DM auto-reply, the WhatsApp opt-out/opt-in/status commands, the **Bot actions** page and the `POST /summarize_and_send_to_groups` and `POST /load_new_kbtopics` endpoints. A database migration drops their tables and columns. Remove any cron job that still calls those endpoints, and drop `QA_TESTERS`, `QA_TEST_GROUPS`, `SCHEDULER_ENABLED` and `DM_AUTOREPLY_*` from your env file (they are ignored).

### 4b. Enabling a group

Open **Admin > Groups** and turn on a group's **Enabled** switch (the UI asks for confirmation). The group list is synced from OpenWA, so a group appears once the bot's number is in it. You can also give a group a display name and edit its community keys there. In the upcoming phases, enabling a group makes it a trip.

### Admin UI

A web admin UI (served at `/admin`) lets you manage Chappa'ai without touching the database:

- **Dashboard**: the start page. Statistics and charts for a date range: groups, chats, messages, active senders, reactions, messages over time, top groups and senders, and activity by hour and weekday (see [Dashboard](#dashboard)).
- **Groups**: enable or disable a group, edit community keys and set a display name.
- **Contacts**: view and edit sender names.
- **Opt-outs**: view, add and remove opted-out contacts. The list is managed only here (there are no WhatsApp commands).
- **Messages**: read-only message browser with search and filters.
- **Settings**: the OpenWA connection and the WhatsApp sessions the bot serves (see [Settings and sessions](#settings-and-sessions)).
- **Session switcher**: at the top of every page. Dashboard, Groups and Messages show the selected session only; with a single session it just shows its name.

The UI follows the Iris design language: Rubik (bundled with the app, no external font requests), a violet primary colour, soft borders and rounded cards.

- **Theme:** System, Light or Dark. Pick it in the account menu (sidebar footer) or in the **More** sheet on phones. The choice is remembered in the browser; System follows the OS setting live.
- **Navigation:** a sidebar on desktop (Dashboard, Groups, Messages, Contacts, Opt-outs, Settings; labels from 1024px wide, icon-only on tablets from 768px) and, on phones, a header with a bottom tab bar (Dashboard, Groups, Messages) plus a **More** sheet (Contacts, Opt-outs, Settings, theme, log out).
- **Responsive Groups:** a compact table from 1280px, cards below that (two columns from 768px, one column on phones). Contacts, Opt-outs and Messages turn into stacked cards on phones, and dialogs (such as Edit group) become bottom sheets.
- **Confirmations, errors and toasts** use SweetAlert2, themed to match light or dark.
- **Accessibility:** a "Skip to content" link is the first tab stop, everything works from the keyboard, dialogs trap focus and return it to the control that opened them, and group names and JIDs render correctly for right-to-left (Hebrew) text.

#### Enabling it

The admin UI is **off by default**. Set both `ADMIN_PASSWORD` and `ADMIN_SESSION_SECRET` (they are intentionally not set in `.env.example`), restart the web server (`docker compose restart chappaai`) and open `http://localhost:8000/admin`:

```bash
ADMIN_PASSWORD=choose-a-strong-password
ADMIN_SESSION_SECRET=$(openssl rand -hex 32)
```

- Sessions last 12 hours. Logging out only clears the browser cookie: sessions are stateless, so change `ADMIN_SESSION_SECRET` to revoke all of them.
- Login attempts are rate-limited to 5 failures per minute per client IP. The limiter keys on the connecting address, so behind a reverse proxy configure the proxy / uvicorn forwarded-headers handling so clients are not all seen as one address.
- HTTPS is strongly recommended: terminate TLS at a reverse proxy and set `ADMIN_COOKIE_SECURE=true`.
- The admin API lives under `/api/v1/admin` (login-protected; see Swagger at `/docs`).

#### Dashboard

`/admin` opens on the Dashboard: an overview of the activity Chappa'ai has stored.

- **Date range:** presets 24 hours, 7 days (the default), 30 days, 90 days and All time, plus **Custom** with From and To dates (days in your browser's local time; the To day is included). The range is kept in the URL (`?range=30d`, `?range=custom&from=2026-08-01&to=2026-08-31`), so reloading or sharing the link keeps it. An invalid or reversed custom range shows an error and is not applied.
- **Auto-refresh:** the relative presets (24 hours to 90 days) reload every 60 seconds while the tab is visible; a refresh missed while the tab was hidden runs when you come back. Custom ranges and All time do not refresh.
- **Tiles:** Groups (all time, with the number of managed, i.e. enabled, groups), Chats (groups and direct chats with at least one message in the range), Messages, Active senders and Reactions.
- **Charts:** Messages over time, Top 5 groups, Top senders (top 10), Activity by hour of day, Activity by weekday and Text vs media (text, media and other messages). Messages over time is grouped per hour, day, week (weeks start on Monday) or month depending on the length of the range. Every chart has a **Show as table** toggle that shows the same numbers as a table.
- **Time zone:** hours, days and weekdays are counted in the server time zone from `TIMEZONE` (default `Asia/Jerusalem`), shown under the range picker.
- **Session:** the numbers cover the session selected in the switcher (its groups and its direct chats). With no active session every number is zero.
- **Bot messages are excluded** from every number (messages and reactions sent by the bot's own WhatsApp account). The bot's identity comes from the live WhatsApp session; if it cannot be looked up, the numbers include the bot and the page says "Bot messages could not be identified and are included".
- A range without messages shows the tiles with zeros and "No messages in this range" instead of the charts.

<!-- TODO: refresh screenshot (dashboard screenshots still show the removed Knowledge-base topics tile and Bot actions navigation) -->
![Dashboard showing tiles and charts for the last 7 days](assets/screenshots/admin-dashboard-light.png)
![Dashboard for the last 7 days (dark)](assets/screenshots/admin-dashboard-dark.png)

The 30 days preset, grouped per day:

![Dashboard for the last 30 days](assets/screenshots/admin-dashboard-30d-light.png)

A custom range with the From and To dates:

![Dashboard with a custom date range](assets/screenshots/admin-dashboard-custom-light.png)

"Show as table" on the weekday chart, and a range with no messages:

![Activity by weekday shown as a table](assets/screenshots/admin-dashboard-table-light.png)
![Dashboard empty state for a range without messages](assets/screenshots/admin-dashboard-empty-light.png)

On phones the tiles use two columns, the charts stack in one column and the tab bar starts with Dashboard:

<!-- TODO: refresh screenshot -->
<p>
<img src="assets/screenshots/admin-mobile-dashboard-light.png" alt="Dashboard on mobile (light)" width="180">
<img src="assets/screenshots/admin-mobile-dashboard-dark.png" alt="Dashboard on mobile (dark)" width="180">
</p>

The numbers come from `GET /api/v1/admin/stats` (login-protected with the admin session cookie, like the rest of the admin API):

| Parameter | Description |
| --------- | ----------- |
| `from`    | Start of the range, ISO 8601. Optional: defaults to the earliest message (or 7 days before `to` when there are no messages). |
| `to`      | End of the range, ISO 8601, inclusive. Optional: defaults to now. |
| `session_id` | Session id (from `GET /api/v1/admin/settings/sessions`). Optional while only one session is active; required (`400` otherwise) when several are, and `404` for an unknown or inactive session. Groups and Messages take the same parameter. |

Datetimes without an offset are read in `TIMEZONE`. Both must lie between 1970 and 2100, and `from` must not be after `to` (otherwise `422`). Example: `GET /api/v1/admin/stats?from=2026-10-01T00:00:00&to=2026-10-07T23:59:59`.

The response contains:

- `from`, `to` (the resolved range in the configured zone), `timezone` and `bot_excluded` (`false` when the bot could not be identified and its messages are counted).
- Counts in the range: `messages`, `chats` (distinct chats), `active_senders` (distinct senders) and `reactions`; `groups` is `{total, managed}` and is not limited to the range.
- `split`: `{text, media, other}`. Text is a message with text and no media, media is a message with media, other is the rest.
- `bucket` and `series` (`[{start, count}]`, zero-filled). The bucket is `hour` for ranges up to 48 hours, `day` up to 92 days, `week` up to two years (weeks start on Monday, so the first slot can start before `from`) and `month` beyond that.
- `top_groups` (up to 5) and `top_senders` (up to 10), each `[{…_jid, name, count}]` ordered by count, then JID. A group's `name` is its display name or WhatsApp name, a sender's is the push name; either can be `null` (the UI then shows the number from the JID).
- `by_hour` (24 counts, hour 0 to 23) and `by_weekday` (7 counts, 0 = Sunday to 6 = Saturday).

#### Settings and sessions

**Settings** (`/admin/settings`) holds the OpenWA connection and the WhatsApp sessions the bot serves. One OpenWA server can host several WhatsApp sessions (numbers); the bot serves every enabled one. Changes apply immediately, without restarting the web server.

![Settings page with the OpenWA connection and three sessions](assets/screenshots/admin-settings-light.png)
![Settings page (dark)](assets/screenshots/admin-settings-dark.png)

**Connection** (one for all sessions):

- **OpenWA base URL** (for example `http://whatsapp:2785` inside compose), **API key** (the OpenWA server's `API_MASTER_KEY`), **Webhook URL** and **Webhook secret** (at least 16 characters; OpenWA signs every delivery with it).
- The API key and webhook secret are stored encrypted and are never shown or returned by the API; the form shows "•••• stored" instead. Leave a secret field blank to keep the stored value. Stored secrets are never sent to a different host: when you change the base URL (trailing slashes aside), enter the API key and webhook secret again, otherwise saving fails with `422` (the form says so under the URL).
- The base URL cannot be a literal link-local or cloud metadata address (`169.254.0.0/16`, `fe80::/10`); host names are not resolved for this check.
- The webhook URL is a base URL: each session registers `<webhook url>/<session id>` in OpenWA, for example `http://chappaai:8000/webhook/<session id>`. Leave it blank to skip webhook registration (for example when you register webhooks yourself).
- **Save connection** reloads every session and re-registers its webhook. **Test connection** checks OpenWA with the values in the form (blank fields fall back to the stored ones; a changed base URL needs the API key typed again) by reading the status of the first session. It reports `connected`, `OpenWA returned HTTP <status>`, or `cannot reach OpenWA (<error type>)`; OpenWA's own response text is never shown.

**Sessions:**

- Add a session with a **label** (your own name for it) and the **OpenWA session id** (the `id` OpenWA returned when the session was created; each one can be added only once). Creating sessions and pairing them by QR code stay in OpenWA (see [Connect your device](#4-connect-your-device)).
- Each session shows its OpenWA status (for example `ready`), the number of groups it owns, and an error if it could not be started. **Enabled** turns a session on or off without deleting it; a disabled session receives nothing.
- **Sync now** imports that session's groups from OpenWA right away and reports how many it owns. Groups are otherwise synced when a session starts and after its webhook is registered; chats and messages are not imported, they are stored as OpenWA delivers them to the webhook.
- **Re-register webhook** registers (or updates) that session's webhook in OpenWA again, for example after OpenWA lost it. A successful registration also syncs the session's groups.
- **Delete** is refused while the session still owns groups or messages; disable it instead.

**How data is split between sessions:**

- **One WhatsApp group belongs to exactly one session**: the first session that syncs the group owns it. If a second session's number is in the same group, it does not take the group over, and its copies of that group's messages are ignored. Group settings follow the group's session. Messages, including direct chats, belong to the session that received them.
- **Contacts and opt-outs are shared**: a sender's name and an opt-out apply in every session.
- The **session switcher** at the top of each admin page picks the session that Dashboard, Groups and Messages show. The choice is remembered in the browser. Disabled sessions cannot be selected; with no enabled session the switcher links to Settings.

![Session switcher on Groups with the "Family phone" session selected](assets/screenshots/admin-session-switcher-light.png)

**The encryption key.** `SETTINGS_ENCRYPTION_KEY` is required and must be base64 of exactly 32 random bytes (AES-256-GCM). Generate it once:

```bash
python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
# or: openssl rand -base64 32
```

> **Warning:** back up `SETTINGS_ENCRYPTION_KEY` together with the database. Without the key the stored API key and webhook secret cannot be decrypted, and nothing can recover them: every session then shows a decryption error until you enter the API key and webhook secret again in Settings. Changing the key has the same effect. It is separate from `ADMIN_SESSION_SECRET`, so rotating the login secret never touches the stored credentials.

The settings API (login-protected, under `/api/v1/admin/settings`; like every admin `POST`/`PUT`/`PATCH`/`DELETE`, it also needs the `X-Requested-With: admin-ui` header, otherwise `403`):

| Method   | Path                                            | Purpose |
| -------- | ----------------------------------------------- | ------- |
| `GET`    | `/api/v1/admin/settings/connection`             | The connection: `base_url`, `webhook_url`, `api_key_set`, `webhook_secret_set` (secrets are never returned) |
| `PUT`    | `/api/v1/admin/settings/connection`             | Save `base_url`, `webhook_url`, `api_key`, `webhook_secret`. A missing or `null` secret keeps the stored one (both are required the first time, and again whenever `base_url` changes: `422` otherwise). A link-local `base_url` is `422`. Reloads all sessions and re-registers their webhooks |
| `POST`   | `/api/v1/admin/settings/connection/test`        | Check OpenWA with optional `base_url`, `api_key` and `openwa_session_id` (fallback: the stored values and the first session; a `base_url` different from the stored one needs `api_key`, else `422`). Returns `{ok, detail}`, where `detail` is `connected`, `OpenWA returned HTTP <status>` or `cannot reach OpenWA (<error type>)` |
| `GET`    | `/api/v1/admin/settings/sessions`               | List sessions: `id`, `label`, `openwa_session_id`, `enabled`, `status`, `error`, `group_count` (the status is refreshed live, 3 seconds at most) |
| `POST`   | `/api/v1/admin/settings/sessions`               | Add a session: `{label, openwa_session_id}` (`409` if that OpenWA session id is already used) |
| `PATCH`  | `/api/v1/admin/settings/sessions/{session_id}`  | Change `label`, `openwa_session_id` or `enabled` |
| `DELETE` | `/api/v1/admin/settings/sessions/{session_id}`  | Delete a session (`409` while it still owns groups or messages) |
| `POST`   | `/api/v1/admin/settings/sessions/{session_id}/sync` | Import the session's groups now; returns `{"groups": <count owned>}` (`409` if the session is not active, `502` with the HTTP status or error type if OpenWA failed) |
| `POST`   | `/api/v1/admin/settings/sessions/{session_id}/webhook` | Re-register the session's webhook (`409` if the session is not active or no webhook URL is set, `502` with the HTTP status or error type if OpenWA refused) |

`{session_id}` is the app's own session id (the `id` field), not the OpenWA session id. The same id is used by the `session_id` query parameter of the other admin endpoints and `/status`, and in the webhook URL.

#### Notes

- **Group names:** the WhatsApp name, topic and owner are refreshed from WhatsApp and are read-only. The "display name" is your own alias and survives syncs.

#### Screenshots

<!-- TODO: refresh screenshot (all desktop and mobile screenshots below still show the removed Bot actions navigation item; they will be refreshed in the next phase) -->

#### Login
![Login](assets/screenshots/admin-login-light.png)
![Login (dark)](assets/screenshots/admin-login-dark.png)

#### Groups
<!-- TODO: refresh screenshot (Groups still shows the removed spam notice and Schedules columns) -->
![Groups](assets/screenshots/admin-groups-light.png)
![Groups (dark)](assets/screenshots/admin-groups-dark.png)

At about 900px the sidebar collapses to icons and Groups shows cards:

![Groups with the icon-only sidebar](assets/screenshots/admin-sidebar-collapsed-light.png)

The account menu holds the theme switch (System / Light / Dark) and log out:

![Account menu](assets/screenshots/admin-account-menu-light.png)

Between 768px and 1279px Groups shows cards; the full sidebar appears from 1024px:

![Groups on a 1024px tablet](assets/screenshots/admin-groups-tablet-light.png)

Toasts (SweetAlert2) appear in the top-right corner, here after **Re-register webhook** in Settings:

![Toast](assets/screenshots/admin-toast-light.png)

Editing a group (display name and community keys):

<!-- TODO: refresh screenshot (the Edit group dialog still shows the removed Summary language field) -->
![Edit group](assets/screenshots/admin-groups-edit-light.png)
![Edit group (dark)](assets/screenshots/admin-groups-edit-dark.png)

Enabling a group asks for confirmation (SweetAlert2):

<!-- TODO: refresh screenshot -->
![Enable group confirmation](assets/screenshots/admin-groups-confirm-light.png)
![Enable group confirmation (dark)](assets/screenshots/admin-groups-confirm-dark.png)

#### Contacts
![Contacts](assets/screenshots/admin-contacts-light.png)
![Contacts (dark)](assets/screenshots/admin-contacts-dark.png)

#### Opt-outs
![Opt-outs](assets/screenshots/admin-opt-outs-light.png)
![Opt-outs (dark)](assets/screenshots/admin-opt-outs-dark.png)

#### Messages
![Messages](assets/screenshots/admin-messages-light.png)
![Messages (dark)](assets/screenshots/admin-messages-dark.png)

#### Settings
The OpenWA connection and the sessions (more in [Settings and sessions](#settings-and-sessions)):

![Settings](assets/screenshots/admin-settings-light.png)
![Settings (dark)](assets/screenshots/admin-settings-dark.png)

The session switcher above every page, here with the "Family phone" session selected:

![Session switcher](assets/screenshots/admin-session-switcher-light.png)

#### Mobile
<p>
<img src="assets/screenshots/admin-mobile-groups-light.png" alt="Groups on mobile (light)" width="180">
<img src="assets/screenshots/admin-mobile-groups-dark.png" alt="Groups on mobile (dark)" width="180">
<img src="assets/screenshots/admin-mobile-messages-light.png" alt="Messages on mobile (light)" width="180">
<img src="assets/screenshots/admin-mobile-messages-dark.png" alt="Messages on mobile (dark)" width="180">
<img src="assets/screenshots/admin-mobile-more-light.png" alt="More sheet on mobile (light)" width="180">
<img src="assets/screenshots/admin-mobile-more-dark.png" alt="More sheet on mobile (dark)" width="180">
</p>

### 5. API usage

Swagger docs are available at `http://localhost:8000/docs`.

#### Key Endpoints

- <b>/webhook/{session id} (POST)</b> OpenWA webhook, signed with the webhook secret (see [Webhooks](#webhooks)).
- <b>/status (GET)</b> Health check: OpenWA session status (with `bot_jid` and `bot_lid`) and database connectivity; `503` when unhealthy. Add `?session_id=<session id>` when more than one session is active.
- <b>/readiness (GET)</b> Lightweight readiness check that returns `{"status": "ok"}` immediately.
- <b>/api/v1/admin/stats (GET)</b> Dashboard statistics for a date range, bot messages excluded (admin login required; see [Dashboard](#dashboard)).
- <b>/api/v1/admin/settings/…</b> OpenWA connection and sessions (admin login required; see [Settings and sessions](#settings-and-sessions)).
- <b>/api/v1/admin/groups</b>, <b>/contacts</b>, <b>/opt-outs</b>, <b>/messages</b> The data behind the admin pages (admin login required).

---

## 🚀 Production Deployment

To deploy in a production environment using the optimized configuration:

1. **Create Production Environment File**:
   Copy `.env.example` to `.env.prod` and configure your production secrets.

   ```bash
   cp .env.example .env.prod
   ```

2. **Start Services** (`--env-file` lets compose read `OPENWA_API_KEY` from `.env.prod`, see [Starting the Services](#3-starting-the-services)):

   ```bash
   docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
   ```

This configuration includes:

- Automatic restart policies (`restart: always`)
- Startup ordering: the `chappaai` service waits for a healthy PostgreSQL

The container runs `alembic upgrade head` before starting the app, so database migrations are applied on every start.

---

## Developing

### Setup

Install dependencies using `uv`:

```bash
uv sync --all-extras --dev
```

### Development Commands

The project uses **Poe the Poet** for task automation with parallel execution:

```bash
# Run all checks (format, then parallel lint/typecheck/test)
uv run poe check

# Individual tasks
uv run poe format     # Format code with ruff
uv run poe lint       # Lint code with ruff
uv run poe typecheck  # Type check with pyright
uv run poe test       # Run tests with pytest

# List all available tasks
uv run poe
```

The `check` command runs formatting first, then executes linting, type checking, and testing **in parallel** for faster execution.

### Frontend (admin UI)

The admin UI is a React 19 + Vite SPA in `web/` (Node 20) styled with Tailwind CSS 4, Radix UI primitives, lucide icons and SweetAlert2. Design tokens (colours, radii, fonts) for light and dark live in `web/src/index.css`:

```bash
cd web
npm ci
npm run dev    # dev server; proxies /api to localhost:8000, open http://localhost:5173/admin/
npm run lint   # type check
npm test       # unit tests
npm run build  # writes to src/admin/static/dist, served by the backend
```

The Docker build compiles the SPA in a Node stage, so no local build is needed for images.

Admin integration tests need a Postgres database whose name contains `test`:

```bash
ADMIN_TEST_DB_URI=postgresql+asyncpg://user:password@localhost:5432/<db with "test" in its name> uv run pytest
```

> **Warning:** that database's tables are dropped and recreated.

### CI

GitHub Actions workflows in `.github/workflows/`:

- `code-quality.yml` and `test.yml` (with a `pgvector/pgvector:pg17` service) run on pull requests; `pr-lint.yml` checks PR titles.
- `docker.yml` is started manually: it runs both checks, builds `techblog/chappaai` for `linux/amd64` and `linux/arm64`, pushes `:latest` and `:<version>` (date-based `YYYY.M.PATCH`, auto-incremented by `scripts/next-version.sh` when no version is given) and then tags the commit.

### Key Files

- Main application: `app/main.py`
- WhatsApp gateway interface and types: `src/whatsapp/gateway.py`, `src/whatsapp/types.py`
- OpenWA client and webhook parser: `src/whatsapp/openwa.py`, `src/whatsapp/openwa_webhook.py`
- Webhook and status endpoints: `src/api/webhook.py`, `src/api/status.py`
- Stored OpenWA settings (encryption, one-time env import, per-session gateway registry): `src/openwa_settings/`; settings API: `src/admin/settings.py`
- Message handler (listen-only: stores messages and reactions): `src/handler/__init__.py`, `src/handler/base_handler.py`
- Database models: `src/models/`; migrations: `migrations/`
- Admin backend (auth, API, SPA serving): `src/admin/`
- Admin frontend (React SPA): `web/`

---

## Architecture

The project consists of several key components:

- FastAPI backend (`chappaai` service) that receives webhooks and serves the admin API and UI
- [OpenWA](https://github.com/rmyndharis/OpenWA) (engine `whatsapp-web.js`) as the WhatsApp gateway, accessed through a gateway-neutral `WhatsAppGateway` interface
- PostgreSQL (`pgvector/pgvector:pg17`) storing groups, senders, messages, reactions, opt-outs and the encrypted OpenWA settings
- A listen-only message handler: inbound messages and reactions are stored, nothing is ever sent back to WhatsApp

```mermaid
flowchart LR
    WA[WhatsApp group] --> OpenWA[OpenWA]
    OpenWA -- "signed webhook<br/>POST /webhook/{session id}" --> API[chappaai<br/>FastAPI]
    API -- "groups sync, session status" --> OpenWA
    API --> DB[(PostgreSQL<br/>pgvector)]
    UI[Admin UI /admin] -- "/api/v1/admin" --> API
```

### Webhooks

OpenWA delivers incoming messages, reactions and group events to `POST /webhook/{session id}`, one URL per session (the session id is the app's own id shown by `GET /api/v1/admin/settings/sessions`):

- **Signed requests.** Every request must carry `X-OpenWA-Signature: sha256=<hex>`, the HMAC-SHA256 of the raw body using the webhook secret from **Admin > Settings > Connection**. The signature is verified before the body is parsed or the session is looked up; a missing or invalid signature (or no stored secret) returns `401`, malformed JSON returns `400`, and bodies larger than 2 MiB return `413`. A signed delivery for an unknown or disabled session is acknowledged and ignored.
- **Registration.** If the connection has a webhook URL, the web server registers (or updates) `<webhook url>/<session id>` with OpenWA for every active session, for `message.received`, `message.reaction` and the `group.*` events: at startup (retrying for a few minutes while OpenWA starts), when a session is added or enabled, when the connection is saved, and on **Re-register webhook**. After a successful registration the session's groups are synced again. OpenWA's SSRF guard must allow that host; the compose files set `SSRF_ALLOWED_HOSTS` for you.
- **Legacy URL.** The bare `POST /webhook` used by earlier versions still works while exactly one session is enabled. It needs the same signature (checked first, so an unsigned request gets `401` whatever the number of sessions); a signed request returns `404` when zero or several sessions are enabled. See [Upgrading from env-only OpenWA settings](#upgrading-from-env-only-openwa-settings).
- **Redelivery.** OpenWA delivers at least once. Deliveries are deduplicated per session on `X-OpenWA-Idempotency-Key`; a delivery whose processing failed is not marked as seen, so OpenWA's retry is processed again.
- **Group events** (`group.*`) re-sync the session's groups from OpenWA.
- **Identities.** Users are stored as `<number>@s.whatsapp.net`; the adapter converts OpenWA's `@c.us` ids in both directions. Senders that OpenWA reports as `@lid` are mapped to their phone number when `RESOLVE_LID_TO_PHONE=true` (set in the compose files) provides `senderPhone`.
- **The bot's own `@lid`.** WhatsApp may identify the bot by a privacy id (`<digits>@lid`) instead of its phone number. At runtime the app learns the bot's own `@lid` from OpenWA (`GET /api/sessions/<id>/contacts/check/<phone>`, field `whatsappId`) and caches it; the dashboard excludes the bot's messages under either id. If the lookup fails (OpenWA error, session not ready, unexpected response), only the phone-number id is known, and the lookup is not retried for 300 seconds. Check `bot_lid` in `/status` (add `?session_id=<session id>` when more than one session is active): it is the learned id, or `null` when unknown. For an OpenWA server you run yourself, set `RESOLVE_LID_TO_PHONE=true` so senders also resolve to phone numbers.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## License

[MIT](LICENSE)
