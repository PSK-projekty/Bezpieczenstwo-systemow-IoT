# IoT Security Demo

This repository contains a small but complete management stack for IoT fleets. A FastAPI backend exposes JWT secured REST endpoints and a PyQt5 desktop client consumes them. The focus of the project is to demonstrate secure onboarding of devices, continuous telemetry, user administration and audit logging.

## Highlights

- JWT based authentication for people (access and refresh tokens) and devices (short lived access tokens). Each token type uses a dedicated signing key and expiry.
- Device catalogue with five ready-made categories (weather station, indoor thermometer, IP camera, air quality probe and smart lock). Categories define their own payload blueprint and emission cadence.
- Continuous telemetry simulator that generates readings for active devices with category specific intervals. Manual uploads still honour rate and size limits.
- Full CRUD for devices (create, detail, update, rotate secrets, deactivate, delete) and for users (admin only). User actions are available through `/admin/users` endpoints and the GUI.
- Audit log of security events (logins, denied requests, rotation attempts) available to administrators.
- CSV export of device readings straight from the GUI and on-demand filtering by ISO-8601 time ranges.
- CORS enabled by default so the API can be explored directly from a browser (`/docs`, `/redoc`).

## Directory layout

```
app/
  api/        # FastAPI routers (auth, devices, device data, admin, health)
  core/       # configuration and crypto helpers
  db/         # SQLAlchemy models and session factory (SQLite)
  schemas/    # Pydantic schemas for requests and responses
  services/   # business logic (auth, devices, readings, logging, simulator)
docs/         # additional architecture and API notes
gui/          # PyQt5 desktop client
```

More architectural notes are available in `docs/architecture.md`, while `docs/api_usage.md` documents every REST endpoint.

## Installation

```bash
python -m venv .venv          # optional but recommended
.\.venv\Scripts\activate       # Windows PowerShell
pip install -r requirements.txt
```

Configuration is handled via environment variables (see `.env.example`). By default the backend uses SQLite stored in `./data/iot_demo.db` and demo secrets.

## Running the backend

```bash
uvicorn app.main:app --reload
```

Useful endpoints:

- Interactive OpenAPI docs: <http://127.0.0.1:8000/docs>
- Redoc documentation: <http://127.0.0.1:8000/redoc>
- Health probe: <http://127.0.0.1:8000/healthz>

## Desktop GUI

The PyQt5 client (`python -m gui`) consumes the same REST API. Compared to the earlier revision it now features:

- A redesigned two-column layout without the redundant "system state" tab.
- Device creation wizard that lists the predefined categories and shows sample payloads.
- Continuous refresh of telemetry (using the simulator) with export to CSV.
- Quick actions for rotating secrets, invalidating tokens and deleting devices. Removed devices disappear from the list immediately.
- User management and security log tabs available to administrators.

Set `IOT_BACKEND_URL` if the backend runs on a different host.

## Testing

```bash
pytest
```

Ten tests cover registration, device lifecycle, rate limits, token handling and the admin surface. The suite uses an in-memory SQLite database and a disabled telemetry simulator for determinism.

## Security notes

- Distinct JWT secrets for user access, user refresh and device access tokens.
- Device secret rotation bumps an internal version counter so old tokens cannot be reused.
- Size and frequency limits on `/device/readings` prevent flooding the collector.
- All password and device secrets are stored as bcrypt hashes.
- Audit trail stored in the `security_events` table keeps track of both successful and denied actions.

## Purpose of JWT in this project

Access tokens created for humans encode the user id and role so that the backend can authorise each request without additional lookups. Devices obtain their own short lived token after presenting the one time secret generated during onboarding. Refresh tokens allow users to renew access without logging in again and are rotated on every use. Secrets, expiry times and even the signing algorithm can be adjusted in configuration (`Settings` in `app/core/config.py`).

## Project goal

This demo shows how to securely bootstrap IoT devices, guard their data plane and present the outcomes to operators. It is meant as a teaching aid for the IoT security course – feel free to extend it with a web front end, WebSocket telemetry or more advanced alerting.
