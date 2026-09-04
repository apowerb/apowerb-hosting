# Docker Compose deployment

Use this option to run the stack from the published container images.

## Files

- Compose entrypoint: [docker-compose.yml](docker-compose.yml)
- Collector configuration, used by the optional logs profile:
  [otel-collector.yaml](otel-collector.yaml)
- Traefik overlay: [docker-compose.traefik.yml](docker-compose.traefik.yml)
- Environment template: [../.env.example](../.env.example)
- Secret bootstrap script: [../scripts/generate-secrets.sh](../scripts/generate-secrets.sh)

## Prerequisites

- Docker Engine
- Docker Compose v2
- A local `.env` file created from `.env.example`

## Quick start

1. Copy the environment template.
2. Optional but recommended: run the bootstrap helper to populate missing secret values in `.env`.
3. Start the stack.

Run these from the repository root. The Compose file lives in this folder, so
it has to be named explicitly. There IS a `docker-compose.yml` at the root, and
it is not this one: it targets Hostman App Platform, has no Postgres, and will
refuse to start without a managed database. Naming the file is what keeps the
two apart.

```bash
cp .env.example .env
./scripts/generate-secrets.sh

docker compose -f docker-compose/docker-compose.yml --env-file .env up -d
```

To check that the result actually works — schema, sign-up, sign-in, and an agent
answering — follow [TESTING.md](TESTING.md). For a ten-second check of a
deployment you already have, from outside:

```bash
scripts/check-deployment.sh http://localhost:3000
```

## What this starts

The Compose stack runs three services:

- `postgres` on its internal Docker network
- `apowerb` backend on port `8000`
- `apowerb-ui` frontend on port `3000`

## Logs and agent traces (optional)

Off by default. Two more services — an OpenTelemetry collector and the
`th2pulse` ingest — are deployed only when the `logs` profile is on, and the
stack is otherwise unchanged.

Uncomment both lines in `.env`:

```
COMPOSE_PROFILES=logs
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
```

They belong together. The profile alone runs an ingest nobody writes to; the
endpoint alone leaves the application retrying an exporter with nowhere to
send.

`./scripts/generate-secrets.sh` fills `TH2PULSE_INGEST_TOKEN` and
`TH2PULSE_QUERY_TOKEN`. They are required, not hardening: the ingest binds
`0.0.0.0` inside its container — a container's loopback reaches nothing — and
refuses to start without them, because `/spans` serves recorded tool
arguments and responses.

What gets stored: the agent traces ADK emits natively — tool executions with
their arguments and responses, LLM calls, durations — each tied to its
conversation and user, in a `th2pulse` schema of the same Postgres.
Application log records are a separate path and stay empty for now: they need
the backend image to call `th2pulse.init_observability`, which it does not
do yet.

The collector is not optional plumbing between the two: the application
exports OTLP in protobuf, the ingest reads OTLP/JSON only, and
`encoding: json` in [otel-collector.yaml](otel-collector.yaml) is what
bridges them.

## Published images

The stack uses the published images below:

- Backend: `apowerb/apowerb`
- Frontend: `apowerb/apowerb-ui`
- Ingest, with the `logs` profile: `apowerb/th2pulse`
- Collector, with the `logs` profile: `otel/opentelemetry-collector-contrib`

The backend and frontend tags are PINNED to a pair that was proven together,
not left on `latest`. They cap each other in both directions -- the frontend
calls routes the older backends do not serve, and a newer backend can drop a
route an older frontend still calls -- so move both or neither.

These can be overridden in `.env` with:

- `APOWERB_BACKEND_IMAGE`
- `APOWERB_BACKEND_TAG`
- `APOWERB_FRONTEND_IMAGE`
- `APOWERB_FRONTEND_TAG`
- `TH2PULSE_IMAGE`, `TH2PULSE_TAG`
- `OTEL_COLLECTOR_IMAGE`, `OTEL_COLLECTOR_TAG`

## Important environment variables

The Compose stack depends on these values from `.env`:

- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_SSLMODE`
- `ENCRYPT_KEY`
- `TH2AGENT_PORT`
- `FRONT_PORT`
- `PUBLIC_API_URL`

## Secrets

`ENCRYPT_KEY` must be present before startup.
The helper script in [../scripts/generate-secrets.sh](../scripts/generate-secrets.sh) is a bootstrap convenience that fills missing values in `.env` without overwriting existing ones.

## Useful commands

```bash
docker compose -f docker-compose/docker-compose.yml --env-file .env ps
docker compose -f docker-compose/docker-compose.yml --env-file .env logs -f apowerb
docker compose -f docker-compose/docker-compose.yml --env-file .env logs -f apowerb-ui
docker compose -f docker-compose/docker-compose.yml --env-file .env down
```

## Single-host HTTPS overlay

For a public VM or a self-hosted host, run the overlay that adds Traefik:

```bash
docker compose -f docker-compose/docker-compose.yml -f docker-compose/docker-compose.traefik.yml --env-file .env up -d
```

This requires `APP_HOST` and `ACME_EMAIL` in `.env`.
